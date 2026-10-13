"""시작 화면의 버전 마인드맵 (streamlit-agraph, 클릭 가능).

LangChain(위) → 옛 버전(한 줄) → 고른 버전의 영역(아래) 순서의 나무 모양.
버전 상자를 클릭하면 agraph 가 그 상자의 id 를 돌려주고, app.py 가 고른 버전으로 삼는다 (새로고침 없음).
상자 글자: 기능 수와 1.x에서 최신 위치 / 옛 창고(classic) 비율
"""

from streamlit_agraph import Config, Edge, Node

from .versions import SUMMARY

INK, GREEN, ORANGE, BLUE = "#18202B", "#1B7A43", "#B8501F", "#2457C5"
AUTO_ID = "auto"


def _color(bg: str, border: str) -> dict:
    return {"background": bg, "border": border,
            "highlight": {"background": bg, "border": ORANGE}, "hover": {"background": bg, "border": ORANGE}}


def _box(nid: str, label: str, bg: str, border: str, size: int, font_color: str = INK, width: int = 1, **kw) -> Node:
    return Node(id=nid, label=label, shape="box", color=_color(bg, border), borderWidth=width,
                borderWidthSelected=width, margin=12, shapeProperties={"borderRadius": 8},
                font={"size": size, "color": font_color, "face": "Malgun Gothic, Noto Sans KR, sans-serif",
                      "multi": "html", "bold": {"size": size + 4}}, **kw)


def _share(kinds: dict) -> str:
    total = sum(kinds.values()) or 1
    return (f"최신 {kinds.get('native', 0) * 100 // total}% · "
            f"classic {kinds.get('classic_fallback', 0) * 100 // total}%")


def graph(selected: str | None, auto: bool = False) -> tuple[list[Node], list[Edge], Config]:
    nodes = [_box("root", "<b>LangChain</b>\n옛 코드", BLUE, BLUE, 16, "#FFFFFF", title="옛 버전을 골라 주세요")]
    edges = []
    for v in SUMMARY["versions"]:
        on = v["version"] == selected
        nid = v["version"]
        nodes.append(_box(nid, f"<b>{nid}</b>\n기능 {v['total']:,}\n{_share(v['kinds'])}",
                          "#FFE7C2" if on else "#E4ECFB", ORANGE if on else "#C9D2DD", 14,
                          width=3 if on else 1, title=f"LangChain {nid} 고르기"))
        edges.append(Edge("root", nid, color=ORANGE if on else "#9AA5B4", width=3 if on else 1))
        if on:
            for a in v["areas"][:6]:
                aid = f"{nid}/{a['name']}"
                nodes.append(_box(aid, f"<b>{a['name']}</b>\n{a['total']:,}\n{_share(a['kinds'])}",
                                  "#FFFFFF", "#C9D2DD", 12, title=f"{a['name']} 영역 기능 {a['total']:,}개"))
                edges.append(Edge(nid, aid, color="#9AA5B4"))
    nodes.append(_box(AUTO_ID, "<b>모르겠어요</b>\n자동 감지", "#FFE7C2" if auto else "#F1F3F6",
                      ORANGE if auto else "#9AA5B4", 14, width=3 if auto else 1, title="코드를 보고 버전 짐작하기"))
    edges.append(Edge("root", AUTO_ID, color=ORANGE if auto else "#9AA5B4", dashes=True, width=3 if auto else 1))
    if selected or auto:
        nodes.append(_box("target", f"<b>LangChain 1.x</b>\n최신 {SUMMARY['latest']['langchain']}",
                          GREEN, GREEN, 15, "#FFFFFF", title="목표 버전"))
        edges.append(Edge(selected or AUTO_ID, "target", color=GREEN, dashes=True, width=2, label="변환",
                          font={"color": GREEN, "size": 13, "strokeWidth": 0}))
    config = Config(height=470 if (selected or auto) else 300, width=1000, directed=True, physics=False,
                    hierarchical=True, direction="UD", sortMethod="directed", levelSeparation=120,
                    nodeSpacing=185, treeSpacing=140,
                    interaction={"dragNodes": False, "dragView": True, "zoomView": True, "hover": True,
                                 "keyboard": False, "zoomSpeed": 0.6,
                                 "selectConnectedEdges": False})
    config.width = "100%"    # 화면 폭에 맞춤 (Config 는 px 로만 받으므로 직접 바꿈)
    return nodes, edges, config


def clicked_version(node_id: str | None) -> str | None:
    """클릭한 상자 id → 옛 버전 (영역 상자를 누르면 그 영역의 버전). 버전이 아니면 None."""
    if not node_id:
        return None
    if node_id == AUTO_ID:
        return AUTO_ID
    version = node_id.split("/")[0]
    return version if any(v["version"] == version for v in SUMMARY["versions"]) else None
