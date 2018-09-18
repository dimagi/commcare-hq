from __future__ import absolute_import
from __future__ import unicode_literals

import tempfile

from django.conf import settings


def transifex_details_available_for_domain(domain):
    return (
        settings.TRANSIFEX_DETAILS and
        settings.TRANSIFEX_DETAILS.get('project', {}).get(domain)
    )


def get_file_content_from_workbook(wb):
    # temporary write the in-memory workbook to be able to read its content
    with tempfile.TemporaryFile(suffix='.xlsx') as f:
        wb.save(f)
        f.seek(0)
        content = f.read()
    return content
