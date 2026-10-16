"""선택 기능(src/ui/extras/) 불러오기. extras 폴더를 통째로 빼도 화면이 동작하도록 이 파일은 폴더 밖에 둔다."""

import importlib


def load(name: str):
    """선택 기능 모듈 (src/ui/extras/{name}.py). 폴더나 파일이 없으면 None."""
    try:
        return importlib.import_module(f"src.ui.extras.{name}")
    except ImportError:
        return None
