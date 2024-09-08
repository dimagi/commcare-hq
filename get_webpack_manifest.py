import json
import os


def get_webpack_manifest(path=None):

    if not path:
        path = os.path.join('webpack/_build/manifest.json')
    if not os.path.exists(path):
        return None

    with open(path, 'r', encoding='utf-8') as f:
        manifest = json.load(f)

    return manifest
