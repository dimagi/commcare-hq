import json
from pathlib import Path

import corehq

WEBPACK_BUILD_DIR = Path(corehq.__file__).resolve().parent.parent / "webpack" / "_build"


def get_webpack_manifest(filename=None):

    if not filename:
        path = WEBPACK_BUILD_DIR / "manifest.json"
    else:
        path = WEBPACK_BUILD_DIR / filename
    if not path.is_file():
        return None

    with open(path, 'r', encoding='utf-8') as f:
        manifest = json.load(f)

    return manifest
