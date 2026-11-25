import io

from django.contrib import messages
from django.http import Http404, HttpResponseRedirect, JsonResponse
from django.urls import reverse
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from django.views.decorators.http import require_GET, require_POST

from couchdbkit import NoResultFound
from couchexport.export import export_raw
from couchexport.models import Format
from couchexport.shortcuts import export_response
from dimagi.utils.decorators.view import get_file
from dimagi.utils.logging import notify_exception

from corehq.apps.app_manager.dbaccessors import get_app, get_brief_app
from corehq.apps.app_manager.decorators import (
    no_conflict_require_POST,
    require_can_edit_apps,
)
from corehq.apps.app_manager.exceptions import (
    AppInDifferentDomainException,
    FormNotFoundException,
    ModuleNotFoundException,
    XFormException,
)
from corehq.apps.app_manager.ui_translations import (
    build_ui_translation_download_file,
    process_ui_translation_upload,
)
from corehq.apps.hqwebapp.decorators import waf_allow
from corehq.apps.translations.app_translations.ai_failed_labels import (
    failed_label_reason,
    get_failed_labels,
)
from corehq.apps.translations.app_translations.ai_status import (
    AITranslationStatus,
)
from corehq.apps.translations.app_translations.ai_translator import (
    ai_translation_enabled,
    langs_to_translate,
    monthly_word_limit_reached,
    reason_app_cant_be_translated,
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
from corehq.apps.translations.const import MODE_FILL_MISSING
from corehq.apps.translations.exceptions import BulkAppTranslationsException
from corehq.apps.translations.tasks import queue_app_translation, run_message
from corehq.apps.translations.utils import (
    update_app_translations_from_trans_dict,
)
from corehq.util.workbook_json.excel import WorkbookJSONError, get_workbook


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
    app = get_app(domain, app_id)
    single_sheet = request.GET.get('format') == "single"
    headers = get_bulk_app_sheet_headers(app, single_sheet=single_sheet, lang=lang)
    if single_sheet:
        sheets = get_bulk_app_single_sheet_by_name(app, lang)
    else:
        sheets = get_bulk_app_sheets_by_name(app, lang=lang)

    temp = io.BytesIO()
    data = [(k, v) for k, v in sheets.items()]
    export_raw(headers, data, temp)
    filename = '{app_name} v.{app_version} - App Translations{lang}'.format(
        app_name=app.name,
        app_version=app.version,
        lang=' ' + lang if lang else '',
    )
    return export_response(temp, Format.XLS_2007, filename)


@waf_allow('XSS_BODY')
@no_conflict_require_POST
@require_can_edit_apps
@get_file("bulk_upload_file")
def upload_bulk_app_translations(request, domain, app_id):
    lang = request.POST.get('language')
    validate = request.POST.get('validate')
    app = get_app(domain, app_id)
    file = request.file
    try:
        workbook = get_workbook(file)
    except WorkbookJSONError as e:
        messages.error(request, str(e))
    else:
        if validate:
            if not lang:
                msgs = [(messages.error, _("Please select language to validate."))]
            else:
                try:
                    msgs = validate_bulk_app_translation_upload(
                        app, workbook, request.couch_user.get_email(), lang, file
                    )
                except BulkAppTranslationsException as e:
                    msgs = [(messages.error, str(e))]
        else:
            sheet_name_to_unique_id = get_sheet_name_to_unique_id_map(request.file, lang)
            msgs = process_bulk_app_translation_upload(app, workbook, sheet_name_to_unique_id, lang=lang)
            app.save()
        _add_messages_to_request(request, msgs)

    # In v2, languages is the default tab on the settings page
    return HttpResponseRedirect(
        reverse('app_settings', args=[domain, app_id])
    )


@require_POST
@require_can_edit_apps
def start_ai_translation(request, domain, app_id):
    if not ai_translation_enabled(domain):
        return _json_error(_("AI translation isn't available for this project."), 403)
    app = _get_app(domain, app_id)
    reason = reason_app_cant_be_translated(app)
    if reason:
        return _json_error(reason, 400)
    if monthly_word_limit_reached(domain):
        return _json_error(_("This project has reached its monthly AI translation "
                             "limit. Contact support to raise it."), 403)
    lang = request.POST.get('lang')
    if lang not in langs_to_translate(app):
        return _json_error(_("This language can't be translated with AI."), 400)
    queued = queue_app_translation(
        domain, app_id, lang, MODE_FILL_MISSING, request.couch_user.username)
    if not queued:
        return _json_error(_("This language is already being translated."), 409)
    return JsonResponse({'success': True})


@require_GET
@require_can_edit_apps
def ai_translation_status(request, domain, app_id):
    """Status of each language AI can translate the app into, so the
    Languages page polls one URL however many languages are running."""
    app = _get_brief_app(domain, app_id)
    if not ai_translation_enabled(domain):
        return _json_error(_("AI translation isn't available for this project."), 403)
    return JsonResponse({
        lang: _with_message(AITranslationStatus(app_id, lang).get())
        for lang in langs_to_translate(app)
    })


@require_GET
@require_can_edit_apps
def ai_translation_failed_labels(request, domain, app_id):
    """Return the labels the language's last run couldn't translate.

    The page fetches them when someone asks to see them. ``labels`` is
    None once the list has expired.
    """
    if not ai_translation_enabled(domain):
        return _json_error(_("AI translation isn't available for this project."), 403)
    app = _get_app(domain, app_id)
    records = get_failed_labels(app_id, request.GET.get('lang'))
    if records is None:
        return JsonResponse({'labels': None})
    questions_by_form = {}
    return JsonResponse({
        'labels': [_failed_label_row(app, record, questions_by_form) for record in records],
    })


# which screen of a menu a module-sheet row's ``list_or_detail`` is on
CASE_PROPERTY_SECTIONS = {
    'list': gettext_lazy("Case list"),
    'detail': gettext_lazy("Case detail"),
    'case_search_display': gettext_lazy("Case search"),
    'case_search_hint': gettext_lazy("Case search"),
}


def _failed_label_row(app, record, questions_by_form):
    """Describe why a label failed to translate, and where it is in the app.

    The row has where the label is in the app as it is now, a link to
    it, its English text and why it failed. A label whose menu or form
    has since been deleted has no location or link.
    """
    row = {
        'source': record['source'],
        'reason': failed_label_reason(record['reason']),
        'location': [],
        'url': None,
    }
    domain, app_id = app.domain, app.get_id
    try:
        if record['type'] in ('menu', 'case_property'):
            module = app.get_module_by_unique_id(record['unique_id'])
            row['location'] = [module.default_name()]
            row['url'] = reverse('view_module', args=[domain, app_id, module.unique_id])
            if record['type'] == 'case_property':
                # a report menu's rows say 'list', but it has no case list
                section = None if module.module_type == 'report' else (
                    CASE_PROPERTY_SECTIONS.get(record['list_or_detail']))
                row['location'] += [str(section), record['case_property']] if section else [
                    record['case_property']]
        else:
            form = app.get_form(record['unique_id'])
            row['location'] = [form.get_module().default_name(), form.default_name()]
            row['url'] = reverse('view_form', args=[domain, app_id, form.unique_id])
            if record['type'] == 'form_text':
                name, url = _form_text_location(app, form, record['itext_id'], questions_by_form)
                row['location'].append(name)
                row['url'] = url
    except (ModuleNotFoundException, FormNotFoundException):
        row['location'], row['url'] = [], None
    return row


def _form_text_location(app, form, itext_id, questions_by_form):
    """Name the question ``itext_id`` belongs to, and link to it."""
    if form.unique_id not in questions_by_form:
        try:
            questions = form.get_questions(
                [app.default_language], include_triggers=True, include_groups=True)
        except XFormException:
            # a form that doesn't parse still gets its rows, named by text id
            questions = []
        # reverse order puts "age-group" before "age", so "age-group-hint"
        # matches the question it belongs to, not "age"
        questions_by_form[form.unique_id] = sorted(
            questions, key=lambda question: question['value'], reverse=True)
    url = reverse('form_source', args=[app.domain, app.get_id, form.unique_id])
    question, part = _question_for_itext(questions_by_form[form.unique_id], itext_id)
    if question is None:
        return itext_id, url
    # the form builder selects the question at /data/<path> for #form/<path>
    path = question['value'].removeprefix('/data/')
    name = question['label'] or path
    if part:
        name = f'{name} › {part}'
    return name, f'{url}#form/{path}'


def _question_for_itext(questions, itext_id):
    """Find the part of the question for given ``itext_id``.

    A question has more text than its label, such as a hint or the
    choices of a multiple choice question. Their ids start with the
    question's path, e.g. ``age-hint`` is the hint of question ``age``.

    Returns the question and what the text is: None if it is the
    label, otherwise "hint", "choice" and so on.
    """
    for question in questions:
        if question.get('label_ref') == itext_id:
            return question, None
    for question in questions:
        path = question['value'].removeprefix('/data/')
        if itext_id.startswith(f'{path}-'):
            rest = itext_id[len(path) + 1:]
            return question, {
                'hint': _("hint"),
                'help': _("help text"),
                'constraintMsg': _("validation message"),
            }.get(rest, _("choice"))
    return None, None


def _with_message(status):
    if status.get('message_code'):
        status['message'] = run_message(status['message_code'])
    return status


def _get_app(domain, app_id):
    """The app, or 404 if it is deleted or in another project."""
    try:
        app = get_app(domain, app_id)
    except AppInDifferentDomainException:
        raise Http404()
    if app.is_deleted():
        raise Http404()
    return app


def _get_brief_app(domain, app_id):
    """The app's summary, which is enough for its languages, or 404 if it
    is deleted, a build, or in another project."""
    try:
        return get_brief_app(domain, app_id)
    except NoResultFound:
        raise Http404()


def _json_error(message, status):
    return JsonResponse({'error': message}, status=status)


def _add_messages_to_request(request, msgs):
    for add_message_func, message in msgs:
        # add_message_func is a function like django.contrib.messages.error
        # message is a string
        add_message_func(request, message)
