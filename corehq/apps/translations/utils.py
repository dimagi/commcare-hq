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


def update_app_translations_from_trans_dict(app, new_trans):
    """
    :param app: app to update translations on
    :param new_trans: dict of new translations, lang_code: translations
    """
    if isinstance(app, LinkedApplication):
        current_trans_dicts = [app.linked_app_translations, app.translations]
    else:
        current_trans_dicts = [app.translations]

    if toggles.PARTIAL_UI_TRANSLATIONS.enabled(app.domain):
        for lang in new_trans:
            for current_translation_dict in current_trans_dicts:
                if lang in current_translation_dict:
                    current_translation_dict[lang].update(new_trans[lang])
                else:
                    current_translation_dict[lang] = new_trans[lang]
    else:
        for current_translation_dict in current_trans_dicts:
            current_translation_dict.update(new_trans)
