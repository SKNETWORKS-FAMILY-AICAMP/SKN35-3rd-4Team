"""docs.langchain.com Python 인덱스 + 통합 분류 index를 따라 `.md` 원문을 받는다.

1. PYTHON_INDEX(llms.txt 하위 인덱스)에서 `[제목](url): 설명` 행과 상위 제목(섹션)을 읽는다.
2. oss/python/ 아래이면서 제외 영역(deepagents, langgraph 등)이 아닌 페이지만 남긴다.
3. 통합 상세 페이지(ChatOpenAI, Chroma 등)는 인덱스에 없으므로
   integrations/{분류}/index.md 의 링크를 따라 추가한다.
"""

import hashlib
import json
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

from . import (
    DOCS_BASE, EXCLUDE_NAME_PARTS, EXCLUDE_SEGMENTS, INCLUDE_PREFIX, INTEGRATION_CATEGORIES,
    LATEST_DIR, LATEST_MANIFEST_PATH, PYTHON_INDEX, REQUEST_DELAY_SEC, ROOT, USER_AGENT,
)

INDEX_LINE = re.compile(r"^- \[([^\]]+)\]\((https://docs\.langchain\.com/[^)]+?)\)(?::\s*(.*))?$")
HEADING = re.compile(r"^(#{2,6})\s+(.+)$")
INTEGRATION_LINK = re.compile(r"\]\((?:https://docs\.langchain\.com)?/(oss/python/integrations/([a-z_-]+)/([^)#\s/]+))\)")
TITLE = re.compile(r"^#\s+(.+)$", re.MULTILINE)


def fetch(url: str, retries: int = 3) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.read().decode("utf-8")
        except (urllib.error.URLError, TimeoutError) as e:
            if isinstance(e, urllib.error.HTTPError) and e.code == 404:
                raise
            if attempt == retries - 1:
                raise
            time.sleep(2 ** attempt)
    raise RuntimeError("unreachable")


def doc_path(url: str) -> str:
    """https://docs.langchain.com/oss/python/x.md → oss/python/x"""
    path = url.removeprefix(DOCS_BASE + "/").split("#")[0]
    return path.removesuffix(".md")


def wanted(path: str) -> bool:
    if not path.startswith(INCLUDE_PREFIX):
        return False
    parts = path.split("/")
    if EXCLUDE_SEGMENTS & set(parts):
        return False
    return not any(p in parts[-1] for p in EXCLUDE_NAME_PARTS)


def parse_index(text: str) -> list[dict]:
    pages, headings = [], {}
    for line in text.splitlines():
        if m := HEADING.match(line):
            level = len(m.group(1))
            headings = {k: v for k, v in headings.items() if k < level}
            headings[level] = m.group(2).strip()
        elif m := INDEX_LINE.match(line.strip()):
            pages.append({
                "path": doc_path(m.group(2)),
                "title": m.group(1),
                "description": m.group(3) or None,
                "section": " / ".join(headings[k] for k in sorted(headings)),
                "source": "index",
            })
    return pages


def integration_pages(category: str) -> list[dict]:
    text = fetch(f"{DOCS_BASE}/oss/python/integrations/{category}/index.md")
    pages = []
    for path, cat, slug in INTEGRATION_LINK.findall(text):
        if cat == category and slug != "index":
            pages.append({"path": path, "title": None, "description": None,
                          "section": f"Integrations / {category}", "source": "integration_index"})
    return pages


def collect_targets() -> list[dict]:
    targets: dict[str, dict] = {}
    for page in parse_index(fetch(PYTHON_INDEX)):
        if wanted(page["path"]):
            targets.setdefault(page["path"], page)
    for category in INTEGRATION_CATEGORIES:
        for page in integration_pages(category):
            targets.setdefault(page["path"], page)
        time.sleep(REQUEST_DELAY_SEC)
    return sorted(targets.values(), key=lambda p: p["path"])


def main():
    targets = collect_targets()
    print(f"수집 대상: {len(targets)}페이지")
    manifest, failed, skipped = [], [], []
    for i, page in enumerate(targets, 1):
        url = f"{DOCS_BASE}/{page['path']}.md"
        try:
            text = fetch(url)
        except Exception as e:  # 한 페이지 실패로 전체를 멈추지 않는다
            failed.append(page["path"])
            print(f"  [실패] {page['path']}: {e}", file=sys.stderr)
            continue
        if text.lstrip()[:15].lower().startswith(("<!doctype", "<html")):
            # .md 원문이 없고 외부(레퍼런스 사이트 등)로 넘어가는 페이지
            skipped.append(page["path"])
            continue
        out = LATEST_DIR / f"{page['path']}.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        title = page["title"] or ((m := TITLE.search(text)) and m.group(1).strip())
        manifest.append({
            "url": url.removesuffix(".md"),
            "path": page["path"],
            "file": str(out.relative_to(ROOT)),
            "title": title,
            "description": page["description"],
            "section": page["section"],
            "source": page["source"],
            "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "bytes": len(text.encode("utf-8")),
            "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        })
        if i % 25 == 0:
            print(f"  {i}/{len(targets)}")
        time.sleep(REQUEST_DELAY_SEC)

    LATEST_MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LATEST_MANIFEST_PATH.open("w", encoding="utf-8") as f:
        for rec in manifest:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    total = sum(r["bytes"] for r in manifest)
    print(f"완료: {len(manifest)}페이지, {total / 1e6:.1f}MB, 실패 {len(failed)}건, HTML 건너뜀 {len(skipped)}건")
    for path in failed:
        print(f"  실패: {path}")
    for path in skipped:
        print(f"  건너뜀(HTML): {path}")


if __name__ == "__main__":
    main()
