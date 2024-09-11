import json
import os
import warnings
from django.conf import settings


def get_webpack_manifest(path=None):
    manifest = {}

    if not path:
        path = os.path.join('webpack/_build/manifest.json')
    if not os.path.exists(path):
        if not settings.UNIT_TESTING and settings.DEBUG:
            warnings.warn("\x1b[33;20m"  # yellow color
                          "\n\n\nNo webpack manifest found!"
                          "\nDid you run `yarn dev` or `yarn build`?\n\n"
                          "\x1b[0m")
        return manifest

    with open(path, 'r', encoding='utf-8') as f:
        manifest = json.load(f)

    return manifest
