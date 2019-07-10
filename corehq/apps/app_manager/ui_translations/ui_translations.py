from __future__ import absolute_import
from __future__ import unicode_literals

import io
import re
from collections import defaultdict
from distutils.version import StrictVersion

from django.utils.translation import ugettext as _

import six
from six.moves import range

from couchexport.export import export_raw_to_writer

from commcare_translations import load_translations
from corehq.apps.app_manager import app_strings
from corehq.apps.app_manager.ui_translations.commcare_versioning import (
    get_commcare_version_from_workbook,
    set_commcare_version_in_workbook,
)
from corehq.apps.translations.models import TransifexBlacklist
from corehq.util.workbook_json.excel import (
    WorkbookJSONError,
    WorksheetNotFound,
    get_workbook,
)


def process_ui_translation_upload(app, trans_file):
    trans_dict = defaultdict(dict)
    # Use this to hard fail and not update any translations
    error_properties = []
    # Use this to pass warnings without failing hard
    warnings = []

    try:
        workbook = get_workbook(trans_file)
    except WorkbookJSONError as e:
        error_properties.append(six.text_type(e))
        return trans_dict, error_properties, warnings

    commcare_version = get_commcare_version_from_workbook(workbook.wb)
    try:
        translations = workbook.get_worksheet(title='translations')
    except WorksheetNotFound:
        error_properties.append(_('Could not find sheet "translations" in uploaded file.'))
        return trans_dict, error_properties, warnings

    commcare_ui_strings = list(load_translations('en', version=2, commcare_version=commcare_version).keys())
    default_trans = get_default_translations_for_download(app, commcare_version)
    lang_with_defaults = app.langs[get_index_for_defaults(app.langs)]

    for row in translations:
        if row["property"] not in commcare_ui_strings:
            # Add a warning for  unknown properties, but still add them to the translation dict
            warnings.append(row["property"] + " is not a known CommCare UI string, but we added it anyway")
        for lang in app.langs:
            if row.get(lang):
                all_parameters = re.findall(r"\$.*?}", row[lang])
                for param in all_parameters:
                    if not re.match(r"\$\{[0-9]+}", param):
                        error_properties.append(row["property"] + ' - ' + row[lang])
                if not (lang_with_defaults == lang and
                        row[lang] == default_trans.get(row["property"], "")):
                    trans_dict[lang].update({row["property"]: row[lang]})

    return trans_dict, error_properties, warnings


def _get_ui_blacklist(app):
    blacklist = TransifexBlacklist.objects.filter(
        domain=app.domain,
        app_id=app._id,
        module_id='',
        field_type='ui',
    ).all()
    return {b.field_name for b in blacklist}


def build_ui_translation_download_file(app):
    blacklist = _get_ui_blacklist(app)
    properties = tuple(["property"] + app.langs)
    temp = io.BytesIO()
    headers = (("translations", properties),)

    row_dict = {}
    for i, lang in enumerate(app.langs):
        index = i + 1
        trans_dict = app.translations.get(lang, {})
        for prop, trans in six.iteritems(trans_dict):
            if prop in blacklist:
                continue
            if prop not in row_dict:
                row_dict[prop] = [prop]
            num_to_fill = index - len(row_dict[prop])
            row_dict[prop].extend(["" for i in range(num_to_fill)] if num_to_fill > 0 else [])
            row_dict[prop].append(trans)

    rows = list(row_dict.values())
    try:
        commcare_version = str(StrictVersion(app.build_version.vstring))
    except ValueError:
        commcare_version = None

    all_prop_trans = get_default_translations_for_download(app, commcare_version)
    rows.extend([[t] for t in sorted(all_prop_trans.keys()) if t not in row_dict and t not in blacklist])

    def fillrow(row):
        num_to_fill = len(properties) - len(row)
        row.extend(["" for i in range(num_to_fill)] if num_to_fill > 0 else [])
        return row

    def add_default(row):
        row_index = get_index_for_defaults(app.langs) + 1
        if not row[row_index]:
            # If no custom translation exists, replace it.
            row[row_index] = all_prop_trans.get(row[0], "")
        return row

    rows = [add_default(fillrow(row)) for row in rows]

    data = (("translations", tuple(rows)),)
    with export_raw_to_writer(headers, data, temp) as writer:
        set_commcare_version_in_workbook(writer.book, commcare_version)
    return temp


def get_default_translations_for_download(app, commcare_version):
    return app_strings.CHOICES[app.translation_strategy].get_default_translations('en', commcare_version)


def get_index_for_defaults(langs):
    try:
        return langs.index("en")
    except ValueError:
        return 0
