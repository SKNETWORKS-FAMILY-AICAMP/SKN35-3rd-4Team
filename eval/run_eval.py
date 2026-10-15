"""평가 실행 (4번): 같은 질문을 우리 챗봇(팀 그래프)과 일반 LLM에 보내고 답을 그대로 저장한다.

채점은 하지 않는다. 채점은 eval/score.py가 저장된 답을 읽어서 한다 (다시 돌리지 않고 채점만 바꿀 수 있게).

    python eval/run_eval.py                       # 질문 36개 + 분류 확인 질문 14개, 두 시스템 모두
    python eval/run_eval.py --only q01,q02        # 일부만
    python eval/run_eval.py --systems bot         # 우리 챗봇만 (bot | llm | route)
    python eval/run_eval.py --fresh               # 저장된 답을 지우고 처음부터

저장: eval/results/raw_bot.jsonl · raw_llm.jsonl · raw_route.jsonl (질문 하나 끝날 때마다 한 줄씩 추가,
중간에 멈춰도 다시 실행하면 이미 끝난 질문은 건너뛴다)

- 일반 LLM: 팀 그래프와 같은 gpt-4o-mini, temperature 0. 시스템 프롬프트 없이 사용자가 보낸 글 그대로.
- route: 질문 분류기(classifier_node)만 같은 질문으로 3번씩 불러 분류가 흔들리는지 본다.
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

OUT = ROOT / "eval" / "results"
MODEL = "gpt-4o-mini"
ROUTE_REPEAT = 3


def load_questions() -> list[dict]:
    """질문 36개 + 분류 확인 질문 14개. 모두 {id, set, text, ...} 형태로 맞춘다."""
    items = []
    for q in json.loads((ROOT / "eval" / "questions.json").read_text(encoding="utf-8")):
        text = f"{q['request']}\n\n```python\n{q['code'].rstrip()}\n```"
        items.append({**q, "set": "upgrade" if q["target_version"] == "1.x" else "hop", "text": text,
                      "expected_route": "migration"})
    for p in json.loads((ROOT / "eval" / "route_probes.json").read_text(encoding="utf-8")):
        items.append({**p, "set": "probe"})
    return items


def done_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return {json.loads(l)["id"] for l in path.read_text(encoding="utf-8").splitlines() if l.strip()}


def append(path: Path, rec: dict) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")


# 우리 챗봇

def slim_evidence(e: dict) -> dict:
    keep = ("evidence_id", "source", "match", "kind", "import_status", "old", "new", "title")
    return {k: e.get(k) for k in keep if e.get(k) is not None}


def run_bot(graph, item: dict) -> dict:
    from langchain_core.messages import HumanMessage

    inputs = {"question": item["text"], "messages": [HumanMessage(content=item["text"])]}
    attempts, nodes, state = [], [], None
    t0 = time.time()
    try:
        for ns, mode, data in graph.stream(inputs, stream_mode=["updates", "values"], subgraphs=True):
            if mode == "values" and not ns:
                state = data
            elif mode == "updates":
                for node, upd in data.items():
                    if node == "migration":
                        continue
                    nodes.append([node, round(time.time() - t0, 1)])
                    if node == "verifier" and upd and upd.get("verify_result"):
                        vr = upd["verify_result"]
                        attempts.append({
                            "attempt": upd.get("attempt"),
                            "passed": vr.get("passed"),
                            "errors": [{"type": e.get("type"), "message": e.get("message")} for e in vr.get("errors", [])],
                            "warnings": [e.get("type") for e in vr.get("warnings", [])],
                        })
        error = None
    except Exception as exc:  # 한 질문이 실패해도 나머지는 계속
        error = f"{type(exc).__name__}: {exc}"
    elapsed = round(time.time() - t0, 1)

    s = state or {}
    reply = None
    for m in reversed(s.get("messages", []) or []):
        if getattr(m, "type", "") == "ai":
            reply = m.content
            break
    analysis = s.get("analysis") if isinstance(s.get("analysis"), dict) else {}
    return {
        "id": item["id"], "set": item["set"], "elapsed": elapsed, "error": error,
        "classification": s.get("classification"),
        "analysis_target": (analysis.get("analysis") or analysis).get("target_version") if analysis else None,
        "target_version": s.get("target_version"),
        "old_code": s.get("old_code"), "new_code": s.get("new_code"),
        "changes": s.get("changes"), "unresolved": s.get("unresolved"),
        "rewrite_notes": s.get("rewrite_notes"), "install_packages": s.get("install_packages"),
        "evidences": [slim_evidence(e) for e in s.get("evidences", []) or []],
        "shown_evidence_ids": s.get("shown_evidence_ids"),
        "exclude_ids": s.get("exclude_ids"),
        "verify_result": s.get("verify_result"),
        "attempts": attempts, "nodes": nodes, "reply": reply,
    }


# 일반 LLM

def run_llm(llm, item: dict) -> dict:
    t0 = time.time()
    try:
        reply, error = llm.invoke(item["text"]).content, None
    except Exception as exc:
        reply, error = None, f"{type(exc).__name__}: {exc}"
    return {"id": item["id"], "set": item["set"], "elapsed": round(time.time() - t0, 1), "error": error, "reply": reply}


# 분류 일관성

def run_route(item: dict) -> dict:
    from langchain_core.messages import HumanMessage
    from src.graph.nodes.classifier_node import classifier_node

    labels = []
    for _ in range(ROUTE_REPEAT):
        try:
            out = classifier_node({"question": item["text"], "messages": [HumanMessage(content=item["text"])]})
            labels.append(out.get("classification"))
        except Exception as exc:
            labels.append(f"error: {type(exc).__name__}")
    return {"id": item["id"], "set": item["set"], "expected": item.get("expected_route"), "labels": labels}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="쉼표로 구분한 질문 id")
    ap.add_argument("--systems", default="bot,llm,route")
    ap.add_argument("--fresh", action="store_true")
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    items = load_questions()
    if args.only:
        wanted = set(args.only.split(","))
        items = [i for i in items if i["id"] in wanted]
    systems = args.systems.split(",")

    missing = [k for k in ("OPENAI_API_KEY", "CHROMA_API_KEY", "CHROMA_TENANT", "CHROMA_DATABASE") if not os.environ.get(k)]
    if missing:
        sys.exit(f".env에 값이 없습니다: {', '.join(missing)}")

    graph = llm = None
    if "bot" in systems:
        from src.graph.supervisor import supervisor
        graph = supervisor()
    if "llm" in systems:
        from langchain_openai import ChatOpenAI
        llm = ChatOpenAI(model=MODEL, temperature=0)

    for name in systems:
        path = OUT / f"raw_{name}.jsonl"
        if args.fresh and path.exists():
            path.unlink()
        skip = done_ids(path)
        todo = [i for i in items if i["id"] not in skip]
        print(f"[{name}] {len(todo)}개 실행 (이미 끝난 {len(skip)}개 건너뜀)", flush=True)
        for n, item in enumerate(todo, 1):
            if name == "bot":
                rec = run_bot(graph, item)
            elif name == "llm":
                rec = run_llm(llm, item)
            else:
                rec = run_route(item)
            rec["run_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
            append(path, rec)
            info = rec.get("labels") or (rec.get("verify_result") or {}).get("passed", rec.get("classification"))
            print(f"  [{name}] {n}/{len(todo)} {item['id']} {rec.get('elapsed', '')}s {info} {rec.get('error') or ''}", flush=True)


if __name__ == "__main__":
    main()
