"""대응표·최신 문서·구버전 가이드를 청크로 나누고 메타데이터를 붙여 chunks.jsonl 하나로 쓴다.

청크 레코드 공통 필드:
    chunk_id   대응표는 imap-… (state.py의 evidence_id와 동일), 메서드 대응표는 mmap-…, 문서는 doc-<해시>
               (페이지 경로 + 제목 경로 + 순번 기준이라 재수집해도 같은 위치면 같은 ID)
    source     import_map | method_map | latest_docs | migration_guide
    era        1.x | 0.3
    text       임베딩·검색에 쓰는 본문 (문서 청크는 "제목 > 섹션" 머리줄 포함)
    imports    청크 코드블록 안의 langchain/langgraph import 문
    packages   imports 의 최상위 패키지
"""

import hashlib
import json
import re
from collections import Counter

from . import (
    CHUNKS_PATH, IMPORT_MAP_PATH, LATEST_MANIFEST_PATH, MAX_CHARS, METHOD_MAP_PATH, MIGRATION_MANIFEST_PATH,
    MIGRATION_MAX_CHARS, MIGRATION_WHOLE_PAGE_MAX, MIN_CHARS, ROOT,
)
from .clean_mdx import FENCE, clean

HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*#*$")
FROM_IMPORT = re.compile(r"^\s*from\s+((?:langchain|langgraph)[\w.]*)\s+import\s+(\([^)]*\)|[^\n#]+)", re.MULTILINE)
PLAIN_IMPORT = re.compile(r"^\s*import\s+((?:langchain|langgraph)[\w.]*)", re.MULTILINE)
CODE_BLOCK = re.compile(r"^(`{3,}|~{3,})[^\n]*\n(.*?)^\1\s*$", re.MULTILINE | re.DOTALL)


def load_jsonl(path):
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def doc_chunk_id(source: str, path: str, section: str, n: int) -> str:
    return "doc-" + hashlib.sha1(f"{source}|{path}|{section}|{n}".encode()).hexdigest()[:12]


# ---------------------------------------------------------------- import 추출

def extract_imports(text: str) -> list[str]:
    found = []
    for code in (m.group(2) for m in CODE_BLOCK.finditer(text)):
        for module, names in FROM_IMPORT.findall(code):
            names = " ".join(names.strip("()").split())
            names = ", ".join(n.strip() for n in names.split(",") if n.strip())
            found.append(f"from {module} import {names}")
        for module in PLAIN_IMPORT.findall(code):
            found.append(f"import {module}")
    return list(dict.fromkeys(found))


def packages_of(imports: list[str]) -> list[str]:
    return sorted({imp.split()[1].split(".")[0] for imp in imports})


# ---------------------------------------------------------------- 문서 분할

def split_sections(text: str, max_level: int) -> list[tuple[list[str], str]]:
    """코드블록 밖의 제목(# ~ max_level)에서 자른다. [(제목 경로, 본문)]"""
    sections, path, body, fence = [], [], [], None
    for line in text.split("\n"):
        m = FENCE.match(line)
        if m:
            if fence is None:
                fence = m.group(2)
            elif m.group(2).startswith(fence) and not m.group(3).strip():
                fence = None
        h = HEADING.match(line) if fence is None else None
        if h and len(h.group(1)) <= max_level:
            if "\n".join(body).strip():
                sections.append((list(path), "\n".join(body).strip()))
            level = len(h.group(1))
            path = path[: level - 1] + [""] * max(0, level - 1 - len(path)) + [h.group(2).strip()]
            body = []
        else:
            body.append(line)
    if "\n".join(body).strip():
        sections.append((list(path), "\n".join(body).strip()))
    return [([p for p in hp if p], b) for hp, b in sections]


def blocks(text: str) -> list[str]:
    """빈 줄로 나눈 문단. 코드블록은 통째로 한 덩어리."""
    out, cur, fence = [], [], None
    for line in text.split("\n"):
        m = FENCE.match(line)
        if m:
            if fence is None:
                fence = m.group(2)
            elif m.group(2).startswith(fence) and not m.group(3).strip():
                fence = None
        if fence is None and not m and not line.strip():
            if cur:
                out.append("\n".join(cur))
                cur = []
        else:
            cur.append(line)
    if cur:
        out.append("\n".join(cur))
    return out


OUTPUT_LANGS = {"", "text", "output", "console", "shell-session", "json"}  # 문서의 긴 json 블록은 응답 예시
OUTPUT_START = re.compile(r"^\s*(page_content=|\[?Document\(|\{'|\[\{'|={5,}|-{5,})")
OUTPUT_KEEP = 800


def shrink_outputs(text: str) -> str:
    """실행 결과 덤프(코드가 아닌 긴 블록)는 앞부분만 남긴다. 실제 예제 코드는 그대로 둔다."""
    def repl(m: re.Match) -> str:
        fence, lang, body = m.group(1), m.group(2).strip(), m.group(3)
        is_output = lang in OUTPUT_LANGS or OUTPUT_START.match(body)
        if not is_output or len(body) <= OUTPUT_KEEP * 2:
            return m.group(0)
        return f"{fence}{lang}\n{body[:OUTPUT_KEEP].rstrip()}\n… (output truncated, originally {len(body)} chars)\n{fence}"
    return re.sub(r"^(`{3,}|~{3,})([^\n]*)\n(.*?)^\1[ \t]*$", repl, text, flags=re.MULTILINE | re.DOTALL)


def split_table(block: str, max_chars: int) -> list[str]:
    """마크다운 표를 행 단위로 나누고 조각마다 머리행(제목+구분선)을 반복한다."""
    lines = block.split("\n")
    head, rows = lines[:2], lines[2:]
    parts, cur = [], []
    for row in rows:
        if cur and len("\n".join(head + cur + [row])) > max_chars:
            parts.append("\n".join(head + cur))
            cur = []
        cur.append(row)
    if cur:
        parts.append("\n".join(head + cur))
    return parts


def pack(text: str, max_chars: int) -> list[str]:
    """문단을 max_chars 안으로 묶는다. 표는 행 단위로 나누고, 더 큰 코드블록은 그대로 둔다."""
    if len(text) <= max_chars:
        return [text]
    units = []
    for b in blocks(text):
        is_table = all(l.lstrip().startswith("|") for l in b.split("\n")) and b.count("\n") >= 2
        units.extend(split_table(b, max_chars) if is_table and len(b) > max_chars else [b])
    parts, cur = [], ""
    for b in units:
        if cur and len(cur) + len(b) + 2 > max_chars:
            parts.append(cur)
            cur = b
        else:
            cur = f"{cur}\n\n{b}" if cur else b
    if cur:
        parts.append(cur)
    return parts


def merge_small(pieces: list[dict], min_chars: int) -> list[dict]:
    """min_chars 미만 조각은 다음 조각 앞에 붙인다 (마지막이면 이전 조각 뒤에)."""
    out, carry = [], None
    for p in pieces:
        if carry:
            p = {**p, "section": carry["section"],
                 "body": f"{carry['heading_line']}{carry['body']}\n\n{p['heading_line']}{p['body']}",
                 "heading_line": ""}
            carry = None
        if len(p["body"]) < min_chars:
            carry = p
        else:
            out.append(p)
    if carry:
        if out:
            last = out[-1]
            out[-1] = {**last, "body": f"{last['body']}\n\n{carry['heading_line']}{carry['body']}"}
        else:
            out.append(carry)
    return out


def chunk_page(text: str, title: str, *, max_level: int, max_chars: int, min_chars: int) -> list[dict]:
    pieces = []
    for hp, body in split_sections(text, max_level):
        section_path = hp[1:] if hp and hp[0] == title else hp  # h1(페이지 제목)은 머리줄에 따로
        section = " > ".join(section_path)
        heading_line = f"## {section_path[-1]}\n\n" if section_path else ""
        for part in pack(body, max_chars):
            pieces.append({"section": section, "body": part, "heading_line": heading_line})
    return merge_small(pieces, min_chars)


def doc_records(manifest_path, source: str) -> list[dict]:
    records = []
    for page in load_jsonl(manifest_path):
        text = shrink_outputs(clean((ROOT / page["file"]).read_text(encoding="utf-8")))
        title = page.get("title") or page["path"]
        if source == "migration_guide":
            if len(text) <= MIGRATION_WHOLE_PAGE_MAX:
                pieces = [{"section": "", "body": text, "heading_line": ""}]
            else:
                pieces = chunk_page(text, title, max_level=2, max_chars=MIGRATION_MAX_CHARS, min_chars=MIN_CHARS)
            url, era, extra = page["source_url"], page["era"], {"group": page["group"]}
        else:
            pieces = chunk_page(text, title, max_level=3, max_chars=MAX_CHARS, min_chars=MIN_CHARS)
            url, era, extra = page["url"], "1.x", {"doc_section": page.get("section")}

        seen = Counter()
        for p in pieces:
            n = seen[p["section"]]
            seen[p["section"]] += 1
            header = " > ".join(x for x in [title, p["section"]] if x)
            body = p["body"] if p["body"].lstrip().startswith("#") else p["heading_line"] + p["body"]
            chunk_text = f"{header}\n\n{body.strip()}"
            imports = extract_imports(chunk_text)
            records.append({
                "chunk_id": doc_chunk_id(source, page["path"], p["section"], n),
                "source": source,
                "era": era,
                "text": chunk_text,
                "url": url,
                "path": page["path"],
                "title": title,
                "section": p["section"],
                "imports": imports,
                "packages": packages_of(imports),
                "has_code": "```" in chunk_text,
                "chars": len(chunk_text),
                **extra,
            })
    return records


# ---------------------------------------------------------------- 대응표

def as_import(path: str | None, granularity: str) -> str | None:
    if path is None:
        return None
    if granularity == "module":
        return f"import {path}"
    module, _, name = path.rpartition(".")
    return f"from {module} import {name}"


def import_map_records() -> list[dict]:
    records = []
    for r in load_jsonl(IMPORT_MAP_PATH):
        old_imp, new_imp = as_import(r["old"], r["granularity"]), as_import(r["new"], r["granularity"])
        lines = [f"Legacy import: {old_imp}",
                 f"LangChain 1.x import: {new_imp} ({r['kind']})" if new_imp else "LangChain 1.x import: none (unresolved)"]
        dep = ", ".join(f"{k} {r[k]}" for k in ("since", "removal") if r.get(k))
        if dep:
            lines.append(f"Deprecated: {dep}")
        if r.get("alternative"):
            lines.append(f"Alternative: {r['alternative']}")
        if r.get("import_status") and r["import_status"] != "ok":
            lines.append(f"Import check: {r['import_status']}")
        imports = [i for i in (old_imp, new_imp) if i]
        text = "\n".join(lines)
        records.append({
            "chunk_id": r["id"],
            "source": "import_map",
            "era": "1.x",
            "text": text,
            "old": r["old"],
            "new": r["new"],
            "kind": r["kind"],
            "import_status": r["import_status"],
            "seen_in": r["seen_in"],
            "imports": imports,
            "packages": packages_of(imports),
            "has_code": False,
            "chars": len(text),
        })
    return records


def method_map_records() -> list[dict]:
    status_text = {
        "removed": "removed in LangChain 1.x (calling it raises an error)",
        "deprecated": "deprecated (still works only in the legacy/classic class)",
        "exists": "still available",
    }
    records = []
    for r in load_jsonl(METHOD_MAP_PATH):
        owner = r["class_path"] or ", ".join(r["classes"])
        lines = [f"Legacy method call: {r['call']} on {r['class']} ({owner})",
                 f"LangChain 1.x status: {status_text[r['status_1x']]}"]
        if r.get("alternative"):
            lines.append(f"Replacement: {r['alternative']}")
        if r.get("removal"):
            lines.append(f"Removal: {r['removal']}")
        if r.get("note"):
            lines.append(f"Note: {r['note']}")
        text = "\n".join(lines)
        records.append({
            "chunk_id": r["id"],
            "source": "method_map",
            "era": "1.x",
            "text": text,
            "class": r["class"],
            "classes": r["classes"],
            "method": r["method"],
            "status_1x": r["status_1x"],
            "alternative": r.get("alternative"),
            "doc_refs": r.get("doc_refs", []),
            "imports": [],
            "packages": [],
            "has_code": False,
            "chars": len(text),
        })
    return records


def main():
    chunks = import_map_records()
    chunks += method_map_records()
    chunks += doc_records(LATEST_MANIFEST_PATH, "latest_docs")
    chunks += doc_records(MIGRATION_MANIFEST_PATH, "migration_guide")

    ids = Counter(c["chunk_id"] for c in chunks)
    dup = [i for i, n in ids.items() if n > 1]
    if dup:
        raise SystemExit(f"duplicate chunk_id: {len(dup)} ids, e.g. {dup[:5]}")

    CHUNKS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CHUNKS_PATH.open("w", encoding="utf-8") as f:
        for c in chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")

    print(f"{CHUNKS_PATH.relative_to(ROOT)}: {len(chunks)} chunks")
    for source in ("import_map", "method_map", "latest_docs", "migration_guide"):
        sizes = sorted(c["chars"] for c in chunks if c["source"] == source)
        print(f"  {source}: {len(sizes)}개, 길이 중간값 {sizes[len(sizes) // 2]}, "
              f"최대 {sizes[-1]}, {MAX_CHARS}자 초과 {sum(s > MAX_CHARS for s in sizes)}개")


if __name__ == "__main__":
    main()
