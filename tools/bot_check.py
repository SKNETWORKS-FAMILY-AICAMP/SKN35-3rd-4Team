"""자동 점검 봇: 버전마다 옛 코드를 넣어 화면 흐름(시작 → 확인 → 채팅)을 끝까지 돌려 본다.

    python tools/bot_check.py

각 경우마다 확인하는 것: 오류 없음, 결과 배지, 버전 안내(자동 감지 · 고른 버전과 다름)가 기대와 맞는지.
2번 대응표(data/processed/import_map.jsonl)가 있으면 실제 데이터로, 없으면 예시로 돈다.
"""

import sys
from pathlib import Path

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
AUTO = "모르겠어요 (자동 감지)"
COMMON = "from langchain.chat_models import ChatOpenAI\nfrom langchain.chains import LLMChain\n"
CODES = {
    "0.0.300 전용": "from langchain.agents import create_csv_agent\n" + COMMON,
    "0.0.354 전용": "from langchain.vectorstores import BESVectorStore\n" + COMMON,
    "0.1.20 이후": "from langchain.agents import create_tool_calling_agent\n" + COMMON,
    "0.2.17 이후": "from langchain.memory import ConversationVectorStoreTokenBufferMemory\n" + COMMON,
    "흔한 코드": COMMON + "from langchain.prompts import PromptTemplate\n",
    "LangChain 아님": "import numpy as np\nprint(np.zeros(3))\n",
}
# (고를 버전, 코드 이름, 기대: 안내 문구에 들어갈 말 / None 이면 안내 없음)
CASES = [
    ("0.0.300", "0.0.300 전용", None),
    ("0.0.354", "0.0.354 전용", None),
    ("0.1.20", "0.1.20 이후", None),
    ("0.2.17", "0.2.17 이후", None),
    ("0.3.30", "0.2.17 이후", None),
    ("0.0.300", "흔한 코드", None),
    ("0.3.30", "흔한 코드", None),
    ("0.0.300", "0.2.17 이후", "고르신 버전은 0.0.300"),
    ("0.3.30", "0.0.300 전용", "고르신 버전은 0.3.30"),
    (AUTO, "0.0.300 전용", "0.0.300** 시기"),
    (AUTO, "0.0.354 전용", "0.0.354** 시기"),
    (AUTO, "0.1.20 이후", "0.1.20 ~ 0.3.30"),
    (AUTO, "0.2.17 이후", "0.2.17 ~ 0.3.30"),
    (AUTO, "흔한 코드", "0.0.300 ~ 0.3.30"),
    (AUTO, "LangChain 아님", None),
]


def run_case(pick: str, code_name: str) -> tuple[list, str, list[str]]:
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60)
    at.run()
    at.button_group[0].set_value(pick).run()
    [b for b in at.button if "다음" in b.label][0].click().run()
    [b for b in at.button if "확인하고" in b.label][0].click().run()
    at.chat_input[0].set_value(CODES[code_name]).run()
    # 채팅 답변만 집는다 (사이드바의 "옛 버전 → 목표" 글자는 제외)
    reply = next((m.value for m in reversed(at.markdown)
                  if any(k in m.value for k in ("고쳤어요", "찾았지만", "찾지 못했"))), "")
    badges = [m.value for m in at.markdown if "badge[" in m.value and ("검증" in m.value or "변환" in m.value)]
    warn = [w.body for w in at.warning]
    return list(at.exception), reply + " " + " ".join(warn), badges


def main() -> int:
    data = (ROOT / "data" / "processed" / "import_map.jsonl").exists()
    print(f"데이터: {'2번 대응표 (실제)' if data else '예시'}\n")
    bad = 0
    for pick, code_name, expect in CASES:
        errors, reply, badges = run_case(pick, code_name)
        has_note = "시기" in reply or "고르신 버전" in reply
        if errors:
            ok, why = False, f"오류: {errors}"
        elif expect is None:
            ok = not ("고르신 버전" in reply) and (pick == AUTO or not has_note)
            why = "안내 없음" if ok else f"예상하지 못한 안내: {reply[:80]}"
        else:
            ok = expect in reply
            why = f"안내 확인: {expect}" if ok else f"기대 '{expect}' 없음 → {reply[:90]}"
        bad += not ok
        badge = badges[0].split("]")[0].split(":")[-1].strip() if badges else "(배지 없음)"
        print(f"[{'OK ' if ok else 'BAD'}] 고른 버전 {pick:<14} 코드 {code_name:<12} | {badge:<18} | {why}")
    print(f"\n{len(CASES) - bad}/{len(CASES)} 통과")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
