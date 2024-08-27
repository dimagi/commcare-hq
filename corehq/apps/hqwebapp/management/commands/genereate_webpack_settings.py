import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

import corehq

WEBPACK_BASE_DIR = Path(corehq.__file__).resolve().parent.parent / "webpack"


class Command(BaseCommand):
    help = ("Generates a settings file for webpack so that the same staticfiles directory "
            "that Django is using is passed to the Webpack build.")

    def handle(self, **options):
        webpack_settings = {
            'staticfilesPath': settings.STATIC_ROOT,
        }
        with open(WEBPACK_BASE_DIR / "settings.json", "w") as f:
            json.dump(webpack_settings, f)
