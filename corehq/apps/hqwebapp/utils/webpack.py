import json
from pathlib import Path

from django.conf import settings
from memoized import memoized

import corehq

WEBPACK_BUILD_DIR = Path(corehq.__file__).resolve().parent.parent / "webpack" / "_build"


def cache_unless_debug(func):
    return func if settings.DEBUG else memoized(func)


class WebpackManifestNotFoundError(Exception):
    pass


@cache_unless_debug
def get_webpack_manifest(filename=None):
    if not filename:
        path = WEBPACK_BUILD_DIR / "manifest.json"
    else:
        path = WEBPACK_BUILD_DIR / filename
    if not path.is_file():
        raise WebpackManifestNotFoundError

    with open(path, 'r', encoding='utf-8') as f:
        manifest = json.load(f)

    return manifest
