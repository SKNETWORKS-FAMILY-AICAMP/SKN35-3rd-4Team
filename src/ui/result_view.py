"""결과 패널 그림 (HTML): 전후 비교 · 바뀐 줄 · 근거 · 안내. 화면은 st.html 로 그대로 넣는다."""

import difflib
import html

SOURCE = {  # 근거 출처 → (이름, 설명)
    "import_map": ("import 대응표", "2번이 PyPI 패키지 코드에서 뽑은 옛 경로 → 1.x 경로 표 (실제로 import 해 보고 만든 것)"),
    "method_map": ("메서드 대응표", "옛 메서드(.run · .predict 등) → 새 메서드 표"),
    "latest_docs": ("최신 공식 문서", "LangChain 공식 문서 (docs.langchain.com)"),
    "migration_guide": ("옛 마이그레이션 가이드", "0.3.30 시절 공식 마이그레이션 가이드"),
    "version_map": ("버전별 도구 목록", "버전마다 실제로 있는 기능 목록을 비교"),
    "sample": ("예시", "화면 시험용 예시 근거 (팀 데이터가 없을 때)"),
}
KIND = {  # 근거 종류 → 쉬운 설명
    "native": "목표 버전에 같은 기능이 있고, 위치(import 경로)만 바뀌었어요",
    "moved": "목표 버전에서 위치가 바뀌었어요",
    "same": "목표 버전에도 같은 위치에 그대로 있어요",
    "classic_fallback": "1.x 에서는 langchain_classic(옛 창고)에만 남아 있어요. 대안이 있으면 최신 방식으로 바꿔요",
    "unresolved": "목표 버전에서 같은 기능을 찾지 못했어요",
    "deprecated": "아직 동작하지만 없어질 예정인 옛 메서드예요",
    "removed": "목표 버전에서 없어진 메서드예요",
    "exists": "목표 버전에서도 그대로 쓸 수 있어요",
}

CSS = """
<style>
.rv { font-family: inherit; --add: rgba(46,160,67,.16); --add-b: #2ea043; --del: rgba(248,81,73,.15); --del-b: #f85149;
      --card: rgba(127,127,127,.07); --line: rgba(127,127,127,.22); --sub: rgba(127,127,127,1); }
.rv .mono { font-family: Consolas, 'SFMono-Regular', Menlo, monospace; font-size: 13px; }
.rv .diff { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.rv .pane { border: 1px solid var(--line); border-radius: 12px; overflow: hidden; }
.rv .pane h4 { margin: 0; padding: 8px 12px; font-size: 13px; border-bottom: 1px solid var(--line); background: var(--card); }
.rv .ln { display: flex; white-space: pre-wrap; word-break: break-all; padding: 1px 10px 1px 0; min-height: 20px; }
.rv .ln .no { width: 34px; flex: none; text-align: right; padding-right: 10px; color: var(--sub); opacity: .55; user-select: none; }
.rv .ln.del { background: var(--del); box-shadow: inset 3px 0 var(--del-b); }
.rv .ln.add { background: var(--add); box-shadow: inset 3px 0 var(--add-b); }
.rv .legend { display: flex; gap: 14px; font-size: 12.5px; color: var(--sub); margin: 8px 2px 0; }
.rv .sw { display: inline-block; width: 10px; height: 10px; border-radius: 3px; margin-right: 5px; vertical-align: -1px; }
.rv .card { border: 1px solid var(--line); border-radius: 14px; padding: 12px 14px; margin: 0 0 10px; background: var(--card);
            animation: rvIn .45s ease both; }
@keyframes rvIn { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: none; } }
.rv .head { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-bottom: 8px; }
.rv .num { width: 24px; height: 24px; border-radius: 50%; background: #0071e3; color: #fff; font-size: 12.5px; font-weight: 700;
           display: inline-flex; align-items: center; justify-content: center; }
.rv .chip { font-size: 12px; padding: 2px 9px; border-radius: 999px; border: 1px solid var(--line); }
.rv .chip.id { font-family: Consolas, monospace; } .rv .chip.k { background: rgba(0,113,227,.10); border-color: transparent; color: #2f7fe0; }
.rv .row { border-radius: 8px; padding: 5px 10px; margin: 3px 0; white-space: pre-wrap; word-break: break-all; }
.rv .row.del { background: var(--del); } .rv .row.add { background: var(--add); }
.rv .row b { opacity: .7; margin-right: 6px; }
.rv .why { font-size: 13.5px; margin-top: 8px; }
.rv .chk { display: grid; grid-template-columns: repeat(auto-fill, minmax(230px, 1fr)); gap: 8px; }
.rv .ck { border: 1px solid var(--line); border-radius: 12px; padding: 10px 12px; background: var(--card); animation: rvIn .45s ease both; }
.rv .ck .t { font-weight: 700; font-size: 14px; } .rv .ck .d { font-size: 12.5px; color: var(--sub); margin-top: 2px; }
.rv .st { float: right; font-size: 12px; font-weight: 700; padding: 1px 8px; border-radius: 999px; }
.rv .st.ok { background: var(--add); color: #2ea043; } .rv .st.warn { background: rgba(255,159,10,.16); color: #d98200; }
.rv .st.bad { background: var(--del); color: #f85149; } .rv .msg { font-size: 12.5px; margin-top: 6px; }
.rv .sum { display: flex; gap: 10px; margin-bottom: 10px; flex-wrap: wrap; }
.rv .sum div { border-radius: 12px; padding: 8px 14px; background: var(--card); border: 1px solid var(--line); font-size: 13px; }
.rv .sum b { font-size: 20px; margin-right: 6px; }
.rv .src { font-size: 12.5px; color: var(--sub); margin: 2px 0 6px; }
.rv .path { font-size: 13px; margin: 4px 0; } .rv a { color: #2f7fe0; text-decoration: none; }
.rv details { margin-top: 6px; font-size: 12.5px; } .rv details pre { white-space: pre-wrap; margin: 6px 0 0; color: var(--sub); }
.rv .empty { color: var(--sub); font-size: 14px; padding: 8px 2px; }
@media (max-width: 900px) { .rv .diff { grid-template-columns: 1fr; } }
</style>
"""
e = html.escape


def _lines(text: str, marks: set[int], cls: str) -> str:
    return "".join(f'<div class="ln {cls if i in marks else ""}"><span class="no">{i + 1}</span>{e(t) or " "}</div>'
                   for i, t in enumerate(text.splitlines()))


def diff_html(old: str, new: str) -> str:
    """양쪽 나란히, 지운 줄 빨강 · 새 줄 초록."""
    a, b = old.splitlines(), new.splitlines()
    dels, adds = set(), set()
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if tag in ("replace", "delete"):
            dels.update(range(i1, i2))
        if tag in ("replace", "insert"):
            adds.update(range(j1, j2))
    return (CSS + '<div class="rv"><div class="diff">'
            f'<div class="pane"><h4>변경 전</h4><div class="mono">{_lines(old, dels, "del")}</div></div>'
            f'<div class="pane"><h4>변경 후</h4><div class="mono">{_lines(new, adds, "add")}</div></div></div>'
            f'<div class="legend"><span><span class="sw" style="background:#f85149"></span>지운 줄 {len(dels)}</span>'
            f'<span><span class="sw" style="background:#2ea043"></span>새 줄 {len(adds)}</span></div></div>')


def _ids(c: dict) -> list[str]:
    return [i.strip() for i in (c.get("evidence_id") or "").split(",") if i.strip()]


def changes_html(changes: list[dict], evidences: list[dict] | None = None) -> str:
    """변경 사항 카드: 옛 줄(빨강) → 새 줄(초록), 바꾼 까닭, 근거 출처 이름."""
    by_id = {ev.get("evidence_id"): ev.get("source") for ev in evidences or []}
    sources = {k: [by_id.get(i) for i in _ids(c)] for k, c in enumerate(changes)}
    if not changes:
        return CSS + '<div class="rv"><div class="empty">바뀐 줄이 없어요.</div></div>'
    cards = []
    for n, c in enumerate(changes, 1):
        old, new = c.get("old") or "", c.get("new") or ""
        rows = ""
        if old and old != "(새 줄)":
            rows += f'<div class="row del mono"><b>−</b>{e(old)}</div>'
        if new and new != "(삭제)":
            rows += f'<div class="row add mono"><b>+</b>{e(new)}</div>'
        if new == "(삭제)":
            rows += '<div class="src">이 줄은 지웠어요</div>'
        names = list(dict.fromkeys(SOURCE.get(src, (src, ""))[0] for src in (sources or {}).get(n - 1, []) if src))
        if not names and c.get("source"):
            names = [SOURCE.get(c["source"], (c["source"], ""))[0]]
        chips = "".join(f'<span class="chip k">{e(x)}</span>' for x in names) or (
            '<span class="chip">근거 없음</span>' if not _ids(c) else "")
        why = f'<div class="why">{e(c["reason"])}</div>' if c.get("reason") else ""
        alt = f'<div class="src">대안: <span class="mono">{e(c["alternative"])}</span></div>' if c.get("alternative") else ""
        cards.append(f'<div class="card" style="animation-delay:{(n - 1) * 0.06:.2f}s"><div class="head">'
                     f'<span class="num">{n}</span>{chips}</div>{rows}{why}{alt}</div>')
    return CSS + '<div class="rv">' + "".join(cards) + "</div>"


def evidence_html(evidences: list[dict], changes: list[dict]) -> str:
    """근거 카드: 출처 · 옛 경로 → 새 경로 · 종류 설명 · 문서 링크 · 원문 일부 · 이 근거로 바뀐 줄."""
    used = {}
    for n, c in enumerate(changes, 1):
        for i in _ids(c):
            used.setdefault(i, []).append(n)
    if not evidences:                                    # 임시 결과: 바뀐 줄에 적힌 근거만으로 만든다
        evidences = [{"evidence_id": i, "source": next((c.get("source") for c in changes if i in _ids(c)), None),
                      "kind": next((c.get("kind") for c in changes if i in _ids(c)), None)} for i in used]
    if not evidences:
        return CSS + '<div class="rv"><div class="empty">근거가 없어요.</div></div>'
    cards = []
    for k, ev in enumerate(sorted(evidences, key=lambda x: min(used.get(x.get("evidence_id"), [99])))):
        eid = ev.get("evidence_id", "")
        name, desc = SOURCE.get(ev.get("source"), (ev.get("source") or "근거", ""))
        lines = used.get(eid)
        body = f'<div class="src">{e(desc)}</div>' if desc else ""
        if ev.get("old") or ev.get("new"):
            body += (f'<div class="path mono">{e(ev.get("old") or "")} <b>→</b> '
                     f'{e(ev.get("new") or "(목표 버전에 없음)")}</div>')
        if ev.get("kind") in KIND:
            body += f'<div class="path">{e(KIND[ev["kind"]])}</div>'
        if ev.get("alternative"):
            body += f'<div class="path">대안: <span class="mono">{e(ev["alternative"])}</span></div>'
        if ev.get("title") or ev.get("url"):
            title = " · ".join(x for x in (ev.get("title"), ev.get("section")) if x) or ev.get("url")
            link = f'<a href="{e(ev["url"])}" target="_blank">{e(title)} ↗</a>' if ev.get("url") else e(title)
            body += f'<div class="path">문서: {link}</div>'
        if ev.get("text"):
            body += f'<details><summary>근거 원문 보기</summary><pre>{e(ev["text"][:700])}</pre></details>'
        tail = f'변경 사항 {", ".join(map(str, lines))}번의 근거' if lines else "검색됐지만 변경에는 쓰이지 않음"
        cards.append(f'<div class="card" style="animation-delay:{k * 0.06:.2f}s"><div class="head">'
                     f'<span class="chip k">{e(name)}</span>'
                     f'<span class="src" style="margin:0">{tail}</span></div>{body}</div>')
    return CSS + '<div class="rv">' + "".join(cards) + "</div>"


CHECKS = [  # (이름, 설명, 오류 · 경고 종류) — 3번 verifier 11가지
    ("문법", "파이썬 문법이 맞는지", {"syntax_error"}),
    ("근거 확인", "이번에 보여 준 근거만 썼는지", {"missing_evidence", "evidence_not_shown", "unknown_evidence_id"}),
    ("변경 기록", "기록 없이 바뀐 줄(환각)이 없는지", {"old_line_mismatch", "change_not_applied", "unrecorded_change"}),
    ("남은 옛 import", "옛 경로가 남지 않았는지", {"legacy_import_remaining", "no_1x_path"}),
    ("import 존재", "새 경로가 목표 버전에 정말 있는지", {"import_failed", "ungrounded_import", "install_required",
                                                 "import_unverified", "import_not_in_evidence"}),
    ("남은 옛 메서드", ".run() 같은 옛 호출이 남지 않았는지", {"legacy_method_remaining"}),
    ("안 쓰는 import", "필요 없는 import가 남지 않았는지", {"unused_import"}),
    ("반환값 보존", "결과 모양(문자열 등)을 잃지 않았는지", {"return_type_changed"}),
    ("정의 안 된 이름", "실행하면 NameError가 나지 않는지", {"undefined_name"}),
    ("출력 꺼내기", "결과를 ['text']처럼 잘못 꺼내지 않는지", {"invoke_output_subscript"}),
    ("체인 입출력 키", "체인의 입력 · 출력 키가 맞는지", {"chain_io_key"}),
]


def checks_html(result: dict) -> str:
    """검사 결과: 11가지를 통과 · 경고 · 실패로."""
    ck = result.get("checks") or {}
    if not ck.get("done"):
        return CSS + '<div class="rv"><div class="empty">임시 결과라 검사 정보가 없어요. 팀 챗봇에 연결되면 11가지 검사 결과가 나와요.</div></div>'
    errs, warns = ck.get("errors") or [], ck.get("warnings") or []
    known = set().union(*(t for _, _, t in CHECKS))
    items, n_ok, n_warn, n_bad = [], 0, 0, 0
    for k, (name, desc, types) in enumerate(CHECKS, 1):
        bad = [x for x in errs if x.get("type") in types]
        warn = [x for x in warns if x.get("type") in types]
        st, label = ("bad", "실패") if bad else (("warn", "경고") if warn else ("ok", "통과"))
        n_ok, n_warn, n_bad = n_ok + (st == "ok"), n_warn + (st == "warn"), n_bad + (st == "bad")
        msg = "".join(f'<div class="msg">· {e(x.get("message", ""))}</div>' for x in (bad + warn)[:3])
        items.append(f'<div class="ck" style="animation-delay:{(k - 1) * 0.04:.2f}s"><span class="st {st}">{label}</span>'
                     f'<div class="t">{k}. {e(name)}</div><div class="d">{e(desc)}</div>{msg}</div>')
    other = [x for x in errs + warns if x.get("type") not in known]
    extra = "".join(f'<div class="msg">· {e(x.get("message", ""))}</div>' for x in other[:3])
    v = result["verification"]
    head = (f'<div class="sum"><div><b>{n_ok}</b>통과</div><div><b>{n_warn}</b>경고</div><div><b>{n_bad}</b>실패</div>'
            f'<div><b>{v["attempts"]}</b>회 시도</div></div>')
    note = '<div class="src" style="margin-top:10px">마지막 시도 기준 · 오류는 다시 고칠 이유가 되고, 경고는 결과에 표시만 해요.</div>'
    return CSS + f'<div class="rv">{head}<div class="chk">{"".join(items)}</div>' + (
        f'<div class="card" style="margin-top:10px"><div class="t">그 밖의 메시지</div>{extra}</div>' if extra else "") + note + "</div>"


def report_md(result: dict) -> str:
    """내려받기용 변경 리포트 (마크다운)."""
    v = result["verification"]
    src = result.get("source_version") or "?"
    out = [f"# LangChain 버전 변경 리포트", "", f"- 버전: {src} → {result['target_version']}",
           f"- 검사: {'통과' if v['success'] else '실패'} ({v['attempts']}회 시도)", ""]
    if result.get("install_packages"):
        out += ["## 설치할 패키지", "", "```bash", "pip install " + " ".join(result["install_packages"]), "```", ""]
    out += ["## 변경 사항", ""]
    for n, c in enumerate(result["changes"], 1):
        out += [f"### {n}. {c.get('reason', '')}".rstrip(), "", "```diff"]
        if c.get("old") and c["old"] != "(새 줄)":
            out.append(f"- {c['old']}")
        if c.get("new") and c["new"] != "(삭제)":
            out.append(f"+ {c['new']}")
        out += ["```", ""]
    if result.get("unresolved"):
        out += ["## 못 바꾼 줄", ""] + [f"- `{u.get('code', '')}`: {u.get('reason', '')}" for u in result["unresolved"]] + [""]
    out += ["## 바뀐 코드", "", "```python", result["migrated_code"].rstrip(), "```", ""]
    return "\n".join(out)


def notes_html(result: dict) -> str | None:
    """안내: 못 바꾼 줄 · 설치할 패키지 · 그래프 안내 · 경고. 없으면 None."""
    parts = []
    for u in result.get("unresolved") or []:
        parts.append(f'<div class="card"><div class="head"><span class="chip" style="color:#f85149">못 바꾼 줄</span></div>'
                     f'<div class="row del mono">{e(u.get("code", ""))}</div><div class="why">{e(u.get("reason", ""))}</div></div>')
    if result.get("install_packages"):
        parts.append('<div class="card"><div class="head"><span class="chip k">설치할 패키지</span></div>'
                     f'<div class="row mono">pip install {e(" ".join(result["install_packages"]))}</div></div>')
    for n in result.get("notes") or []:
        parts.append(f'<div class="card"><div class="head"><span class="chip k">안내</span></div><div>{e(n)}</div></div>')
    for w in result.get("warnings") or []:
        parts.append(f'<div class="card"><div class="head"><span class="chip">검사 경고</span></div><div class="src">{e(w)}</div></div>')
    return CSS + '<div class="rv">' + "".join(parts) + "</div>" if parts else None
