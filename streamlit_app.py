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
from src.ui.client import LATEST, ask, graph_status, mode, run
from src.ui.optional import load
from src.ui.mock import import_paths
from src.ui import result_view
from src.ui.versions import ALL_WITH_NEW

KST = timedelta(hours=9)  # DB 시각은 UTC 로 저장, 화면에는 한국 시간

followups = load("followups")            # [선택 기능] 없으면 None
version_detect = load("version_detect")  # [선택 기능] 없으면 None

st.set_page_config(page_title="LangChain 마이그레이션 어시스턴트", page_icon=":material/sync_alt:", layout="wide")

APP_NAME = "LangChain 버전 마이그레이션 코드 어시스턴트"
AUTO = "자동 감지"
KIND_LABEL = {"native": "최신 위치", "moved": "위치 이동", "same": "그대로", "classic_fallback": "옛 창고(classic)",
              "unresolved": "못 찾음", "deprecated": "옛 메서드", "removed": "없어진 메서드", "exists": "그대로"}
# 확인용 예제: 평가 질문 중 1.x 로 올리는 30개 (팀 그래프가 지원하는 방향). 파일이 없으면 예제 칸을 숨긴다
_EXAMPLE_FILE = Path(__file__).parent / "eval" / "questions.json"
EXAMPLES = ([q for q in json.loads(_EXAMPLE_FILE.read_text(encoding="utf-8"))
             if q["target_version"] == "1.x" and q["type"] != "버전 오가기"] if _EXAMPLE_FILE.exists() else [])
ORDER = ALL_WITH_NEW
USER_ID_RULE = re.compile(r"^[0-9A-Za-z가-힣_]{2,20}$")

ss = st.session_state
ss.setdefault("user", None)
ss.setdefault("session_id", None)
ss.setdefault("messages", [])
ss.setdefault("followups", [])


# ---------------------------------------------------------------- 공통
def new_chat() -> None:
    ss["session_id"], ss["messages"], ss["followups"], ss["reopened"] = None, [], [], False


def open_chat(session_id: str) -> None:
    """저장된 세션 다시 열기. 기록에는 질문 · 답만 있으므로 결과 패널은 비어 있다."""
    ss["session_id"], ss["followups"], ss["reopened"] = session_id, [], True
    ss["messages"] = []
    for row in db.get_history(session_id, ss["user"]["user_id"]):
        ss["messages"].append({"role": "user", "content": row["question"], "result": None})
        ss["messages"].append({"role": "assistant", "content": row["answer"] or "", "result": None})


def send_example() -> None:
    """확인용 예제: 그 질문의 버전으로 맞추고 보낸다 (위젯이 그려지기 전에 실행되는 콜백)."""
    q = next(x for x in EXAMPLES if x["id"] == ss["example_pick"])
    ss["pending"] = f"{q['request']}\n\n```python\n{q['code']}```"


def retry(request: str) -> None:
    """검사에 실패한 요청을 그대로 다시 보낸다 (위젯이 그려지기 전에 실행되는 콜백)."""
    ss["pending"] = request


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
        if EXAMPLES:
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


def version_label(result: dict) -> str:
    """원래 버전 → 바꾼 버전 (원래 버전을 모르면 바꾼 버전만)."""
    src = result.get("source_version")
    found = (result.get("detected") or {}).get("candidates") or []
    if not src and found:                            # 임시 결과: 화면이 코드로 짐작한 시기
        src = found[0] if len(found) == 1 else f"{found[0]} ~ {found[-1]}"
    return f"{src} → {result['target_version']}" if src else f"→ {result['target_version']}"


def show_history(results: list[dict]) -> None:
    """한 대화에서 여러 번 바꿨으면 흐름을 짧게: ① 0.1.20 → 1.4.5  ② 1.4.5 → 0.2.17 (지금 것은 진하게)."""
    if len(results) < 2:
        return
    marks = "①②③④⑤⑥⑦⑧⑨⑩"
    parts = []
    for i, r in enumerate(results):
        label = f"{marks[i] if i < len(marks) else i + 1} {version_label(r)}"
        parts.append(f"**{label}**" if i == len(results) - 1 else f":gray[{label}]")
    st.markdown("변환 기록 &nbsp; " + " &nbsp;·&nbsp; ".join(parts))


def show_result(result: dict) -> None:
    v = result["verification"]
    graph = result.get("mode") == "graph"
    with st.container(horizontal=True):
        if v["success"]:
            st.badge(f"검증 통과 · {v['attempts']}회", icon=":material/check_circle:", color="green")
        elif graph:
            st.badge(f"검증 실패 · {v['attempts']}회", icon=":material/error:", color="red")
        else:
            st.badge("변환 못 함", icon=":material/error:", color="red")
        st.badge(version_label(result), icon=":material/swap_horiz:", color="blue")
        if not graph:
            st.badge("임시 결과", icon=":material/hub:", color="gray")
    if not graph:
        st.caption("팀 챗봇에 연결되지 않아 화면이 대응표로 만든 임시 결과예요.")
    if not v["success"]:
        st.warning(v["message"])
        if graph and result.get("request"):
            st.button("같은 요청으로 다시 시도", icon=":material/refresh:", type="primary",
                      key=f"retry_{abs(hash(result['request'] + result['migrated_code'])) % 10**8}",
                      on_click=retry, args=(result["request"],),
                      help="검사에 실패한 요청을 처음부터 다시 보내요. 챗봇이 근거를 새로 찾아 다시 고쳐요.")
        if not graph:
            return
    evs = result.get("evidences") or []
    n_ev = len(evs) or len({i.strip() for c in result["changes"] for i in (c.get("evidence_id") or "").split(",") if i.strip()})
    notes = result_view.notes_html(result)
    labels = ["전후 비교", f"변경 사항 {len(result['changes'])}", f"근거 {n_ev}", "검사 결과", "코드 받기"]
    labels += ["안내"] if notes else []
    labels += ["처리 과정"] if result.get("steps") else []
    tabs = st.tabs(labels)
    with tabs[0]:
        st.html(result_view.diff_html(result["original_code"], result["migrated_code"]))
    with tabs[1]:
        st.html(result_view.changes_html(result["changes"], evs))
    with tabs[2]:
        st.html(result_view.evidence_html(evs, result["changes"]))
    with tabs[3]:
        st.html(result_view.checks_html(result))
    with tabs[4]:
        st.caption("바뀐 코드예요. 오른쪽 위 버튼으로 복사할 수 있어요.")
        st.code(result["migrated_code"], language="python", wrap_lines=True)
        key = abs(hash(result["migrated_code"])) % 10**8
        with st.container(horizontal=True):
            st.download_button("코드 내려받기 (.py)", result["migrated_code"], file_name="migrated.py",
                               mime="text/x-python", icon=":material/download:", key=f"dl_py_{key}")
            st.download_button("변경 리포트 내려받기 (.md)", result_view.report_md(result), file_name="migration_report.md",
                               mime="text/markdown", icon=":material/description:", key=f"dl_md_{key}")
        if result.get("install_packages"):
            st.caption("먼저 설치할 패키지")
            st.code("pip install " + " ".join(result["install_packages"]), language="bash")
    if notes:
        with tabs[5]:
            st.html(notes)
    if result.get("steps"):
        with tabs[-1]:
            st.caption("그래프가 실제로 지나간 단계예요. 실패한 회차와 다시 시도한 과정도 그대로 남아요.")
            show_steps(result["steps"], result.get("seconds"))


# ---------------------------------------------------------------- 처리 과정 (진행 표시 · 답 아래 기록 · 결과 탭)
def show_step(done: str, details=(), sec=None) -> None:
    """단계 하나: 끝난 일 한 줄 + 세부 내용 (무엇을 찾았고, 어떤 근거로, 왜 실패했는지)."""
    tail = f"  ·  {sec:.0f}초" if sec is not None else ""
    st.markdown(f":material/check_circle: **{done}**{tail}")
    for d in details:
        st.markdown(f"<div style='margin:-6px 0 2px 28px;font-size:0.86rem;opacity:.8'>· {as_inline(d)}</div>",
                    unsafe_allow_html=True)


def as_inline(text: str) -> str:
    """세부 내용의 `코드` 부분만 <code>로, 나머지는 HTML 이스케이프."""
    import html as _html
    parts = str(text).split("`")
    return "".join(f"<code>{_html.escape(p)}</code>" if i % 2 else _html.escape(p) for i, p in enumerate(parts))


def show_steps(steps: list, seconds=None) -> None:
    for s in steps:
        show_step(s["done"], s.get("details") or [], s.get("sec"))
    if seconds is not None:
        st.caption(f"전체 {seconds:.0f}초 · {len(steps)}단계")


def steps_label(m: dict) -> str:
    n = len(m.get("steps") or [])
    return f"처리 과정 보기 · {n}단계" + (f" · {m['seconds']:.0f}초" if m.get("seconds") is not None else "")


# ---------------------------------------------------------------- 대화 처리
def handle(text: str, status=None) -> None:
    """사용자 메시지 하나를 처리: 화면 표시 → 팀 그래프(질문 분류 → 변환 · 검색 · 일반 답) → 기록 저장 → 연상 질문.

    status: st.status 상자. 그래프 단계가 끝날 때마다 끝난 일을 한 줄 쓰고, 제목을 다음 할 일로 바꾼다.
    """
    if ss["session_id"] is None:                     # 새 대화의 첫 질문 → 새 세션
        ss["session_id"] = db.new_session_id()
    ss["messages"].append({"role": "user", "content": text, "result": None})

    def on_step(done: str, nxt: str, details=()) -> None:
        if status is not None:
            show_step(done, details)
            status.update(label=nxt, expanded=True)      # 제목만 바꾸면 상자가 접혀 세부 내용이 안 보임

    code = extract_code(text)
    result, steps, seconds = None, [], None
    try:
        answer = ask(text, on_step)                  # 팀 그래프 (없으면 None)
    except Exception as e:                           # 그래프 실행 중 오류 → 임시 결과로 계속
        answer = None
        st.toast(f"팀 그래프 오류로 임시 결과를 보여 줘요: {type(e).__name__}", icon=":material/warning:")
    if answer is not None:
        result = answer["result"]
        steps, seconds = answer.get("steps") or [], answer.get("seconds")
        reply = summary(result) if result else answer["reply"]
        if result:
            result["request"] = text                 # 다시 시도 버튼이 같은 요청을 다시 보냄
    elif import_paths(code):                         # 그래프 없음: 화면 쪽 임시 결과 (1.x 로)
        result = run(code)
        note = version_note(result) if result["verification"]["success"] else None
        reply = (note + "\n\n" if note else "") + summary(result)
    elif followups is not None:            # [선택 기능: followups] 코드 없는 질문에 LLM 이 답함
        reply = followups.answer(text, ss["messages"][:-1])
    else:
        reply = "옛 LangChain 코드를 붙여 넣어 주세요. 코드가 있어야 바꿔 드릴 수 있어요."
    ss["messages"].append({"role": "assistant", "content": reply, "result": result, "steps": steps, "seconds": seconds})
    db.add_turn(ss["user"]["user_id"], ss["session_id"], text, reply)   # 질문 + 답 = chat_history 한 행
    # [선택 기능: followups] 연상 질문 — 시작
    ss["followups"] = followups.followups(text, result) if followups is not None else []
    # [선택 기능: followups] 연상 질문 — 끝


def chat_screen() -> None:
    st.markdown(f"#### {APP_NAME}")
    st.caption(f"바꿀 버전은 질문에 적어 주세요 (예: \"0.2로 되돌려 줘\"). 적지 않으면 최신 LangChain {LATEST['langchain']}로 바꿔요.")

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
                    st.write("옛 LangChain 코드를 붙여 넣거나, LangChain 버전 변화에 대해 물어보세요.")
            last_bot = max((i for i, m in enumerate(ss["messages"]) if m["role"] == "assistant"), default=-1)
            for i, m in enumerate(ss["messages"]):
                with st.chat_message(m["role"]):
                    if m["role"] == "assistant" and m.get("steps"):   # 답 위에 처리 과정 (가장 최근 답은 펼쳐 둠)
                        with st.expander(steps_label(m), icon=":material/account_tree:", expanded=(i == last_bot)):
                            show_steps(m["steps"], m.get("seconds"))
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
                    with st.status("질문 종류를 파악하는 중", expanded=True) as status:
                        handle(text, status)
                        status.update(label="완료 · 처리 과정은 답 위에 남겨 둬요", state="complete", expanded=True)
                        time.sleep(0.2)
            st.rerun()
    with result_col:
        st.subheader("결과", divider="blue")
        results = [m["result"] for m in ss["messages"] if m.get("result")]
        last = results[-1] if results else None
        if last:
            show_history(results)
            show_result(last)
        elif ss["messages"] and ss.get("reopened"):
            st.info("다시 연 대화는 질문과 답만 저장돼 있어요. 코드를 다시 보내면 결과가 여기에 나와요.",
                    icon=":material/history:")
        elif ss["messages"]:
            st.info("질문에 대한 답은 왼쪽 대화에 있어요. 코드 변환을 요청하면 여기에 전후 비교와 근거가 나옵니다.",
                    icon=":material/arrow_back:")
        else:
            st.info("코드를 넣으면 여기에 전후 비교, 바뀐 줄과 근거가 나옵니다.", icon=":material/arrow_back:")


# ---------------------------------------------------------------- 시작
if ss["user"] is None:
    login_screen()
else:
    sidebar()
    chat_screen()
