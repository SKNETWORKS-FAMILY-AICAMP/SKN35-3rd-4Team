"""LangChain 버전 마이그레이션 코드 어시스턴트 챗봇 화면 (4번 화면 · 평가).

실행 (프로젝트 루트에서, 자세한 방법은 docs/화면_실행방법.md):
    uv pip install -r requirements.txt
    uv run streamlit run streamlit_app.py

구성
    로그인     아이디 (가입 때 중복 검사) → users.user_id
    사이드바   ChatGPT 처럼: 새 대화(= 새 session_id), 내 대화 목록, 로그아웃
    기록       질문 하나와 답 하나를 chat_history 한 행으로 저장 (팀 ERD, docs/DB_설계.md)
    본문       위: 지금 코드 버전 · 변환할 버전 선택 / 왼쪽: 채팅 / 오른쪽: 결과 패널 (전후 비교 · 변경표 · 근거)
챗봇 호출은 src/ui/client.py 한 곳. 대화 기록은 src/ui/db.py (TiDB, 없으면 SQLite).

[선택 기능] 4번 영역이 아닌 기능은 src/ui/extras/ 에 있고 load() 로만 부른다. 폴더를 빼면 그 기능만 사라진다.
    followups       연상 질문(이어서 물어보기), 코드 없는 질문 답변
    version_detect  지금 코드 버전 자동 감지
자세한 정리: docs/머지_가이드.md
"""

import difflib
import json
import re
from pathlib import Path
import time
from datetime import timedelta

import streamlit as st

from src.ui import db
from src.ui.client import LATEST, TARGET_VERSIONS, graph_status, mode, run
from src.ui.optional import load
from src.ui.mock import import_paths
from src.ui.versions import ALL_WITH_NEW

KST = timedelta(hours=9)  # DB 시각은 UTC 로 저장, 화면에는 한국 시간

followups = load("followups")            # [선택 기능] 없으면 None
version_detect = load("version_detect")  # [선택 기능] 없으면 None

st.set_page_config(page_title="LangChain 마이그레이션 어시스턴트", page_icon=":material/sync_alt:", layout="wide")

APP_NAME = "LangChain 버전 마이그레이션 코드 어시스턴트"
AUTO = "자동 감지"
KIND_LABEL = {"native": "최신 위치", "moved": "위치 이동", "same": "그대로", "classic_fallback": "옛 창고(classic)",
              "unresolved": "못 찾음", "deprecated": "옛 메서드", "removed": "없어진 메서드", "exists": "그대로"}
# 확인용 예제: 평가 질문 중 1.x 로 올리는 30개 (팀 그래프가 지원하는 방향)
EXAMPLES = [q for q in json.loads((Path(__file__).parent / "eval" / "questions.json").read_text(encoding="utf-8"))
            if q["target_version"] == "1.x" and q["type"] != "버전 오가기"]
ORDER = ALL_WITH_NEW
USER_ID_RULE = re.compile(r"^[0-9A-Za-z가-힣_]{2,20}$")

ss = st.session_state
ss.setdefault("user", None)
ss.setdefault("session_id", None)
ss.setdefault("messages", [])
ss.setdefault("followups", [])


# ---------------------------------------------------------------- 공통
def new_chat() -> None:
    ss["session_id"], ss["messages"], ss["followups"] = None, [], []


def open_chat(session_id: str) -> None:
    """저장된 세션 다시 열기. 기록에는 질문 · 답만 있으므로 결과 패널은 비어 있다."""
    ss["session_id"], ss["followups"] = session_id, []
    ss["messages"] = []
    for row in db.get_history(session_id, ss["user"]["user_id"]):
        ss["messages"].append({"role": "user", "content": row["question"], "result": None})
        ss["messages"].append({"role": "assistant", "content": row["answer"] or "", "result": None})


def send_example() -> None:
    """확인용 예제: 그 질문의 버전으로 맞추고 보낸다 (위젯이 그려지기 전에 실행되는 콜백)."""
    q = next(x for x in EXAMPLES if x["id"] == ss["example_pick"])
    ss["source_pick"] = q["source_version"] if q["source_version"] in ALL_WITH_NEW else AUTO
    ss["target_pick"] = q["target_version"]
    ss["pending"] = f"{q['request']}\n\n```python\n{q['code']}```"


def logout() -> None:
    ss["user"] = None
    new_chat()


def extract_code(text: str) -> str:
    """메시지에서 코드 부분만. ``` 블록이 있으면 그 안, 없으면 전체."""
    blocks = re.findall(r"```(?:python)?\n(.*?)```", text, re.S)
    return "\n".join(blocks) if blocks else text


def as_markdown(text: str) -> str:
    """코드만 붙여 넣은 메시지는 코드 블록으로 보여 준다."""
    if "```" in text or not import_paths(text):
        return text
    return f"```python\n{text.strip()}\n```"


def summary(result: dict) -> str:
    v = result["verification"]
    note = f"\n\n_{result['note']}_" if result.get("note") else ""
    if result.get("mode") == "graph":           # 팀 그래프 결과
        n, left = len(result["changes"]), len(result["unresolved"])
        head = f"{n}군데를 고쳤어요." if n else "바꿀 부분을 찾지 못했어요."
        tail = f" 근거가 부족한 {left}줄은 그대로 두었어요." if left else ""
        check = (f" 검사는 {v['attempts']}회 만에 통과했어요." if v["success"] else
                 f" 다만 {v['attempts']}회 시도 후에도 검사를 통과하지 못했어요.")
        return head + tail + check + " 오른쪽에서 바뀐 줄과 근거를 보세요."
    if not v["success"]:
        return v["message"] + note
    changes = result["changes"]
    if not changes:
        return f"바꿀 import가 없어요. 쓰인 기능이 LangChain {result['target_version']}에도 그대로 있어요."
    classic = [c for c in changes if c["kind"] == "classic_fallback"]
    lcel = [c for c in classic if "StrOutputParser" in c["new"]]
    missing = [c for c in changes if c["kind"] == "unresolved"]
    extra = ""
    if lcel:
        extra += f" 1.x에서 없어진 기능 {len(lcel)}개는 최신 방식(LCEL)으로 바꿨어요."
    if len(classic) > len(lcel):
        extra += f" {len(classic) - len(lcel)}개는 옛 창고(classic) 위치와 대안을 같이 안내해요."
    if missing:
        extra += f" {len(missing)}개는 {result['target_version']}에 같은 기능이 없어서 그대로 두었어요."
    src = result["source_version"] or (result["detected"]["candidates"] or [None])[-1]
    back = src in ORDER and ORDER.index(result["target_version"]) < ORDER.index(src)
    head = f"LangChain {result['target_version']}로 되돌리면서 " if back else ""
    return (f"{head}import {len(changes)}줄을 찾아 고쳤어요.{extra} 검증은 {v['attempts']}회 만에 통과했어요. "
            "오른쪽에서 자세히 보세요." + note)


def version_note(result: dict) -> str | None:
    """[선택 기능: version_detect] 버전 감지 안내. 기능이 없으면 안내도 없음."""
    d = result["detected"]
    if version_detect is None or not d["candidates"]:
        return None
    if result["source_version"] is None:
        return version_detect.describe(d)
    if result["source_version"] not in d["candidates"]:
        span = d["candidates"][0] if len(d["candidates"]) == 1 else f"{d['candidates'][0]} ~ {d['candidates'][-1]}"
        return (f"고르신 버전은 {result['source_version']}인데, 코드는 **{span}** 시기 코드로 보여요 "
                f"(단서: {', '.join(d['clues'])}). 변환은 그대로 진행했어요.")
    return None


# ---------------------------------------------------------------- 로그인
def login_screen() -> None:
    _, mid, _ = st.columns([1, 1.2, 1])
    with mid:
        st.title(APP_NAME)
        st.caption("옛 LangChain 코드를 최신 버전으로 고치고, 근거와 검증 결과를 함께 보여 줍니다.")
        first, again = st.tabs(["처음이에요", "이어서 하기"])
        with first:
            with st.form("signup"):
                name = (st.text_input("사용할 아이디", placeholder="한글 · 영문 · 숫자 · _ 2~20자") or "").strip()
                if st.form_submit_button("시작하기", type="primary", width="stretch"):
                    if not USER_ID_RULE.match(name):
                        st.error("아이디는 한글 · 영문 · 숫자 · _ 로 2~20자예요.")
                    elif db.user_id_taken(name):                      # 중복 검사
                        st.error(f"'{name}'은 이미 있는 아이디예요. 다른 아이디를 쓰거나 '이어서 하기'로 들어가세요.")
                    else:
                        try:
                            ss["user"] = db.create_user(name)
                            st.rerun()
                        except db.UserIdTaken:                         # 그사이 누가 먼저 가입한 경우
                            st.error(f"'{name}'은 이미 있는 아이디예요. 다른 아이디를 써 주세요.")
        with again:
            with st.form("login"):
                name = (st.text_input("내 아이디") or "").strip()
                if st.form_submit_button("이어서 하기", type="primary", width="stretch"):
                    user = db.find_user(name) if name else None
                    if user:
                        ss["user"] = user
                        st.rerun()
                    else:
                        st.error("그 아이디는 없어요. '처음이에요'에서 만들어 주세요.")
        st.caption(f"대화 기록 저장: {db.backend_name()}")


# ---------------------------------------------------------------- 사이드바 (ChatGPT 처럼)
def sidebar() -> None:
    with st.sidebar:
        st.markdown(f"### {APP_NAME}")
        st.button("새 대화", icon=":material/edit_square:", width="stretch", on_click=new_chat)
        with st.expander(f"확인용 예제 ({len(EXAMPLES)}개)", icon=":material/science:"):
            st.selectbox("예제 고르기", [q["id"] for q in EXAMPLES], key="example_pick",
                         format_func=lambda i: next(f"{q['id']} · {q['type']} · {q['difficulty']}" for q in EXAMPLES
                                                    if q["id"] == i))
            pick = next(q for q in EXAMPLES if q["id"] == ss.get("example_pick", EXAMPLES[0]["id"]))
            st.caption(f"{pick['request']} (지금 코드 {pick['source_version']} → 1.x)")
            st.button("이 예제 보내기", icon=":material/send:", width="stretch", type="primary",
                      key="send_example", on_click=send_example)
        st.caption("내 대화")
        sessions = db.list_sessions(ss["user"]["user_id"])
        if not sessions:
            st.caption("아직 대화가 없어요.")
        for c in sessions:
            st.button(c["title"], key=f"sess_{c['session_id']}", width="stretch",
                      type="primary" if c["session_id"] == ss["session_id"] else "tertiary",
                      on_click=open_chat, args=(c["session_id"],))
        st.divider()
        with st.container(horizontal=True, vertical_alignment="center"):
            st.markdown(f":material/account_circle: **{ss['user']['user_id']}**")
            st.button("로그아웃", key="logout", type="tertiary", on_click=logout)
        badge = {"mock": ("변환: 가짜 결과 · 근거 예시", "gray"),
                 "mock+real_evidence": ("변환: 가짜 결과 · 근거 2번 대응표", "blue")}.get(mode(), ("변환: 팀 챗봇", "green"))
        st.badge(badge[0], icon=":material/lan:", color=badge[1])
        ok, why = graph_status()
        if not ok:
            st.caption(f"팀 그래프 연결 안 됨: {why}")
        st.badge(f"기록: {db.backend_name()}", icon=":material/database:", color="gray")


# ---------------------------------------------------------------- 결과 패널
def show_result(result: dict) -> None:
    v = result["verification"]
    with st.container(horizontal=True):
        if v["success"]:
            st.badge(f"검증 통과 · {v['attempts']}회", icon=":material/check_circle:", color="green")
        elif result.get("mode") == "graph":
            st.badge(f"검증 실패 · {v['attempts']}회", icon=":material/error:", color="red")
        else:
            st.badge("변환 못 함", icon=":material/error:", color="red")
        if result.get("mode") == "graph":
            st.badge("팀 그래프", icon=":material/hub:", color="violet")
        st.badge(f"{result['source_version'] or AUTO} → {result['target_version']}", icon=":material/flag:",
                 color="gray")
        if result["changes"]:
            real = all(c["real_evidence"] for c in result["changes"])
            st.badge("근거: 2번 대응표" if real else "근거: 예시", icon=":material/menu_book:",
                     color="blue" if real else "gray")
    if not v["success"]:
        st.warning(v["message"])
        if result.get("mode") != "graph":
            return
    before, after = st.tabs(["전후 비교", "변경표 · 근거"])
    with before:
        left, right = st.columns(2)
        left.caption("변경 전")
        left.code(result["original_code"], language="python", wrap_lines=True)
        right.caption("변경 후")
        right.code(result["migrated_code"], language="python", wrap_lines=True)
        diff = difflib.unified_diff(result["original_code"].splitlines(), result["migrated_code"].splitlines(),
                                    "변경 전", "변경 후", lineterm="")
        with st.expander("바뀐 줄만 보기"):
            st.code("\n".join(diff), language="diff")
    with after:
        rows = [{"옛 줄": c["old"], "새 줄": c["new"], "종류": KIND_LABEL.get(c["kind"], c["kind"]),
                 "대안": c["alternative"] or "", "근거 ID": c["evidence_id"]} for c in result["changes"]]
        if result.get("mode") == "graph":           # 그래프는 바꾼 이유도 준다
            for row, c in zip(rows, result["changes"]):
                row["이유"] = c.get("reason", "")
        if rows:
            st.table(rows)
        st.caption("옛 창고(classic)는 1.x에서 없어져 langchain_classic에만 남은 기능입니다. 대안이 있으면 최신 방식으로 바꿉니다.")
        if result.get("unresolved"):
            st.markdown("**바꾸지 못한 줄** (근거 부족)")
            st.table([{"줄": u.get("code", ""), "이유": u.get("reason", "")} for u in result["unresolved"]])
        if result.get("install_packages"):
            st.markdown("**설치할 패키지**")
            st.code("pip install " + " ".join(result["install_packages"]), language="bash")
        for n in result.get("notes") or []:
            st.caption(f":material/info: {n}")


# ---------------------------------------------------------------- 대화 처리
def handle(text: str, source: str | None, target: str) -> None:
    """사용자 메시지 하나를 처리: 화면 표시 → 변환 또는 답변 → 기록 저장 → 연상 질문."""
    if ss["session_id"] is None:                     # 새 대화의 첫 질문 → 새 세션
        ss["session_id"] = db.new_session_id()
    ss["messages"].append({"role": "user", "content": text, "result": None})

    code = extract_code(text)
    result = None
    if import_paths(code):
        result = run(code, target, source, question=text)
        note = version_note(result) if result["verification"]["success"] else None
        reply = (note + "\n\n" if note else "") + summary(result)
    elif followups is not None:            # [선택 기능: followups] 코드 없는 질문에 LLM 이 답함
        reply = followups.answer(text, ss["messages"][:-1])
    else:
        reply = "옛 LangChain 코드를 붙여 넣어 주세요. 코드가 있어야 바꿔 드릴 수 있어요."
    ss["messages"].append({"role": "assistant", "content": reply, "result": result})
    db.add_turn(ss["user"]["user_id"], ss["session_id"], text, reply)   # 질문 + 답 = chat_history 한 행
    # [선택 기능: followups] 연상 질문 — 시작
    ss["followups"] = followups.followups(text, result) if followups is not None else []
    # [선택 기능: followups] 연상 질문 — 끝


def chat_screen() -> None:
    head, ver_src, ver_tgt = st.columns([2.2, 1, 1], vertical_alignment="bottom")
    head.markdown(f"#### {APP_NAME}")
    source = ver_src.selectbox("지금 코드 버전", [AUTO, *ALL_WITH_NEW], key="source_pick")
    ss.setdefault("target_pick", TARGET_VERSIONS[-1])     # 기본은 최신(1.x)
    target = ver_tgt.selectbox("변환할 버전", TARGET_VERSIONS, key="target_pick",
                               format_func=lambda v: f"LangChain {v} (최신 {LATEST['langchain']})" if v == "1.x"
                               else f"LangChain {v}")
    source = None if source == AUTO else source
    if source == target:
        st.warning("지금 코드 버전과 변환할 버전이 같아요. 변환할 버전을 바꿔 주세요.", icon=":material/info:")

    chat_col, result_col = st.columns([1, 1.25], gap="large")
    with chat_col:
        # 세션 = 대화 하나 ("새 대화"를 누를 때만 새로 시작, 그 안의 질문은 같은 세션에 이어서 저장)
        if ss["session_id"] is None:
            st.caption(":material/fiber_new: 새 세션 · 첫 질문을 보내면 저장이 시작돼요")
        else:
            info = db.session_info(ss["session_id"], ss["user"]["user_id"])
            if info:
                st.caption(f":material/forum: 세션 {info['session_id'][:8]} · {info['started_at'] + KST:%m/%d %H:%M} 시작 · "
                           f"질문 {info['turns']}개 · 같은 세션에 이어서 저장 중")
        box = st.container(height=560)
        with box:
            if not ss["messages"]:
                with st.chat_message("assistant"):
                    st.write("옛 LangChain 코드를 붙여 넣어 보세요. 바꿀 버전은 위에서 고를 수 있어요.")
            for m in ss["messages"]:
                with st.chat_message(m["role"]):
                    st.markdown(as_markdown(m["content"]) if m["role"] == "user" else m["content"])
            # [선택 기능: followups] 이어서 물어보기 버튼 — 시작
            if followups is not None and ss["followups"]:
                st.caption("이어서 물어보기")
                for i, f in enumerate(ss["followups"]):
                    if st.button(f, key=f"follow_{i}", icon=":material/subdirectory_arrow_right:", width="stretch"):
                        ss["pending"] = f
            elif followups is not None and ss["messages"] and not followups.api_key():
                st.caption("OpenAI 키를 설정하면 이어서 물어볼 질문이 여기에 나와요.")
            # [선택 기능: followups] 이어서 물어보기 버튼 — 끝
        typed = st.chat_input("옛 코드나 질문을 입력하세요 (여러 줄은 Shift+Enter)")
        text = typed or ss.pop("pending", None)
        if text:
            with box:
                with st.chat_message("user"):
                    st.markdown(as_markdown(text))
                with st.chat_message("assistant"):
                    with st.status("처리하는 중...", expanded=False):
                        handle(text, source, target)
                        time.sleep(0.2)
            st.rerun()
    with result_col:
        st.subheader("결과", divider="blue")
        last = next((m["result"] for m in reversed(ss["messages"]) if m.get("result")), None)
        if last:
            show_result(last)
        elif ss["messages"]:
            st.info("다시 연 대화는 질문과 답만 저장돼 있어요. 코드를 다시 보내면 결과가 여기에 나와요.",
                    icon=":material/history:")
        else:
            st.info("코드를 넣으면 여기에 전후 비교, 바뀐 줄과 근거가 나옵니다.", icon=":material/arrow_back:")


# ---------------------------------------------------------------- 시작
if ss["user"] is None:
    login_screen()
else:
    sidebar()
    chat_screen()
