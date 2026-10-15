"""평가 채점 (4번): eval/run_eval.py가 저장한 답을 읽어 두 가지 점수를 낸다. LLM을 부르지 않는다.

1. 비교 평가  우리 챗봇 vs 일반 LLM. 두 답에 '같은 잣대'(공통 채점 8항목)를 댄다.
              일반 LLM 답에는 근거 기록이 없으므로 근거 ID · 변경 기록 검사는 넣지 않는다.
2. 자체 평가  우리 팀이 프롬프트와 코드로 정한 규칙을 챗봇이 실제로 지키는지 (점검표 18항목 · 100점).

    python eval/score.py          → eval/results/summary.json, eval/results/scorecard.md

공통 채점 8항목 (목표 버전이 1.x인 질문은 전부, 버전 오가기는 1 · 4 · 5 · 6 · 8만)
    1 문법          파이썬으로 읽히는가
    2 옛 import     2번 대응표의 옛 경로가 남지 않았는가
    3 import 존재   새 import 경로가 LangChain 1.x에 실제로 있는가 (2번 버전별 도구 목록)
    4 정의 안 된 이름  원래 코드엔 없던 NameError가 생기지 않았는가
    5 결과값 보존    .run() 등 문자열을 주던 호출의 결과가 그대로인가, ['text'] 같은 잘못된 꺼내기 · 체인 키가 없는가
    6 안 쓰는 import 바꾸고 남은 import가 없는가
    7 기대 import   사람이 정한 정답 import가 들어 있는가 (전부 있어야 통과)
    8 코드 변경     실제로 코드를 바꿨는가 (원문 그대로 돌려주면 실패)
    → 8개 모두 통과해야 '공통 기준 통과'
"""
import ast
import json
import re
import statistics
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.graph.nodes.verifier_node import (  # noqa: E402
    _assigned_value, _exists_static, _names, _parse, check_chain_io_keys, check_invoke_subscript, check_legacy_imports,
    check_legacy_methods, check_return_type, check_unused_imports, collect_imports, loose_key, undefined_names,
)
from src.rag.import_map import LATEST_VERSION  # noqa: E402
from src.rag.import_map.version_resolve import normalize_version  # noqa: E402
from src.rag.retrieval.import_lookup import lookup, parse_import_paths  # noqa: E402

RES = ROOT / "eval" / "results"
FENCE = re.compile(r"```(?:python|py)?\s*\n(.*?)```", re.S)
HANGUL = re.compile(r"[가-힣]")

JUDGE_ITEMS = [
    ("syntax", "문법"), ("no_legacy_import", "옛 import 없음"), ("imports_exist", "import 실제 존재"),
    ("no_new_undefined", "정의 안 된 이름 없음"), ("output_kept", "결과값 보존"), ("no_unused_import", "남은 import 없음"),
    ("expected_imports", "정답 import 포함"), ("changed", "코드를 실제로 바꿈"),
]
HOP_SKIP = {"no_legacy_import", "imports_exist", "no_unused_import"}  # 1.x 기준 도구라 되돌리기엔 못 씀


def read(name: str) -> dict[str, dict]:
    p = RES / f"raw_{name}.jsonl"
    if not p.exists():
        return {}
    return {r["id"]: r for r in map(json.loads, p.read_text(encoding="utf-8").splitlines()) if r}


def norm(code: str | None) -> str:
    return "\n".join(l.rstrip() for l in (code or "").strip().splitlines() if l.strip())


def extract_code(reply: str | None) -> str | None:
    """일반 LLM 답에서 코드 블록. 여러 개면 import가 있는 가장 긴 것."""
    if not reply:
        return None
    blocks = [b for b in FENCE.findall(reply) if b.strip()]
    if not blocks:
        return reply if _parse(reply) is not None else None
    with_import = [b for b in blocks if "import" in b]
    return max(with_import or blocks, key=len)


# 공통 채점

def judge(q: dict, new_code: str | None) -> dict:
    old = q["code"]
    hop = q["target_version"] != "1.x"
    res = {k: False for k, _ in JUDGE_ITEMS}
    res["detail"] = []
    if not new_code:
        res["detail"].append("코드 없음")
        res["pass"] = False
        return res
    tree, old_tree = _parse(new_code), _parse(old)
    res["changed"] = norm(new_code) != norm(old)
    if tree is None:
        res["detail"].append("문법 오류")
        res["pass"] = False
        return res
    res["syntax"] = True
    imports = collect_imports(tree)

    e4, _, _ = check_legacy_imports(imports)
    res["no_legacy_import"] = not e4
    missing = [p for p, _, _ in imports if _exists_static(p) is False]
    res["imports_exist"] = not missing
    old_undef = set(undefined_names(old_tree)) if old_tree is not None else set()
    new_undef = sorted(set(undefined_names(tree)) - old_undef)
    res["no_new_undefined"] = not new_undef
    e_out = check_return_type(old, old_tree, tree) + check_invoke_subscript(tree) + check_chain_io_keys(tree)
    sub = [] if e_out else lcel_subscript(tree)
    res["output_kept"] = not e_out and not sub
    e7, _ = check_unused_imports(tree, _names(tree), _names(old_tree))
    res["no_unused_import"] = not e7

    have = {p for p, _, _ in imports}
    have_loose = {loose_key(p) for p in have}
    want = [p for line in q.get("expected_imports", []) for p in parse_import_paths(line)]
    lacking = [p for p in want if p not in have and loose_key(p) not in have_loose]
    res["expected_imports"] = not lacking
    res["legacy_methods"] = len(check_legacy_methods(new_code))

    for k, msg in (("no_legacy_import", [e["path"] for e in e4]), ("imports_exist", missing),
                   ("no_new_undefined", new_undef), ("output_kept", [e["type"] for e in e_out] + sub),
                   ("no_unused_import", [e["path"] for e in e7]), ("expected_imports", lacking)):
        if msg and not (hop and k in HOP_SKIP):
            res["detail"].append(f"{k}: {', '.join(map(str, msg))}")
    keys = [k for k, _ in JUDGE_ITEMS if not (hop and k in HOP_SKIP)]
    res["pass"] = all(res[k] for k in keys)
    res["run_pass"] = all(res[k] for k in keys if k != "expected_imports")  # 정답 import 빼고: 실행은 되는 코드인가
    res["applicable"] = keys
    return res


def lcel_subscript(tree: ast.AST) -> list[str]:
    """| 로 만든 체인의 invoke 결과를 ['text']처럼 꺼내는 줄 (실행하면 TypeError).
    verifier 10번보다 넓게 본다: r = chain.invoke(...) 뒤 r['text'], 체인 끝이 ChatOpenAI(...) 직접 호출인 경우도."""
    def is_pipe(expr):
        if isinstance(expr, ast.Name):
            expr = _assigned_value(tree, expr.id)
        return isinstance(expr, ast.BinOp) and isinstance(expr.op, ast.BitOr)

    def lcel_invoke(node):
        node = node.value if isinstance(node, ast.Await) else node
        return (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr in ("invoke", "ainvoke") and is_pipe(node.func.value))

    results = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name) and lcel_invoke(n.value):
            results.add(n.targets[0].id)
    found = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Subscript) and isinstance(n.slice, ast.Constant) and isinstance(n.slice.value, str):
            if lcel_invoke(n.value) or (isinstance(n.value, ast.Name) and n.value.id in results):
                found.append(f"line {n.lineno} [{n.slice.value!r}]")
    return found


def rate(values) -> float | None:
    values = list(values)
    return round(sum(map(bool, values)) / len(values), 4) if values else None


# 자체 평가 점검표: (id, 영역, 항목, 팀이 정한 근거, 목표, 배점)
CHECKLIST = [
    ("A1", "질문 분류", "코드 변환 요청을 migration으로 분류", "classifier 프롬프트 · 분류 규칙 1, 2", 1.00, 6),
    ("A2", "질문 분류", "지식 · 일반 · 지시문 섞인 질문을 맞게 분류", "classifier 프롬프트 · 분류 규칙 2~6", 0.90, 5),
    ("A3", "질문 분류", "같은 질문을 3번 보내도 분류가 같음", "라우터는 출력이 정확히 하나 (프롬프트 1행)", 1.00, 4),
    ("B1", "분석", "질문에서 코드 원문을 그대로 꺼냄", "analyzer 프롬프트 · old_code 규칙", 0.95, 5),
    ("B2", "분석", "질문에 적은 목표 버전을 맞게 읽음 (없으면 최신)", "analyzer target_version 규칙 · 2번 normalize_version", 1.00, 5),
    ("C1", "근거 검색", "근거를 1개 이상 찾음", "retriever: 대응표 정확 매칭 + 하이브리드 검색", 1.00, 4),
    ("C2", "근거 검색", "대응표에 있는 옛 import는 근거로 꼭 가져옴", "retriever · import_lookup", 0.95, 6),
    ("D1", "고쳐 쓰기", "바꾼 줄마다 보여 준 근거 ID만 붙임", "rewriter 원칙 2 · verifier 2번", 0.95, 6),
    ("D2", "고쳐 쓰기", "기록 없이 바뀐 줄이 없음 (환각 없음)", "rewriter 원칙 1, 규칙 6 · verifier 3번", 0.95, 6),
    ("D3", "고쳐 쓰기", "결과값 · 출력 꺼내기 · 체인 키를 지킴", "rewriter 규칙 3 · verifier 8, 10, 11번", 0.95, 5),
    ("D4", "고쳐 쓰기", "새로 쓴 이름은 import도 추가", "rewriter 규칙 4 · verifier 9번", 0.95, 4),
    ("D5", "고쳐 쓰기", "안 쓰게 된 import는 지움", "rewriter 규칙 5 · verifier 7번", 0.95, 4),
    ("E1", "검증 · 재시도", "최종 검증 통과", "verifier 11가지 · 최대 3회", 0.80, 10),
    ("E2", "검증 · 재시도", "1회차에 검증 통과", "-", 0.60, 5),
    ("E3", "검증 · 재시도", "1회차 실패 → 다시 시도해서 통과", "실패 이유 피드백 + 틀린 근거 제외", 0.50, 5),
    ("E4", "검증 · 재시도", "검증 시도가 최대 3회를 넘지 않음", "MAX_ATTEMPTS = 3", 1.00, 3),
    ("E5", "검증 · 재시도", "검증 통과한 코드는 공통 채점도 통과", "검사기 신뢰도", 1.00, 7),
    ("F1", "답변 규칙", "LangChain 질문 답에 '출처' 표기", "search 프롬프트 · 답변 형식", 0.90, 3),
    ("F2", "답변 규칙", "한국어로 답함", "search · general 프롬프트", 1.00, 2),
    ("G1", "안정성 · 속도", "오류 없이 답을 돌려줌", "-", 1.00, 3),
    ("G2", "안정성 · 속도", "코드 변환 60초 안에 끝남", "화면 기다림 한도 (4번)", 0.90, 2),
]


def self_eval(questions: dict, bot: dict, route: dict, judged_bot: dict) -> list[dict]:
    mig = [questions[i] for i in questions if questions[i]["set"] != "probe" and i in bot]
    probes = [questions[i] for i in questions if questions[i]["set"] == "probe" and i in bot]
    probe_mig = [p for p in probes if p["expected_route"] == "migration"]
    probe_other = [p for p in probes if p["expected_route"] != "migration"]
    ran = [bot[q["id"]] for q in mig if bot[q["id"]].get("classification") == "migration"]
    fails = defaultdict(list)

    def final_types(r):
        return {e["type"] for e in (r.get("verify_result") or {}).get("errors", [])}

    def item(cid, values, ids, note=""):
        values = list(values)
        for ok, i in zip(values, ids):
            if not ok:
                fails[cid].append(i)
        return values, note

    out = {}
    out["A1"] = item("A1", [bot[q["id"]].get("classification") == "migration" for q in mig + probe_mig],
                     [q["id"] for q in mig + probe_mig])
    out["A2"] = item("A2", [bot[p["id"]].get("classification") == p["expected_route"] for p in probe_other],
                     [p["id"] for p in probe_other])
    out["A3"] = item("A3", [len(set(r["labels"])) == 1 for r in route.values()], list(route))

    def b1(q):
        return norm(bot[q["id"]].get("old_code")) == norm(q["code"])

    def expected_target(q):
        return LATEST_VERSION if q["target_version"] == "1.x" else normalize_version(q["target_version"])

    routed = [q for q in mig if bot[q["id"]].get("classification") == "migration"]  # 분류가 틀린 질문은 A1에서만 감점
    out["B1"] = item("B1", [b1(q) for q in routed], [q["id"] for q in routed])
    out["B2"] = item("B2", [bot[q["id"]].get("target_version") == expected_target(q) for q in routed], [q["id"] for q in routed])
    out["C1"] = item("C1", [bool(bot[q["id"]].get("evidences")) for q in routed], [q["id"] for q in routed])

    c2_vals, c2_ids = [], []
    for q in routed:
        tree = _parse(q["code"])
        olds = [p for p, _, _ in collect_imports(tree)] if tree is not None else []
        mapped = [p for p in olds if lookup(p) is not None]
        got = {e.get("old") for e in bot[q["id"]].get("evidences", []) if e.get("source") == "import_map"}
        got |= {(e.get("match") or "") for e in bot[q["id"]].get("evidences", [])}
        for p in mapped:
            c2_vals.append(p in got)
            c2_ids.append(f"{q['id']}:{p}")
    out["C2"] = item("C2", c2_vals, c2_ids)

    rule = {
        "D1": {"missing_evidence", "evidence_not_shown", "unknown_evidence_id"},
        "D2": {"unrecorded_change", "old_line_mismatch", "change_not_applied"},
        "D3": {"return_type_changed", "invoke_output_subscript", "chain_io_key"},
        "D4": {"undefined_name"},
        "D5": {"unused_import"},
    }
    for cid, types in rule.items():
        out[cid] = item(cid, [not (final_types(r) & types) for r in ran], [r["id"] for r in ran])

    passed = [bool((r.get("verify_result") or {}).get("passed")) for r in ran]
    out["E1"] = item("E1", passed, [r["id"] for r in ran])
    first = [bool(r["attempts"] and r["attempts"][0]["passed"]) for r in ran]
    out["E2"] = item("E2", first, [r["id"] for r in ran])
    retried = [r for r, f in zip(ran, first) if not f and r["attempts"]]
    out["E3"] = item("E3", [bool(r["verify_result"]["passed"]) for r in retried], [r["id"] for r in retried])
    out["E4"] = item("E4", [len(r["attempts"]) <= 3 for r in ran], [r["id"] for r in ran])
    ok_bot = [r for r in ran if (r.get("verify_result") or {}).get("passed")]
    out["E5"] = item("E5", [judged_bot[r["id"]]["pass"] for r in ok_bot], [r["id"] for r in ok_bot])

    search = [bot[p["id"]] for p in probes if bot[p["id"]].get("classification") == "search"]
    out["F1"] = item("F1", ["출처" in (r.get("reply") or "") for r in search], [r["id"] for r in search])
    talk = [bot[p["id"]] for p in probes if bot[p["id"]].get("classification") in ("search", "general")]
    out["F2"] = item("F2", [len(HANGUL.findall(r.get("reply") or "")) >= 5 for r in talk], [r["id"] for r in talk])
    allrec = list(bot.values())
    out["G1"] = item("G1", [not r.get("error") for r in allrec], [r["id"] for r in allrec])
    out["G2"] = item("G2", [r["elapsed"] <= 60 for r in ran], [r["id"] for r in ran])

    rows = []
    for cid, area, name, basis, target, weight in CHECKLIST:
        values, _ = out[cid]
        r = rate(values)
        rows.append({"id": cid, "area": area, "item": name, "basis": basis, "target": target, "weight": weight,
                     "n": len(values), "ok": sum(map(bool, values)), "rate": r,
                     "score": round(weight * (r if r is not None else 0), 1),
                     "met": r is not None and r >= target, "fails": fails[cid]})
    return rows


def compare(questions: dict, bot: dict, llm: dict, judged_bot: dict, judged_llm: dict) -> dict:
    out = {}
    for group in ("upgrade", "hop"):
        ids = [i for i, q in questions.items() if q["set"] == group and i in bot and i in llm]
        if not ids:
            continue
        g = {"n": len(ids)}
        for name, judged, raw in (("bot", judged_bot, bot), ("llm", judged_llm, llm)):
            items = {}
            for k, label in JUDGE_ITEMS:
                vals = [judged[i][k] for i in ids if k in judged[i].get("applicable", [k])]
                items[k] = {"label": label, "rate": rate(vals), "n": len(vals)}
            times = [raw[i]["elapsed"] for i in ids]
            g[name] = {
                "pass": rate(judged[i]["pass"] for i in ids),
                "run_pass": rate(judged[i].get("run_pass") for i in ids),
                "items": items,
                "median_sec": round(statistics.median(times), 1),
                "legacy_methods": sum(judged[i].get("legacy_methods", 0) for i in ids),
                "by_difficulty": {d: rate(judged[i]["pass"] for i in ids if questions[i]["difficulty"] == d)
                                  for d in sorted({questions[i]["difficulty"] for i in ids})},
                "by_type": {t: rate(judged[i]["pass"] for i in ids if questions[i]["type"] == t)
                            for t in sorted({questions[i]["type"] for i in ids})},
            }
        verified = [i for i in ids if (bot[i].get("verify_result") or {}).get("passed")]
        g["bot"]["verified"] = rate((bot[i].get("verify_result") or {}).get("passed") for i in ids)
        g["bot"]["verified_and_judged"] = rate(judged_bot[i]["pass"] for i in verified) if verified else None
        g["bot"]["misrouted"] = [i for i in ids if bot[i].get("classification") != "migration"]
        g["bot"]["flagged_failures"] = sum(1 for i in ids if not judged_bot[i]["pass"]
                                          and not (bot[i].get("verify_result") or {}).get("passed"))
        g["bot"]["silent_failures"] = sum(1 for i in ids if not judged_bot[i]["pass"]
                                         and (bot[i].get("verify_result") or {}).get("passed"))
        g["per_question"] = [{
            "id": i, "type": questions[i]["type"], "difficulty": questions[i]["difficulty"],
            "bot_pass": judged_bot[i]["pass"], "llm_pass": judged_llm[i]["pass"],
            "bot_verified": bool((bot[i].get("verify_result") or {}).get("passed")),
            "attempts": len(bot[i].get("attempts") or []),
            "bot_detail": judged_bot[i]["detail"], "llm_detail": judged_llm[i]["detail"],
            "bot_sec": bot[i]["elapsed"], "llm_sec": llm[i]["elapsed"],
        } for i in ids]
        out[group] = g
    return out


def main() -> None:
    qs = json.loads((ROOT / "eval" / "questions.json").read_text(encoding="utf-8"))
    probes = json.loads((ROOT / "eval" / "route_probes.json").read_text(encoding="utf-8"))
    questions = {q["id"]: {**q, "set": "upgrade" if q["target_version"] == "1.x" else "hop", "expected_route": "migration"}
                 for q in qs}
    questions.update({p["id"]: {**p, "set": "probe"} for p in probes})
    bot, llm, route = read("bot"), read("llm"), read("route")

    # 분류가 틀려 검증 없이 글로 답한 경우에도 사용자가 받은 코드(답 속 코드 블록)로 채점한다
    judged_bot = {i: judge(questions[i], r.get("new_code") or extract_code(r.get("reply")))
                  for i, r in bot.items() if questions[i]["set"] != "probe"}
    judged_llm = {i: judge(questions[i], extract_code(r.get("reply"))) for i, r in llm.items()
                  if questions[i]["set"] != "probe"}

    rows = self_eval(questions, bot, route, judged_bot)
    total = round(sum(r["score"] for r in rows), 1)
    grade = "A" if total >= 90 else "B" if total >= 80 else "C" if total >= 70 else "D"
    summary = {
        "run_at": max((r.get("run_at", "") for r in bot.values()), default=""),
        "model": "gpt-4o-mini",
        "compare": compare(questions, bot, llm, judged_bot, judged_llm),
        "self_eval": {"total": total, "grade": grade, "rows": rows,
                      "met": sum(r["met"] for r in rows), "items": len(rows)},
        "attempt_curve": attempt_curve(questions, bot),
    }
    (RES / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (RES / "scorecard.md").write_text(scorecard(summary), encoding="utf-8")
    print(scorecard(summary))


def attempt_curve(questions: dict, bot: dict) -> dict:
    """1.x로 올리기: n회차까지 검증 통과한 누적 비율."""
    ids = [i for i, q in questions.items() if q["set"] == "upgrade" and i in bot]
    curve = {}
    for n in (1, 2, 3):
        curve[n] = rate(any(a["passed"] for a in bot[i]["attempts"][:n]) for i in ids) if ids else None
    return curve


def pct(x) -> str:
    return "-" if x is None else f"{x * 100:.0f}%"


def scorecard(s: dict) -> str:
    se = s["self_eval"]
    lines = [f"# 평가 결과 ({s['run_at']} · {s['model']})", ""]
    for group, title in (("upgrade", "1.x로 올리기"), ("hop", "버전 오가기")):
        g = s["compare"].get(group)
        if not g:
            continue
        lines += [f"## 비교 평가 · {title} ({g['n']}개)", "", "| 항목 | 우리 챗봇 | 일반 LLM |", "|---|---|---|",
                  f"| **공통 기준 통과** | **{pct(g['bot']['pass'])}** | **{pct(g['llm']['pass'])}** |",
                  f"| 실행 기준 통과 (정답 import 제외) | {pct(g['bot']['run_pass'])} | {pct(g['llm']['run_pass'])} |"]
        for k, v in g["bot"]["items"].items():
            if v["n"]:
                lines.append(f"| {v['label']} | {pct(v['rate'])} | {pct(g['llm']['items'][k]['rate'])} |")
        lines += [f"| 응답 시간 (중앙값) | {g['bot']['median_sec']}초 | {g['llm']['median_sec']}초 |",
                  f"| 검증 통과 (챗봇 자체 판정) | {pct(g['bot']['verified'])} | 없음 |", ""]
    lines += [f"## 자체 평가 · {se['total']}점 / 100 ({se['grade']}) · 목표 달성 {se['met']}/{se['items']}", "",
              "| | 항목 | 결과 | 목표 | 점수 |", "|---|---|---|---|---|"]
    for r in se["rows"]:
        mark = "✅" if r["met"] else "❌"
        lines.append(f"| {r['id']} | {r['item']} | {mark} {pct(r['rate'])} ({r['ok']}/{r['n']}) | {pct(r['target'])} | {r['score']}/{r['weight']} |")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
