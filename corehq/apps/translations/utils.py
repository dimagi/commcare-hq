from __future__ import absolute_import
from __future__ import unicode_literals

import tempfile

import six

from corehq.apps.app_manager.models import LinkedApplication


def get_file_content_from_workbook(wb):
    # temporary write the in-memory workbook to be able to read its content
    with tempfile.TemporaryFile(suffix='.xlsx') as f:
        wb.save(f)
        f.seek(0)
        content = f.read()
    return content


def update_app_translations_from_trans_dict(app, trans_dict):
    if isinstance(app, LinkedApplication):
        if app.add_ons.get('partial_commcare_translations') is True:
            for lang, trans in six.iteritems(app.translations):
                if lang in trans_dict:
                    app.translations[lang].update(trans_dict[lang])
        else:
            app.linked_app_translations.update(trans_dict)

    if app.add_ons.get('partial_commcare_translations') is True:
        for lang, trans in six.iteritems(app.translations):
            if lang in trans_dict:
                app.translations[lang].update(trans_dict[lang])
    else:
        app.translations.update(trans_dict)
