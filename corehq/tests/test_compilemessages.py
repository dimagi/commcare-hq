from pathlib import Path

import pytest
from django.conf import settings
from django.core.management import call_command, CommandError

LOCALE_DIR = Path(settings.BASE_DIR) / 'locale'


def test_compilemessages_succeeds():
    # Remove .mo files so compilemessages doesn't skip unchanged .po files
    for mo_file in LOCALE_DIR.rglob('*.mo'):
        mo_file.unlink()

    try:
        call_command('compilemessages', '-v', '0')
    except CommandError as err:
        pytest.fail(str(err))
