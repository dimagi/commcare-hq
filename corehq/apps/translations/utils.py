from __future__ import absolute_import
from __future__ import unicode_literals

import tempfile

import six

from corehq.apps.app_manager.models import LinkedApplication
from corehq import toggles


def get_file_content_from_workbook(wb):
    # temporary write the in-memory workbook to be able to read its content
    with tempfile.TemporaryFile(suffix='.xlsx') as f:
        wb.save(f)
        f.seek(0)
        content = f.read()
    return content


def update_app_translations_from_trans_dict(app, trans_dict):
    if isinstance(app, LinkedApplication):
        app_translation_dict = app.linked_app_translations
    else:
        app_translation_dict = app.translations

    if toggles.PARTIAL_UI_TRANSLATIONS.enabled(app.domain):
        for lang in trans_dict:
            if lang in app_translation_dict:
                app_translation_dict[lang].update(trans_dict[lang])
            else:
                app_translation_dict[lang] = trans_dict[lang]
    else:
        app_translation_dict.update(trans_dict)
