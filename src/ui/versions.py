"""화면이 고를 수 있는 버전 목록과 최신 버전 (4번 화면).

version_summary.json: 2번 import 대응표에 나오는 옛 버전 목록과, 버전별 도구 목록에서 본 최신 버전.
"""

import json
from pathlib import Path

SUMMARY = json.loads((Path(__file__).with_name("version_summary.json")).read_text(encoding="utf-8"))
ALL = [v["version"] for v in SUMMARY["versions"]]          # 옛 버전, 오래된 순
ALL_WITH_NEW = [*ALL, "1.x"]                               # 화면에서 고를 수 있는 전체 (오래된 순)
LATEST = SUMMARY["latest"]                                 # 예: {"langchain": "1.4.4", "langchain-core": "1.6.10"}
