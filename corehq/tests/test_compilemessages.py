from io import StringIO
from pathlib import Path

from django.conf import settings
from django.core.management import call_command

LOCALE_DIR = Path(settings.BASE_DIR) / 'locale'


def test_compilemessages_succeeds():
    # Remove .mo files so compilemessages doesn't skip unchanged .po files
    for mo_file in LOCALE_DIR.rglob('*.mo'):
        mo_file.unlink()

    out = StringIO()
    err = StringIO()
    call_command('compilemessages', stdout=out, stderr=err)
    errors = err.getvalue()
    assert errors == '', f'compilemessages produced errors:\n{errors}'
