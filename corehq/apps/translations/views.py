from __future__ import absolute_import, unicode_literals

import io

from django.contrib import messages
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils.translation import ugettext as _

import six

from couchexport.export import export_raw
from couchexport.models import Format
from couchexport.shortcuts import export_response
from dimagi.utils.decorators.view import get_file
from dimagi.utils.logging import notify_exception

from corehq.apps.app_manager.dbaccessors import get_app
from corehq.apps.app_manager.decorators import (
    no_conflict_require_POST,
    require_can_edit_apps,
)
from corehq.apps.app_manager.ui_translations import (
    build_ui_translation_download_file,
    process_ui_translation_upload,
)
from corehq.apps.translations.app_translations.download import (
    get_bulk_app_sheets_by_name,
    get_bulk_app_single_sheet_by_name,
)
from corehq.apps.translations.app_translations.upload_app import (
    get_sheet_name_to_unique_id_map,
    process_bulk_app_translation_upload,
    validate_bulk_app_translation_upload,
)
from corehq.apps.translations.app_translations.utils import (
    get_bulk_app_sheet_headers,
)
from corehq.apps.translations.utils import (
    update_app_translations_from_trans_dict,
)
from corehq.util.workbook_json.excel import (
    WorkbookJSONError,
    get_workbook,
)


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
            update_app_translations_from_trans_dict(app, trans_dict)
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

    # In v2, languages is the default tab on the settings page
    view_name = 'app_settings'
    return HttpResponseRedirect(reverse(view_name, args=[domain, app_id]))


@require_can_edit_apps
def download_bulk_ui_translations(request, domain, app_id):
    app = get_app(domain, app_id)
    temp = build_ui_translation_download_file(app)
    filename = '{app_name} v.{app_version} - CommCare Translations'.format(
        app_name=app.name,
        app_version=app.version)
    return export_response(temp, Format.XLS_2007, filename)


@require_can_edit_apps
def download_bulk_app_translations(request, domain, app_id):
    lang = request.GET.get('lang')
    skip_blacklisted = request.GET.get('skipbl', 'false') == 'true'
    app = get_app(domain, app_id)
    headers = get_bulk_app_sheet_headers(app, lang=lang, eligible_for_transifex_only=skip_blacklisted)
    if lang:
        sheets = get_bulk_app_single_sheet_by_name(app, lang, skip_blacklisted)
    else:
        sheets = get_bulk_app_sheets_by_name(app, eligible_for_transifex_only=skip_blacklisted)

    temp = io.BytesIO()
    data = [(k, v) for k, v in six.iteritems(sheets)]
    export_raw(headers, data, temp)
    filename = '{app_name} v.{app_version} - App Translations{lang}'.format(
        app_name=app.name,
        app_version=app.version,
        lang=' ' + lang if lang else '')
    return export_response(temp, Format.XLS_2007, filename)


@no_conflict_require_POST
@require_can_edit_apps
@get_file("bulk_upload_file")
def upload_bulk_app_translations(request, domain, app_id):
    lang = request.POST.get('language')
    validate = request.POST.get('validate')

    app = get_app(domain, app_id)
    try:
        workbook = get_workbook(request.file)
    except WorkbookJSONError as e:
        messages.error(request, six.text_type(e))
    else:
        if validate:
            msgs = validate_bulk_app_translation_upload(app, workbook, request.user.email, lang)
        else:
            sheet_name_to_unique_id = get_sheet_name_to_unique_id_map(request.file, lang)
            msgs = process_bulk_app_translation_upload(app, workbook, sheet_name_to_unique_id, lang=lang)
            app.save()
        _add_messages_to_request(request, msgs)

    # In v2, languages is the default tab on the settings page
    return HttpResponseRedirect(
        reverse('app_settings', args=[domain, app_id])
    )


def _add_messages_to_request(request, msgs):
    for add_message_func, message in msgs:
        # add_message_func is a function like django.contrib.messages.error
        # message is a string
        add_message_func(request, message)
