import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest
from django.conf import settings

LOCALE_DIR = Path(settings.BASE_DIR) / 'locale'


def test_compilemessages_succeeds():
    # Run msgfmt in a temp copy so we don't need write access to the source tree
    # (CI may run on a read-only filesystem).
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_locale = Path(tmpdir) / 'locale'
        shutil.copytree(LOCALE_DIR, tmp_locale)

        errors = []
        for po_file in tmp_locale.rglob('*.po'):
            result = subprocess.run(
                [
                    'msgfmt',
                    '-c',
                    '-o',
                    str(po_file.with_suffix('.mo')),
                    str(po_file),
                ],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                errors.append(
                    f'{po_file.relative_to(tmp_locale)}: {result.stderr}'
                )

        if errors:
            pytest.fail(
                'compilemessages generated one or more errors:\n'
                + '\n'.join(errors)
            )
