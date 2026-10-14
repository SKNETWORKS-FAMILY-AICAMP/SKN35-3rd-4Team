"""실무형 질문 35개 검사.

    python eval/check_questions.py --py <LangChain 1.x 가 깔린 python> [--map data/processed/import_map.jsonl]

질문마다 확인하는 것
  1. 옛 코드가 파이썬 문법으로 읽히는가
  2. 옛 코드가 1.x 환경에서 실제로 깨지는가 (import 하나라도 실패)
  3. 기대 결과(expected_imports)가 1.x 환경에서 전부 import 되는가
  4. (--map) 옛 코드의 LangChain import 경로가 2번 대응표에 있는가 (없는 것은 목록만 보여 줌)
  (--symbols) 1.x 환경에 패키지가 없어 import 가 안 되면, 2번의 버전별 도구 목록(data/raw/symbols)으로 경로를 확인
  목표가 1.x 가 아닌 질문(버전 오가기)은 2번 도구 목록으로 정적 확인: 옛 경로 중 하나라도 목표 버전에 없는가,
  기대 경로가 목표 버전에 모두 있는가 (--symbols 필요)
"""

import argparse
import ast
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent


def import_lines(code: str) -> list[str]:
    tree = ast.parse(code)
    return [ast.unparse(n) for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))
            and (getattr(n, "module", None) or n.names[0].name).startswith("langchain")]


def old_paths(code: str) -> list[str]:
    out = []
    for n in ast.walk(ast.parse(code)):
        if isinstance(n, ast.ImportFrom) and n.module and n.module.startswith("langchain"):
            out += [f"{n.module}.{a.name}" for a in n.names]
    return out


def try_imports(py: str, lines: list[str]) -> dict[str, str | None]:
    """줄마다 따로 import 해 보고 실패 이유(성공이면 None)."""
    script = ("import json,sys,warnings\nwarnings.filterwarnings('ignore')\nres={}\n"
              "for l in json.loads(sys.argv[1]):\n"
              "    try:\n        exec(l, {})\n        res[l]=None\n"
              "    except Exception as e:\n        res[l]=type(e).__name__+': '+str(e)[:80]\n"
              "print(json.dumps(res))")
    out = subprocess.run([py, "-I", "-c", script, json.dumps(lines)], capture_output=True, text=True,
                         encoding="utf-8", timeout=300)
    return json.loads(out.stdout.strip().splitlines()[-1])


def check_static(q: dict) -> int:
    """목표가 0.x 인 질문: 2번 도구 목록으로 확인."""
    from src.ui.extras import version_map as vm
    tgt = q["target_version"]
    problems = []
    if not vm.available():
        problems.append("--symbols 가 없어서 확인 못 함")
    else:
        olds = old_paths(q["code"])
        if all(vm.has(p, tgt) for p in olds):
            problems.append(f"옛 코드가 {tgt}에서 바꿀 곳이 없음")
        for line in q["expected_imports"]:
            node = ast.parse(line).body[0]
            for x in node.names:
                if not vm.has(f"{node.module}.{x.name}", tgt):
                    problems.append(f"기대 경로가 {tgt}에 없음: {node.module}.{x.name}")
    print(f"[{'OK ' if not problems else 'BAD'}] {q['id']} {q['type']:<12} {q['difficulty']:<3}"
          f" · {q['source_version']} → {tgt} (2번 도구 목록으로 확인)")
    for p in problems:
        print("      -", p)
    return bool(problems)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--py", required=True)
    ap.add_argument("--map", help="2번 import_map.jsonl")
    ap.add_argument("--symbols", help="2번 data/raw/symbols 폴더 (패키지가 없을 때 경로 확인용)")
    a = ap.parse_args()
    qs = json.loads((HERE / "questions.json").read_text(encoding="utf-8"))
    known = None
    if a.map:
        known = {json.loads(l)["old"] for l in Path(a.map).read_text(encoding="utf-8").splitlines() if l.strip()}

    if a.symbols:
        import os
        os.environ["MIGRATION_SYMBOLS_DIR"] = a.symbols
        sys.path.insert(0, str(HERE.parent))
    other = [q for q in qs if q.get("target_version", "1.x") != "1.x"]
    qs_new = [q for q in qs if q.get("target_version", "1.x") == "1.x"]
    all_lines = sorted({l for q in qs_new for l in import_lines(q["code"]) + q["expected_imports"]})
    res = try_imports(a.py, all_lines)
    dumped = set()
    if a.symbols:
        for f in Path(a.symbols).glob("*.jsonl"):
            dumped |= {json.loads(l)["path"] for l in f.read_text(encoding="utf-8").splitlines() if l.strip()}
    expected = {l for q in qs_new for l in q["expected_imports"]}
    for line, err in list(res.items()):
        # 기대 결과(1.x import)에만 쓴다. 도구 목록에는 옛 버전 목록도 있어서 옛 코드에 쓰면 안 됨
        if line in expected and err and err.startswith("ModuleNotFoundError") and dumped:
            node = ast.parse(line).body[0]
            if isinstance(node, ast.ImportFrom) and all(f"{node.module}.{x.name}" in dumped for x in node.names):
                res[line] = None   # 패키지는 없지만 2번 도구 목록에 경로가 있음
    bad = 0
    for q in qs:
        if q in other:
            bad += check_static(q)
            continue
        problems = []
        olds = import_lines(q["code"])
        if all(res[l] is None for l in olds):
            problems.append("옛 코드가 1.x에서 깨지지 않음")
        for l in q["expected_imports"]:
            if res[l] is not None:
                problems.append(f"기대 import 실패: {l} ({res[l]})")
        missing = [p for p in old_paths(q["code"]) if known is not None and p not in known]
        note = f" · 대응표에 없음: {', '.join(p.rsplit('.', 1)[1] for p in missing)}" if missing else ""
        bad += bool(problems)
        print(f"[{'OK ' if not problems else 'BAD'}] {q['id']} {q['type']:<12} {q['difficulty']:<3}{note}")
        for p in problems:
            print("      -", p)
    print(f"\n유형: {dict(Counter(q['type'] for q in qs))}")
    print(f"난이도: {dict(Counter(q['difficulty'] for q in qs))}")
    print(f"{len(qs) - bad}/{len(qs)} 통과")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
