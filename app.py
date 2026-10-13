"""LangChain 마이그레이션 챗봇 화면 (4번 화면 · 평가).

실행 (프로젝트 루트에서):
    uv add streamlit streamlit-agraph   # 팀 저장소에서는 1번과 상의 후
    uv run streamlit run app.py

흐름: ① 시작 화면(버전 마인드맵에서 옛 버전 고르기, 모르면 자동 감지)
      → ② 목표 버전 확인 (최신 버전 안내)
      → ③ 채팅 + 결과 패널 (전후 비교 · 근거 · 진행 과정)
챗봇 호출은 src/ui/client.py 한 곳에서만 한다. 지금은 가짜 결과, 근거는 2번 대응표가 있으면 실제.
"""

import difflib
import time

import streamlit as st
from streamlit_agraph import agraph

from src.ui.client import LATEST, TARGET_VERSIONS, mode, run
from src.ui.mindmap import AUTO_ID, clicked_version, graph
from src.ui.versions import ALL, SUMMARY, describe

st.set_page_config(page_title="LangChain 마이그레이션 챗봇", page_icon=":material/sync_alt:", layout="wide")

AUTO = "모르겠어요 (자동 감지)"
EXAMPLES = {
    "쉬움 · import 경로": (
        "from langchain.chat_models import ChatOpenAI\n"
        "from langchain.prompts import PromptTemplate\n\n"
        "llm = ChatOpenAI(temperature=0)\n"
        "prompt = PromptTemplate.from_template(\"{topic}을 한 줄로 설명해줘\")"
    ),
    "중간 · LLMChain": (
        "from langchain.chat_models import ChatOpenAI\n"
        "from langchain.chains import LLMChain\n"
        "from langchain.prompts import PromptTemplate\n\n"
        "llm = ChatOpenAI(temperature=0)\n"
        "prompt = PromptTemplate.from_template(\"{product}을 만드는 회사 이름을 지어줘\")\n"
        "chain = LLMChain(llm=llm, prompt=prompt)\n"
        "print(chain.run(product=\"양말\"))"
    ),
    "어려움 · 에이전트 · 메모리": (
        "from langchain.chat_models import ChatOpenAI\n"
        "from langchain.agents import initialize_agent\n"
        "from langchain.memory import ConversationBufferMemory\n\n"
        "llm = ChatOpenAI(temperature=0)\n"
        "memory = ConversationBufferMemory()\n"
        "agent = initialize_agent([], llm, memory=memory)"
    ),
    "버전 단서 · tool calling 에이전트": (
        "from langchain_openai import ChatOpenAI\n"
        "from langchain.agents import create_tool_calling_agent\n\n"
        "llm = ChatOpenAI(temperature=0)\n"
        "agent = create_tool_calling_agent(llm, tools=[], prompt=prompt)"
    ),
}
KIND_LABEL = {"native": "최신 위치", "classic_fallback": "옛 창고(classic)", "unresolved": "못 찾음"}
MODE_BADGE = {
    "mock": ("가짜 결과 · 예시 근거", "gray"),
    "mock+real_evidence": ("가짜 결과 · 근거는 2번 대응표", "blue"),
    "graph": ("팀 챗봇 연결됨", "green"),
}

ss = st.session_state
ss.setdefault("stage", "start")            # start → confirm → chat
ss.setdefault("source", None)              # 고른 옛 버전, None 이면 자동 감지
ss.setdefault("target", TARGET_VERSIONS[0])
ss.setdefault("messages", [])
ss.setdefault("results", [])


def go(stage: str) -> None:
    ss["stage"] = stage


def source_label() -> str:
    return "자동 감지" if ss["source"] is None else f"LangChain {ss['source']}"


# ---------------------------------------------------------------- 사이드바
with st.sidebar:
    st.title("마이그레이션 챗봇")
    st.caption("옛 LangChain 코드를 최신 버전으로 고치고, 근거와 검증 결과를 함께 보여 줍니다.")
    label, color = MODE_BADGE[mode()]
    st.badge(label, icon=":material/lan:", color=color)
    if ss["stage"] == "chat":
        st.subheader("버전", divider="gray")
        st.markdown(f"**{source_label()}** → **LangChain {ss['target']}**")
        st.button("버전 다시 고르기", icon=":material/account_tree:", width="stretch", on_click=go, args=("start",))
        st.subheader("예제로 해 보기", divider="gray")
        for name, code in EXAMPLES.items():
            if st.button(name, width="stretch"):
                ss["pending"] = code
        if st.button("대화 지우기", icon=":material/delete:", width="stretch"):
            ss["messages"], ss["results"] = [], []
            st.rerun()

convert_tab, compare_tab, about_tab = st.tabs(
    [":material/forum: 변환하기", ":material/bar_chart: 비교 (준비 중)", ":material/info: 프로젝트 소개"])


# ---------------------------------------------------------------- ① 시작: 버전 마인드맵
def start_screen():
    st.subheader("어떤 버전의 LangChain 코드를 바꾸시나요?", divider="blue")
    current = ss.get("pick")
    nodes, edges, config = graph(None if current in (None, AUTO) else current, auto=current == AUTO)
    with st.container(border=True):
        got = agraph(nodes, edges, config)          # 상자를 클릭하면 그 상자의 id
        st.caption("**버전 상자를 클릭하세요.** 고른 버전 아래로 영역 가지가 펼쳐집니다. "
                   "마우스 휠로 확대 · 축소, 빈 곳을 끌어서 이동할 수 있어요. "
                   "글자: 기능 수, 1.x에서 최신 위치 / 옛 창고(classic) 비율 · 숫자는 2번 import 대응표 기준")
    picked = clicked_version(got)
    if picked and got != ss.get("last_click"):
        ss["last_click"] = got
        ss["pick"] = AUTO if picked == AUTO_ID else picked
        st.rerun()
    choice = st.pills("또는 버튼으로 고르기", [*ALL, AUTO], key="pick")
    if not choice:
        st.info("마인드맵의 버전 상자를 눌러 주세요. 모르면 \"모르겠어요\" 상자를 누르면 코드를 보고 짐작해 드려요.",
                icon=":material/touch_app:")
        return
    info = next((v for v in SUMMARY["versions"] if v["version"] == choice), None)
    left, right = st.columns([3, 1], vertical_alignment="center")
    with left:
        if info:
            k = info["kinds"]
            c0, c1, c2, c3 = st.columns(4)
            c0.metric("기능 수", f"{info['total']:,}")
            c1.metric("최신 위치로 이사", f"{k.get('native', 0):,}")
            c2.metric("옛 창고(classic)", f"{k.get('classic_fallback', 0):,}")
            c3.metric("못 찾음", f"{k.get('unresolved', 0):,}")
        else:
            st.info("코드를 넣으면 어느 버전 시기의 코드인지 짐작해서 알려 드려요.", icon=":material/search:")
    if right.button("다음: 목표 버전 확인", type="primary", icon=":material/arrow_forward:", width="stretch"):
        ss["source"] = None if choice == AUTO else choice
        go("confirm")
        st.rerun()


# ---------------------------------------------------------------- ② 목표 버전 확인
def confirm_screen():
    st.subheader("목표 버전을 확인해 주세요", divider="blue")
    with st.container(border=True):
        a, arrow, b = st.columns([1, 0.3, 1], vertical_alignment="center")
        a.metric("바꿀 코드", source_label())
        arrow.markdown("### →")
        b.metric("목표 버전", f"LangChain {ss['target']}")
        st.caption(f"현재 최신 버전: langchain **{LATEST['langchain']}** · langchain-core **{LATEST['langchain-core']}** "
                   "(2번 데이터 기준). 지금은 1.x로 바꾸는 것만 지원해요.")
    c1, c2 = st.columns([1, 4])
    if c1.button("확인하고 시작", type="primary", icon=":material/check:"):
        go("chat")
        st.rerun()
    if c2.button("다시 고르기", icon=":material/arrow_back:"):
        go("start")
        st.rerun()


# ---------------------------------------------------------------- ③ 채팅 + 결과
def summary(result: dict) -> str:
    v = result["verification"]
    if not v["success"]:
        return v["message"]
    changes = result["changes"]
    classic = [c for c in changes if c["kind"] == "classic_fallback"]
    lcel = [c for c in classic if "StrOutputParser" in c["new"]]
    missing = [c for c in changes if c["kind"] == "unresolved"]
    extra = ""
    if lcel:
        extra += f" 1.x에서 없어진 기능 {len(lcel)}개는 최신 방식(LCEL)으로 바꿨어요."
    if len(classic) > len(lcel):
        extra += f" {len(classic) - len(lcel)}개는 옛 창고(classic) 위치와 대안을 같이 안내해요."
    if missing:
        extra += f" {len(missing)}개는 1.x에서 옮길 곳을 찾지 못했어요."
    return (f"import {len(changes)}줄을 찾아 고쳤어요.{extra} 검증은 {v['attempts']}회 만에 통과했어요. "
            "오른쪽에서 자세히 보세요.")


def version_note(result: dict) -> str | None:
    d = result["detected"]
    if result["source_version"] is None:
        return describe(d)
    if result["source_version"] not in d["candidates"]:
        span = d["candidates"][0] if len(d["candidates"]) == 1 else f"{d['candidates'][0]} ~ {d['candidates'][-1]}"
        return (f"고르신 버전은 {result['source_version']}인데, 코드는 **{span}** 시기 코드로 보여요 "
                f"(단서: {', '.join(d['clues'])}). 변환은 그대로 진행했어요.")
    return None


def show_result(result: dict) -> None:
    v = result["verification"]
    with st.container(horizontal=True):
        if v["success"]:
            st.badge(f"검증 통과 · {v['attempts']}회", icon=":material/check_circle:", color="green")
        else:
            st.badge("변환 못 함", icon=":material/error:", color="red")
        st.badge(f"{result['source_version'] or '자동 감지'} → {result['target_version']}", icon=":material/flag:",
                 color="gray")
        if result["changes"]:
            real = all(c["real_evidence"] for c in result["changes"])
            st.badge("근거: 2번 대응표" if real else "근거: 예시", icon=":material/menu_book:",
                     color="blue" if real else "gray")
    if not v["success"]:
        st.warning(v["message"])
        return
    before, after, steps = st.tabs(["전후 비교", "변경표 · 근거", "진행 과정"])
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
    with steps:
        for s in result["steps"]:
            st.markdown(f"**{s['name']}** · {s['detail']}")


def chat_screen():
    top_l, top_r = st.columns([3, 1], vertical_alignment="center")
    top_l.markdown(f"#### {source_label()} → LangChain {ss['target']}")
    top_r.button("버전 다시 고르기", icon=":material/account_tree:", on_click=go, args=("start",), key="reselect_top")
    chat_col, result_col = st.columns([1, 1.25], gap="large")
    with chat_col:
        box = st.container(height=520)
        with box:
            if not ss["messages"]:
                with st.chat_message("assistant"):
                    hint = ("버전을 모르셔도 괜찮아요. 코드를 넣으면 어느 시기 코드인지 알려 드릴게요."
                            if ss["source"] is None else f"{ss['source']} 시기 코드를 붙여 넣어 주세요.")
                    st.write(f"옛 LangChain 코드를 붙여 넣어 주세요. {hint} 왼쪽 예제 버튼으로 바로 해 볼 수도 있어요.")
            for m in ss["messages"]:
                with st.chat_message(m["role"]):
                    if m["role"] == "user":
                        st.code(m["content"], language="python", wrap_lines=True)
                    else:
                        st.markdown(m["content"])
        typed = st.chat_input("옛 코드를 붙여 넣으세요 (여러 줄은 Shift+Enter)")
        code = typed or ss.pop("pending", None)
        if code:
            ss["messages"].append({"role": "user", "content": code})
            with box:
                with st.chat_message("user"):
                    st.code(code, language="python", wrap_lines=True)
                with st.chat_message("assistant"):
                    with st.status("변환하는 중...", expanded=True) as status:
                        result = run(code, ss["target"], ss["source"])
                        for s in result["steps"]:
                            st.write(f"{s['name']} · {s['detail']}")
                            time.sleep(0.25)
                        status.update(label="완료", state="complete" if result["verification"]["success"] else "error",
                                      expanded=False)
                    note = version_note(result) if result["changes"] else None
                    reply = (note + "\n\n" if note else "") + summary(result)
                    st.markdown(reply)
            ss["messages"].append({"role": "assistant", "content": reply})
            ss["results"].append(result)
    with result_col:
        st.subheader("결과", divider="blue")
        if ss["results"]:
            show_result(ss["results"][-1])
        else:
            st.info("코드를 넣으면 여기에 전후 비교, 바뀐 줄과 근거, 진행 과정이 나옵니다.", icon=":material/arrow_back:")


with convert_tab:
    {"start": start_screen, "confirm": confirm_screen, "chat": chat_screen}[ss["stage"]]()

# ---------------------------------------------------------------- 비교 (평가)
with compare_tab:
    st.info("일반 AI와 우리 챗봇의 비교 결과가 들어갈 자리입니다. 챗봇이 완성되면 같은 문제로 실험해서 채웁니다.",
            icon=":material/hourglass_empty:")
    cols = st.columns(3)
    for col, (name, desc) in zip(cols, [("성공률", "일반 AI vs 우리 챗봇"),
                                         ("난이도별", "쉬움 · 중간 · 어려움"),
                                         ("다시 고치기 효과", "1회차 → 최종")]):
        with col.container(border=True):
            st.markdown(f"**{name}**")
            st.caption(desc)
            st.metric("결과", "–")

# ---------------------------------------------------------------- 프로젝트 소개
with about_tab:
    st.subheader("옛 LangChain 코드를 최신으로, 근거와 검증까지", divider="gray")
    st.write("일반 AI는 옛 버전을 기억해서 틀린 코드를 주고, 틀린 줄도 모릅니다. "
             "이 챗봇은 최신 문서와 이사 목록에서 근거를 찾아 고치고, 실제로 실행해서 확인합니다.")
    st.markdown(
        "| 단계 | 하는 일 | 담당 |\n|---|---|---|\n"
        "| ① analyzer | 코드에서 import 경로 뽑기 | 3번 |\n"
        "| ② retriever | 이사 목록 · 문서에서 근거 찾기 | 2번 |\n"
        "| ③ rewriter | 근거를 보고 코드 다시 쓰기 | 3번 |\n"
        "| ④ verifier | 실행해서 확인, 실패하면 ②로 | 3번 |\n"
        "| ⑤ report | 결과 정리 | 미정 |\n"
        "| 연결 | 단계 잇기, 다시 할지 판단 | 1번 |\n"
        "| 화면 · 평가 | 보여 주기, 일반 AI와 비교 | 4번 |")
