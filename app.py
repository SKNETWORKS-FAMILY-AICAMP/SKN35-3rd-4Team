"""LangChain 버전 마이그레이션 코드 어시스턴트 챗봇 화면 (4번 화면 · 평가).

실행 (프로젝트 루트에서, 자세한 방법은 docs/화면_실행방법.md):
    uv pip install -r requirements.txt
    uv run streamlit run app.py

구성
    로그인     username (중복 금지) → TiDB users 테이블 (user_id)
    사이드바   ChatGPT 처럼: 새 대화, 내 대화 목록, 로그아웃
    본문       위: 지금 코드 버전 · 변환할 버전 선택 / 왼쪽: 채팅 / 오른쪽: 결과 패널 (전후 비교 · 변경표 · 근거)
챗봇 호출은 src/ui/client.py 한 곳. 대화 기록은 src/ui/db.py (TiDB, 없으면 SQLite).

[선택 기능] 4번 영역이 아닌 기능은 src/ui/extras/ 에 있고 load() 로만 부른다. 폴더를 빼면 그 기능만 사라진다.
    followups       연상 질문(이어서 물어보기), 코드 없는 질문 답변
    version_detect  지금 코드 버전 자동 감지
자세한 정리: docs/머지_가이드.md
"""

import difflib
import re
import time
from datetime import timedelta

import streamlit as st

from src.ui import db
from src.ui.client import LATEST, TARGET_VERSIONS, mode, run
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
              "unresolved": "못 찾음"}
ORDER = ALL_WITH_NEW
USERNAME_RULE = re.compile(r"^[0-9A-Za-z가-힣_]{2,20}$")

ss = st.session_state
ss.setdefault("user", None)
ss.setdefault("conv_id", None)
ss.setdefault("messages", [])
ss.setdefault("followups", [])


# ---------------------------------------------------------------- 공통
def new_chat() -> None:
    ss["conv_id"], ss["messages"], ss["followups"] = None, [], []


def open_chat(conv_id: int) -> None:
    ss["conv_id"], ss["followups"] = conv_id, []
    ss["messages"] = [{"role": m["role"], "content": m["content"], "result": m["result"]}
                      for m in db.get_messages(conv_id, ss["user"]["user_id"])]


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
    if not v["success"]:
        return v["message"]
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
            "오른쪽에서 자세히 보세요.")


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
                name = st.text_input("사용할 username", placeholder="한글 · 영문 · 숫자 · _ 2~20자")
                if st.form_submit_button("시작하기", type="primary", width="stretch"):
                    if not USERNAME_RULE.match(name or ""):
                        st.error("username은 한글 · 영문 · 숫자 · _ 로 2~20자예요.")
                    else:
                        try:
                            ss["user"] = db.create_user(name)
                            st.rerun()
                        except db.UsernameTaken:
                            st.error(f"'{name}'은 이미 있는 username이에요. 다른 이름을 쓰거나 '이어서 하기'로 들어가세요.")
        with again:
            with st.form("login"):
                name = st.text_input("내 username")
                if st.form_submit_button("이어서 하기", type="primary", width="stretch"):
                    user = db.find_user(name.strip()) if name else None
                    if user:
                        ss["user"] = user
                        st.rerun()
                    else:
                        st.error("그 username은 없어요. '처음이에요'에서 만들어 주세요.")
        st.caption(f"대화 기록 저장: {db.backend_name()}")


# ---------------------------------------------------------------- 사이드바 (ChatGPT 처럼)
def sidebar() -> None:
    with st.sidebar:
        st.markdown(f"### {APP_NAME}")
        st.button("새 대화", icon=":material/edit_square:", width="stretch", on_click=new_chat)
        st.caption("내 대화")
        convs = db.list_conversations(ss["user"]["user_id"])
        if not convs:
            st.caption("아직 대화가 없어요.")
        for c in convs:
            st.button(c["title"], key=f"conv_{c['conv_id']}", width="stretch",
                      type="primary" if c["conv_id"] == ss["conv_id"] else "tertiary",
                      on_click=open_chat, args=(c["conv_id"],))
        st.divider()
        with st.container(horizontal=True, vertical_alignment="center"):
            st.markdown(f":material/account_circle: **{ss['user']['username']}**")
            st.button("로그아웃", key="logout", type="tertiary", on_click=logout)
        badge = {"mock": ("변환: 가짜 결과 · 근거 예시", "gray"),
                 "mock+real_evidence": ("변환: 가짜 결과 · 근거 2번 대응표", "blue")}.get(mode(), ("변환: 팀 챗봇", "green"))
        st.badge(badge[0], icon=":material/lan:", color=badge[1])
        st.badge(f"기록: {db.backend_name()}", icon=":material/database:", color="gray")


# ---------------------------------------------------------------- 결과 패널
def show_result(result: dict) -> None:
    v = result["verification"]
    with st.container(horizontal=True):
        if v["success"]:
            st.badge(f"검증 통과 · {v['attempts']}회", icon=":material/check_circle:", color="green")
        else:
            st.badge("변환 못 함", icon=":material/error:", color="red")
        st.badge(f"{result['source_version'] or AUTO} → {result['target_version']}", icon=":material/flag:",
                 color="gray")
        if result["changes"]:
            real = all(c["real_evidence"] for c in result["changes"])
            st.badge("근거: 2번 대응표" if real else "근거: 예시", icon=":material/menu_book:",
                     color="blue" if real else "gray")
    if not v["success"]:
        st.warning(v["message"])
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
        st.table([{"옛 줄": c["old"], "새 줄": c["new"], "종류": KIND_LABEL.get(c["kind"], c["kind"]),
                   "대안": c["alternative"] or "", "근거 ID": c["evidence_id"]} for c in result["changes"]])
        st.caption("옛 창고(classic)는 1.x에서 없어져 langchain_classic에만 남은 기능입니다. 대안이 있으면 최신 방식으로 바꿉니다.")


# ---------------------------------------------------------------- 대화 처리
def handle(text: str, source: str | None, target: str) -> None:
    """사용자 메시지 하나를 처리: 화면 표시 → 변환 또는 답변 → 기록 저장 → 연상 질문."""
    user_id = ss["user"]["user_id"]
    if ss["conv_id"] is None:
        title = text.strip().splitlines()[0][:30] or "새 대화"
        ss["conv_id"] = db.create_conversation(user_id, title, source, target)
    ss["messages"].append({"role": "user", "content": text, "result": None})
    db.add_message(ss["conv_id"], "user", text)

    code = extract_code(text)
    result = None
    if import_paths(code):
        result = run(code, target, source)
        note = version_note(result) if result["verification"]["success"] else None
        reply = (note + "\n\n" if note else "") + summary(result)
    elif followups is not None:            # [선택 기능: followups] 코드 없는 질문에 LLM 이 답함
        reply = followups.answer(text, ss["messages"][:-1])
    else:
        reply = "옛 LangChain 코드를 붙여 넣어 주세요. 코드가 있어야 바꿔 드릴 수 있어요."
    ss["messages"].append({"role": "assistant", "content": reply, "result": result})
    db.add_message(ss["conv_id"], "assistant", reply, result)
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
        if ss["conv_id"] is None:
            st.caption(":material/fiber_new: 새 세션 · 첫 질문을 보내면 저장이 시작돼요")
        else:
            info = db.get_conversation(ss["conv_id"], ss["user"]["user_id"])
            if info:
                st.caption(f":material/forum: 세션 #{info['conv_id']} · {info['created_at'] + KST:%m/%d %H:%M} 시작 · "
                           f"메시지 {len(ss['messages'])}개 · 같은 세션에 이어서 저장 중")
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
        else:
            st.info("코드를 넣으면 여기에 전후 비교, 바뀐 줄과 근거가 나옵니다.", icon=":material/arrow_back:")


# ---------------------------------------------------------------- 시작
if ss["user"] is None:
    login_screen()
else:
    sidebar()
    chat_screen()
