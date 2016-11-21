from collections import defaultdict
import re
from StringIO import StringIO

from django.contrib import messages
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect
from django.utils.translation import ugettext as _

from commcare_translations import load_translations
from corehq.apps.app_manager import app_strings
from corehq.apps.app_manager.dbaccessors import get_app
from corehq.apps.app_manager.decorators import no_conflict_require_POST, \
    require_can_edit_apps
from corehq.apps.app_manager.translations import \
    expected_bulk_app_sheet_headers, expected_bulk_app_sheet_rows, \
    process_bulk_app_translation_upload
from corehq.apps.translations import system_text_sources
from corehq.util.spreadsheets_v1.excel import WorkbookJSONReader
from couchexport.export import export_raw
from couchexport.models import Format
from couchexport.shortcuts import export_response
from dimagi.utils.decorators.view import get_file
from dimagi.utils.logging import notify_exception


def get_index_for_defaults(langs):
    try:
        return langs.index("en")
    except ValueError:
        return 0


@no_conflict_require_POST
@require_can_edit_apps
@get_file("bulk_upload_file")
def upload_bulk_ui_translations(request, domain, app_id):

    def _html_message(header_text, messages):
        message = header_text + "<br>"
        for prop in messages:
            message += "<li>%s</li>" % prop
        return message

    success = False
    try:
        app = get_app(domain, app_id)
        trans_dict, error_properties, warnings = process_ui_translation_upload(
            app, request.file
        )
        if error_properties:
            message = _html_message(_("Upload failed. We found problems with the following translations:"),
                                    error_properties)
            messages.error(request, message, extra_tags='html')
        else:
            # update translations only if there were no errors
            app.translations = dict(trans_dict)
            app.save()
            success = True

        if warnings:
            message = _html_message(_("Upload succeeded, but we found following issues for some properties"),
                                    warnings)
            messages.warning(request, message, extra_tags='html')

    except Exception:
        notify_exception(request, 'Bulk Upload Translations Error')
        messages.error(request, _("Something went wrong! Update failed. We're looking into it"))

    if success:
        messages.success(request, _("UI Translations Updated!"))

    return HttpResponseRedirect(reverse('app_languages', args=[domain, app_id]))


@require_can_edit_apps
def download_bulk_ui_translations(request, domain, app_id):
    app = get_app(domain, app_id)
    temp = build_ui_translation_download_file(app)
    return export_response(temp, Format.XLS_2007, "translations")


@require_can_edit_apps
def download_bulk_app_translations(request, domain, app_id):
    app = get_app(domain, app_id)
    headers = expected_bulk_app_sheet_headers(app)
    rows = expected_bulk_app_sheet_rows(app)
    temp = StringIO()
    data = [(k, v) for k, v in rows.iteritems()]
    export_raw(headers, data, temp)
    return export_response(temp, Format.XLS_2007, "bulk_app_translations")


@no_conflict_require_POST
@require_can_edit_apps
@get_file("bulk_upload_file")
def upload_bulk_app_translations(request, domain, app_id):
    app = get_app(domain, app_id)
    msgs = process_bulk_app_translation_upload(app, request.file)
    app.save()
    for msg in msgs:
        # Add the messages to the request object.
        # msg[0] should be a function like django.contrib.messages.error .
        # mes[1] should be a string.
        msg[0](request, msg[1])
    return HttpResponseRedirect(
        reverse('app_languages', args=[domain, app_id])
    )


def process_ui_translation_upload(app, trans_file):

    workbook = WorkbookJSONReader(trans_file)
    translations = workbook.get_worksheet(title='translations')

    commcare_ui_strings = load_translations('en', 2).keys()
    default_trans = get_default_translations_for_download(app)
    lang_with_defaults = app.langs[get_index_for_defaults(app.langs)]

    trans_dict = defaultdict(dict)
    # Use this to hard fail and not update any translations
    error_properties = []
    # Use this to pass warnings without failing hard
    warnings = []
    for row in translations:
        if row["property"] not in commcare_ui_strings:
            # Add a warning for  unknown properties, but still add them to the translation dict
            warnings.append(row["property"] + " is not a known CommCare UI string, but we added it anyway")
        for lang in app.langs:
            if row.get(lang):
                all_parameters = re.findall("\$.*?}", row[lang])
                for param in all_parameters:
                    if not re.match("\$\{[0-9]+}", param):
                        error_properties.append(row["property"] + ' - ' + row[lang])
                if not (lang_with_defaults == lang and
                        row[lang] == default_trans.get(row["property"], "")):
                    trans_dict[lang].update({row["property"]: row[lang]})

    return trans_dict, error_properties, warnings


def build_ui_translation_download_file(app):

    properties = tuple(["property"] + app.langs + ["platform"])
    temp = StringIO()
    headers = (("translations", properties),)

    row_dict = {}
    for i, lang in enumerate(app.langs):
        index = i + 1
        trans_dict = app.translations.get(lang, {})
        for prop, trans in trans_dict.iteritems():
            if prop not in row_dict:
                row_dict[prop] = [prop]
            num_to_fill = index - len(row_dict[prop])
            row_dict[prop].extend(["" for i in range(num_to_fill)] if num_to_fill > 0 else [])
            row_dict[prop].append(trans)

    rows = row_dict.values()
    all_prop_trans = get_default_translations_for_download(app)
    rows.extend([[t] for t in sorted(all_prop_trans.keys()) if t not in row_dict])

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

    def add_sources(row):
        platform_map = {
            "CommCareAndroid": "Android",
            "CommCareJava": "Java",
            "ODK": "Android",
            "JavaRosa": "Java",
        }
        source = system_text_sources.SOURCES.get(row[0], "")
        row[-1] = platform_map.get(source, "")
        return row

    rows = [add_sources(add_default(fillrow(row))) for row in rows]

    data = (("translations", tuple(rows)),)
    export_raw(headers, data, temp)
    return temp


def get_default_translations_for_download(app):
    return app_strings.CHOICES[app.translation_strategy].get_default_translations('en')
