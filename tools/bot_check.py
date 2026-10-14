"""자동 점검 봇: 로그인 → 버전 선택 → 채팅 → 대화 기록 다시 불러오기까지 화면 흐름을 끝까지 돌려 본다.

    python tools/bot_check.py

임시 SQLite 파일로 돌리므로 실제 TiDB 에는 아무것도 쓰지 않는다.
2번 대응표(data/processed/import_map.jsonl)가 있으면 실제 데이터로, 없으면 예시로 돈다.
"""

import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB_FILE = Path(tempfile.gettempdir()) / "migration_bot_check.db"
DB_FILE.unlink(missing_ok=True)
os.environ["MIGRATION_DB_URL"] = f"sqlite:///{DB_FILE.as_posix()}"
os.environ.pop("OPENAI_API_KEY", None)          # LLM 호출 없이 점검
os.environ["MIGRATION_NO_GRAPH"] = "1"          # 팀 그래프(유료 API) 없이 화면만 점검

from streamlit.testing.v1 import AppTest  # noqa: E402

sys.path.insert(0, str(ROOT))
from src.ui import db  # noqa: E402

AUTO = "자동 감지"
COMMON = "from langchain.chat_models import ChatOpenAI\nfrom langchain.chains import LLMChain\n"
CODES = {
    "0.0.300 전용": "from langchain.agents import create_csv_agent\n" + COMMON,
    "0.0.354 전용": "from langchain.vectorstores import BESVectorStore\n" + COMMON,
    "0.1.20 이후": "from langchain.agents import create_tool_calling_agent\n" + COMMON,
    "0.2.17 이후": "from langchain.memory import ConversationVectorStoreTokenBufferMemory\n" + COMMON,
    "흔한 코드": COMMON + "from langchain.prompts import PromptTemplate\n",
}
VERSION_CASES = [  # (옛 버전 선택, 코드, 기대 안내 / None 이면 안내 없음)
    ("0.0.300", "0.0.300 전용", None), ("0.0.354", "0.0.354 전용", None), ("0.1.20", "0.1.20 이후", None),
    ("0.2.17", "0.2.17 이후", None), ("0.3.30", "0.2.17 이후", None), ("0.3.30", "흔한 코드", None),
    ("0.0.300", "0.2.17 이후", "고르신 버전은 0.0.300"), ("0.3.30", "0.0.300 전용", "고르신 버전은 0.3.30"),
    (AUTO, "0.0.300 전용", "0.0.300** 시기"), (AUTO, "0.0.354 전용", "0.0.354** 시기"),
    (AUTO, "0.1.20 이후", "0.1.20 ~ 0.3.30"), (AUTO, "0.2.17 이후", "0.2.17 ~ 0.3.30"),
    (AUTO, "흔한 코드", "0.0.300 ~ 0.3.30"),
]
results = []


def check(name: str, ok: bool, why: str = "") -> None:
    results.append(ok)
    print(f"[{'OK ' if ok else 'BAD'}] {name}" + (f" · {why}" if why else ""))


def app() -> AppTest:
    at = AppTest.from_file(str(ROOT / "streamlit_app.py"), default_timeout=60)
    at.run()
    return at


def signup(at: AppTest, name: str) -> AppTest:
    at.text_input[0].set_value(name)
    at.button[0].click().run()      # 첫 번째 폼 버튼 = 시작하기
    return at


def login(at: AppTest, name: str) -> AppTest:
    at.text_input[1].set_value(name)
    at.button[1].click().run()
    return at


def last_reply(at: AppTest) -> str:
    return next((m.value for m in reversed(at.markdown)
                 if any(k in m.value for k in ("고쳤어요", "찾았지만", "찾지 못했", "키를 설정", "바꿀 import가 없어요",
                                               "도구 목록", "그대로 두었어요"))), "")


def main() -> int:
    data = (ROOT / "data" / "processed" / "import_map.jsonl").exists()
    print(f"데이터: {'2번 대응표 (실제)' if data else '예시'} · 기록: 임시 SQLite\n")

    # 1. 가입 · 중복 금지 · 로그인
    at = signup(app(), "봇사용자")
    check("가입", not at.exception and any("봇사용자" in m.value for m in at.sidebar.markdown))
    dup = signup(app(), "봇사용자")
    check("같은 아이디 가입 막기 (중복 검사)", any("이미 있는 아이디" in e.value for e in dup.error))
    bad = signup(app(), "a")
    check("아이디 규칙 (2~20자)", any("2~20자" in e.value for e in bad.error))
    nobody = login(app(), "없는사람")
    check("없는 아이디 로그인 막기", any("없어요" in e.value for e in nobody.error))

    # 1-1. 세션: 한 대화 안에서 질문 여러 개 → 대화 1개, "새 대화" → 세션 하나 더
    at = signup(app(), "세션봇")
    for text in ("from langchain.chat_models import ChatOpenAI\n", "from langchain.prompts import PromptTemplate\n",
                 "from langchain.chains import LLMChain\n"):
        at.chat_input[0].set_value(text).run()
    sessions = [b for b in at.sidebar.button if b.key and b.key.startswith("sess_")]
    rows = db.get_history(at.session_state["session_id"], "세션봇")
    check("한 세션에 질문 3개 이어서 저장 (질문+답 = 한 행)", len(sessions) == 1 and len(rows) == 3 and
          all(r["answer"] for r in rows), f"세션 {len(sessions)}개 · chat_history {len(rows)}행")
    [b for b in at.sidebar.button if "새 대화" in b.label][0].click().run()
    at.chat_input[0].set_value("from langchain.llms import OpenAI\n").run()
    sessions = [b for b in at.sidebar.button if b.key and b.key.startswith("sess_")]
    check("새 대화 → 새 세션", len(sessions) == 2, f"세션 {len(sessions)}개")

    # 2. 버전 선택 × 코드
    for pick, code_name, expect in VERSION_CASES:
        at = login(app(), "봇사용자")
        at.selectbox(key="source_pick").set_value(pick).run()
        at.chat_input[0].set_value(CODES[code_name]).run()
        reply = last_reply(at)
        if at.exception:
            check(f"{pick} + {code_name}", False, f"오류 {at.exception}")
        elif expect is None:
            check(f"{pick} + {code_name}", "고르신 버전" not in reply and (pick == AUTO or "시기" not in reply), "안내 없음")
        else:
            check(f"{pick} + {code_name}", expect in reply, f"안내: {expect}" if expect in reply else reply[:80])

    # 2-1. 버전 오가기 (변환할 버전 선택)
    qs = {q["id"]: q for q in json.loads((ROOT / "eval" / "questions.json").read_text(encoding="utf-8"))}
    hops = [("1.x", "0.2.17", "q31", "되돌리면서"), (AUTO, "0.3.30", "q32", "그대로 두었어요"),
            (AUTO, "0.2.17", "q31", "LangChain 1.x** 코드로")]
    for src, tgt, qid, expect in hops:
        at = login(app(), "봇사용자")
        at.selectbox(key="source_pick").set_value(src).run()
        at.selectbox(key="target_pick").set_value(tgt).run()
        at.chat_input[0].set_value(qs[qid]["code"]).run()
        reply = " ".join(m.value for m in at.markdown)
        ok = not at.exception and (expect in reply or not data)
        check(f"버전 오가기 {src} → {tgt} ({qid})", ok, f"안내: {expect}" if expect in reply else
              ("예시 데이터라 건너뜀" if not data else reply[-120:]))
    at = login(app(), "봇사용자")
    at.selectbox(key="source_pick").set_value("0.2.17").run()
    at.selectbox(key="target_pick").set_value("0.2.17").run()
    check("같은 버전 고르면 안내", any("버전이 같아요" in w.value for w in at.warning))

    # 2-2. 질문 36개 전부 화면에서 실행 (오류 없이 답이 나오는가)
    failed = []
    for q in qs.values():
        at = login(app(), "봇사용자")
        src = q["source_version"] if q["source_version"] in at.selectbox(key="source_pick").options else AUTO
        at.selectbox(key="source_pick").set_value(src).run()
        at.selectbox(key="target_pick").set_value(q["target_version"]).run()
        at.chat_input[0].set_value(q["request"] + "\n\n```python\n" + q["code"] + "```").run()
        if at.exception or not last_reply(at):
            failed.append(q["id"])
    check(f"질문 {len(qs)}개 전부 실행", not failed, f"실패: {failed}" if failed else "오류 없음")

    # 3. 코드 붙여 넣기 → 결과 패널
    at = login(app(), "봇사용자")
    at.chat_input[0].set_value(COMMON).run()
    check("코드 붙여 넣기 → 결과 패널", not at.exception and any("검증" in m.value for m in at.markdown))
    at = login(app(), "봇사용자")
    at.selectbox(key="example_pick").set_value("q10").run()
    at.button(key="send_example").click().run()
    picked = (at.selectbox(key="source_pick").value, at.selectbox(key="target_pick").value)
    check("확인용 예제 30개 · 보내기 (예제 버전으로 맞춤)",
          len(at.selectbox(key="example_pick").options) == 30 and picked == ("0.1.20", "1.x") and bool(last_reply(at)),
          f"{len(at.selectbox(key='example_pick').options)}개 · {picked[0]} → {picked[1]}")

    # 4. 코드 없는 질문 (followups 가 있으면 키 안내, 빼 두었으면 코드를 넣어 달라는 안내)
    at.chat_input[0].set_value("LCEL이 뭐야?").run()
    shown = " ".join(m.value for m in at.markdown)
    check("코드 없는 질문 안내", not at.exception and ("키를 설정" in shown or "코드를 붙여 넣어 주세요" in shown))

    # 5. 대화 기록 다시 불러오기 (새 세션)
    at = login(app(), "봇사용자")
    convs = [b for b in at.sidebar.button if b.key and b.key.startswith("sess_")]
    check("대화 목록 저장", len(convs) >= len(VERSION_CASES) + 1, f"{len(convs)}개")
    convs[0].click().run()
    restored = [m.value for m in at.markdown if "LCEL이 뭐야" in m.value]
    check("대화 다시 열기 (질문 · 답 복원)", bool(restored) and bool(last_reply(at)) and
          any("질문과 답만" in i.value for i in at.info))

    # 6. 다른 사용자는 내 대화를 못 봄
    other = signup(app(), "다른사람")
    others = [b for b in other.sidebar.button if b.key and b.key.startswith("sess_")]
    check("다른 사용자 대화 분리", not others)

    print(f"\n{sum(results)}/{len(results)} 통과")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
