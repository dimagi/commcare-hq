from __future__ import absolute_import
from __future__ import unicode_literals
import os
import json

from django.core.management.base import BaseCommand
from django.conf import settings

CACHE_DIR = os.path.join(settings.STATIC_ROOT, settings.COMPRESS_OUTPUT_DIR)

JS_CACHE_DIR = os.path.join(CACHE_DIR, 'js')
MANIFEST_FILE = os.path.join(CACHE_DIR, settings.COMPRESS_OFFLINE_MANIFEST)


class Command(BaseCommand):
    help = "Purges all static files that aren't in the manifest.json file"

    def handle(self, **kwargs):
        with open(MANIFEST_FILE, 'r+') as f:
            manifest = json.loads(f.read())

        for filename in os.listdir(JS_CACHE_DIR):
            content_hash = filename.split('.')[0]
            if not self._in_manifest(content_hash, manifest):
                os.remove(os.path.join(JS_CACHE_DIR, filename))

    def _in_manifest(self, content_hash, manifest):
        paths = list(manifest.values())
        for path in paths:
            if content_hash in path:
                return True
        return False
