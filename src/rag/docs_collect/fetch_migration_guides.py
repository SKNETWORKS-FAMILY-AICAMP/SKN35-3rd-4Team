"""구버전(0.2/0.3) 공식 마이그레이션 가이드만 골라 수집한다 (3단계).

구버전 문서 사이트(python.langchain.com)는 최신 문서로 리다이렉트되므로
GitHub 저장소 langchain-ai/langchain 의 `langchain==0.3.30` 태그에서 원문을 받는다.
0.3.30 시점 문서에는 0.0.x~0.3 코드를 옮기는 가이드가 모두 모여 있다.

- .ipynb 는 마크다운 셀과 코드 셀만 남겨 .md 로 변환 (실행 결과, %pip, API 키 입력 셀 제외)
- 가이드의 "변경 후" 코드는 0.3 시점 기준이므로 매니페스트에 era="0.3"을 단다

실행 (프로젝트 루트에서):
    uv run python -m src.rag.docs_collect.fetch_migration_guides
"""

import hashlib
import json
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone

from . import REQUEST_DELAY_SEC, ROOT, USER_AGENT

REPO = "langchain-ai/langchain"
TAG = "langchain==0.3.30"
ERA = "0.3"
MIGRATION_DIR = ROOT / "data" / "raw" / "docs" / "migration"
MIGRATION_MANIFEST_PATH = ROOT / "data" / "raw" / "docs" / "migration_manifest.jsonl"

# (저장소 경로 접두사 또는 파일, 묶음 이름)
GROUPS = [
    ("docs/docs/versions/v0_2/", "version_guide"),
    ("docs/docs/versions/v0_3/", "version_guide"),
    ("docs/docs/versions/migrating_chains/", "chains"),
    ("docs/docs/versions/migrating_memory/", "memory"),
    ("docs/docs/how_to/migrate_agent.ipynb", "agents"),
]
EXCLUDE = {
    "docs/docs/versions/migrating_memory/long_term_memory_agent.ipynb",  # 튜토리얼, 대부분 실행 결과
}

SKIP_CODE = re.compile(r"^\s*(%pip|!pip|%%capture)|getpass\(", re.MULTILINE)
TITLE = re.compile(r"^#\s+(.+)$", re.MULTILINE)
FRONTMATTER_TITLE = re.compile(r"^---\n(?:.*\n)*?(?:title|sidebar_label):\s*(.+)\n(?:.*\n)*?---", re.MULTILINE)


def get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def tag_ref() -> tuple[str, list[str]]:
    """태그의 커밋 sha와 파일 목록 (GitHub API 1회 + 커밋 조회 1회)."""
    enc = urllib.parse.quote(TAG, safe="")
    tree = json.loads(get(f"https://api.github.com/repos/{REPO}/git/trees/{enc}?recursive=1"))
    commit = json.loads(get(f"https://api.github.com/repos/{REPO}/commits/{enc}"))
    files = [t["path"] for t in tree["tree"] if t["type"] == "blob"]
    return commit["sha"], files


def group_of(path: str) -> str | None:
    if path in EXCLUDE or not path.endswith((".md", ".mdx", ".ipynb")):
        return None
    for prefix, group in GROUPS:
        if path == prefix or (prefix.endswith("/") and path.startswith(prefix)):
            return group
    return None


def notebook_to_md(raw: bytes) -> str:
    nb = json.loads(raw)
    lang = nb.get("metadata", {}).get("language_info", {}).get("name", "python")
    parts = []
    for cell in nb["cells"]:
        src = "".join(cell["source"]).strip()
        if not src:
            continue
        if cell["cell_type"] == "markdown":
            parts.append(src)
        elif cell["cell_type"] == "code" and not SKIP_CODE.search(src):
            parts.append(f"```{lang}\n{src}\n```")
    return "\n\n".join(parts) + "\n"


def main():
    sha, files = tag_ref()
    targets = [(p, g) for p in files if (g := group_of(p))]
    print(f"{TAG} ({sha[:10]}): {len(targets)}개 파일")
    manifest = []
    for path, group in sorted(targets):
        raw = get(f"https://raw.githubusercontent.com/{REPO}/{sha}/{path}")
        text = notebook_to_md(raw) if path.endswith(".ipynb") else raw.decode("utf-8")
        rel = path.removeprefix("docs/docs/").rsplit(".", 1)[0]
        out = MIGRATION_DIR / f"{rel}.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        m = TITLE.search(text) or FRONTMATTER_TITLE.search(text)
        manifest.append({
            "path": rel,
            "file": str(out.relative_to(ROOT)),
            "source_url": f"https://github.com/{REPO}/blob/{sha}/{path}",
            "tag": TAG,
            "commit": sha,
            "era": ERA,
            "group": group,
            "format": path.rsplit(".", 1)[1],
            "title": m.group(1).strip().strip("\"'") if m else None,
            "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "bytes": len(text.encode("utf-8")),
            "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        })
        time.sleep(REQUEST_DELAY_SEC)

    with MIGRATION_MANIFEST_PATH.open("w", encoding="utf-8") as f:
        for rec in manifest:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    total = sum(r["bytes"] for r in manifest)
    print(f"완료: {len(manifest)}개, {total / 1e3:.0f}KB")
    for rec in manifest:
        print(f"  [{rec['group']}] {rec['path']} ({rec['bytes'] / 1e3:.1f}KB) {rec['title']}")


if __name__ == "__main__":
    main()
