"""문서 원문(MDX/Docusaurus 마크다운)에서 검색에 잡음이 되는 요소를 걷어낸다.

- 페이지 맨 위 "Documentation Index" 안내 블록, frontmatter, MDX import 문, `:::note` 표시
- 코드블록 여는 줄의 표시용 설정 (```bash pip theme={...} → ```bash) + 들여쓰기 정리
- 래퍼 태그(<CodeGroup>, <Tabs>, <div> 등)는 지우고, 제목이 있는 태그(<Tab title="X">)는 **X** 로
- 강조 상자(<Note>, <Tip>, <Callout> 등)는 태그만 벗기고 내용은 남긴다
코드블록 안쪽 내용은 들여쓰기 외에는 건드리지 않는다.
"""

import re

FENCE = re.compile(r"^(\s*)(`{3,}|~{3,})(.*)$")
TITLED_TAG = re.compile(r"<(Tab|Accordion|Step|Card|Update|Expandable)\b[^>]*?\b(?:title|label)=\"([^\"]+)\"[^>]*>")
PARAM_FIELD = re.compile(r"<ParamField\b[^>]*?\b(?:path|query|body|name)=\"([^\"]+)\"(?:[^>]*?\btype=\"([^\"]+)\")?[^>]*>")
JSX_TAG = re.compile(r"</?[A-Z][A-Za-z0-9]*\b[^>]*?/?>")
HTML_WRAPPER = re.compile(r"</?(div|span|details|summary|br|img|iframe|video|source|p|a)\b[^>]*?/?>", re.IGNORECASE)
MDX_IMPORT = re.compile(r"^import\s+.+\s+from\s+['\"].+['\"];?\s*$")
ADMONITION = re.compile(r"^:::\s*\w*.*$")
DOC_INDEX_BLOCK = re.compile(r"\A(?:>.*\n)+\n?")
FRONTMATTER = re.compile(r"\A---\n.*?\n---\n", re.DOTALL)


def _join_multiline_tags(lines: list[str]) -> list[str]:
    """여러 줄에 걸친 JSX 여는 태그(<Card\n  title=...\n>)를 한 줄로 합친다 (코드블록 밖에서만)."""
    out, buf, in_fence = [], None, None
    for line in lines:
        if buf is None:
            m = FENCE.match(line)
            if m and (in_fence is None or m.group(2).startswith(in_fence)):
                in_fence = None if in_fence else m.group(2)
                out.append(line)
                continue
            if in_fence is None and re.match(r"^\s*<[A-Za-z][^>]*$", line):
                buf = line.strip()
                continue
            out.append(line)
        else:
            buf += " " + line.strip()
            if ">" in line:
                out.append(buf)
                buf = None
    if buf is not None:
        out.append(buf)
    return out


def _clean_prose_line(line: str) -> str:
    line = line.strip()
    if MDX_IMPORT.match(line) or ADMONITION.match(line):
        return ""
    line = TITLED_TAG.sub(lambda m: f"**{m.group(2)}**", line)
    line = PARAM_FIELD.sub(lambda m: f"**{m.group(1)}**" + (f" (`{m.group(2)}`)" if m.group(2) else ""), line)
    line = JSX_TAG.sub("", line)
    line = HTML_WRAPPER.sub("", line)
    return line.strip()


def clean(text: str) -> str:
    text = text.replace("\r\n", "\n")
    text = DOC_INDEX_BLOCK.sub("", text)
    text = FRONTMATTER.sub("", text)
    out, fence, indent = [], None, 0
    for line in _join_multiline_tags(text.split("\n")):
        m = FENCE.match(line)
        if fence is None and m:
            fence, indent = m.group(2), len(m.group(1))
            lang = m.group(3).strip().split(" ")[0] if m.group(3).strip() else ""
            out.append(f"{fence}{lang}")
        elif fence is not None and m and m.group(2).startswith(fence) and not m.group(3).strip():
            out.append(fence)
            fence = None
        elif fence is not None:
            # CodeGroup/Tab 안에서 들어간 들여쓰기만큼 걷어낸다
            out.append(line[indent:] if line[:indent].strip() == "" else line.lstrip())
        else:
            out.append(_clean_prose_line(line))
    cleaned = "\n".join(out)
    return re.sub(r"\n{3,}", "\n\n", cleaned).strip() + "\n"
