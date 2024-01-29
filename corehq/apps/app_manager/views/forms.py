import hashlib
import json
import logging
import re
from xml.dom.minidom import parseString

from django.conf import settings
from django.contrib import messages
from django.http import (
    Http404,
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseRedirect,
    JsonResponse,
)
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET

from diff_match_patch import diff_match_patch
from lxml import etree
from no_exceptions.exceptions import Http400
from text_unidecode import unidecode

from casexml.apps.case.const import DEFAULT_CASE_INDEX_IDENTIFIERS
from dimagi.utils.logging import notify_exception
from dimagi.utils.web import json_response

from corehq import privileges, toggles
from corehq.apps.accounting.utils import domain_has_privilege
from corehq.apps.app_manager.app_schemas.case_properties import (
    get_all_case_properties,
    get_usercase_properties,
)
from corehq.apps.app_manager.const import (
    USERCASE_PREFIX,
    USERCASE_TYPE,
    WORKFLOW_DEFAULT,
    WORKFLOW_FORM,
    WORKFLOW_MODULE,
    WORKFLOW_PARENT_MODULE,
    WORKFLOW_PREVIOUS,
    WORKFLOW_ROOT,
)
from corehq.apps.app_manager.dbaccessors import get_app, get_apps_in_domain
from corehq.apps.app_manager.decorators import (
    no_conflict_require_POST,
    require_can_edit_apps,
    require_deploy_apps,
)
from corehq.apps.app_manager.exceptions import (
    AppMisconfigurationError,
    FormNotFoundException,
    ModuleNotFoundException,
    XFormValidationFailed,
)
from corehq.apps.app_manager.helpers.validators import load_case_reserved_words
from corehq.apps.app_manager.models import (
    AdvancedForm,
    AdvancedFormActions,
    AppEditingError,
    ArbitraryDatum,
    CaseReferences,
    CustomIcon,
    CustomInstance,
    DeleteFormRecord,
    Form,
    FormActionCondition,
    FormActions,
    FormDatum,
    FormLink,
    IncompatibleFormTypeException,
    OpenCaseAction,
    UpdateCaseAction,
)
from corehq.apps.app_manager.templatetags.xforms_extras import (
    clean_trans,
    trans,
)
from corehq.apps.app_manager.util import (
    CASE_XPATH_SUBSTRING_MATCHES,
    USERCASE_XPATH_SUBSTRING_MATCHES,
    actions_use_usercase,
    advanced_actions_use_usercase,
    enable_usercase,
    is_usercase_in_use,
    module_loads_registry_case,
    module_uses_inline_search,
    save_xform,
)
from corehq.apps.app_manager.views.media_utils import handle_media_edits
from corehq.apps.app_manager.views.notifications import notify_form_changed
from corehq.apps.app_manager.views.schedules import get_schedule_context
from corehq.apps.app_manager.views.utils import (
    CASE_TYPE_CONFLICT_MSG,
    back_to_main,
    capture_user_errors,
    clear_xmlns_app_id_cache,
    form_has_submissions,
    get_langs,
    handle_custom_icon_edits,
    set_session_endpoint,
    validate_custom_assertions,
)
from corehq.apps.app_manager.xform import (
    CaseError,
    XFormException,
    XFormValidationError,
)
from corehq.apps.data_dictionary.util import (
    add_properties_to_data_dictionary,
    get_case_property_description_dict,
)
from corehq.apps.domain.decorators import (
    LoginAndDomainMixin,
    api_domain_view,
    login_or_digest,
    track_domain_request,
)
from corehq.apps.hqwebapp.decorators import waf_allow
from corehq.apps.programs.models import Program
from corehq.apps.users.decorators import require_permission
from corehq.apps.users.models import HqPermissions
from corehq.util.view_utils import set_file_download


@no_conflict_require_POST
@require_can_edit_apps
def delete_form(request, domain, app_id, module_unique_id, form_unique_id):
    "Deletes a form from an app"
    app = get_app(domain, app_id)
    record = app.delete_form(module_unique_id, form_unique_id)
    if record is not None:
        messages.success(
            request,
            'You have deleted a form. <a href="%s" class="post-link">Undo</a>'
            % reverse('undo_delete_form', args=[domain, record.get_id]),
            extra_tags='html'
        )
        app.save()
        clear_xmlns_app_id_cache(domain)
    try:
        module_id = app.get_module_by_unique_id(module_unique_id).id
    except ModuleNotFoundException as e:
        messages.error(request, str(e))
        module_id = None

    return back_to_main(request, domain, app_id=app_id, module_id=module_id)


@no_conflict_require_POST
@require_can_edit_apps
def copy_form(request, domain, app_id, form_unique_id):
    app = get_app(domain, app_id)
    form = app.get_form(form_unique_id)
    module = form.get_module()
    to_app = get_app(domain, request.POST['to_app_id']) if request.POST.get('to_app_id') else app
    to_module_id = int(request.POST['to_module_id'])
    to_module = to_app.get_module(to_module_id)
    new_form = None
    try:
        new_form = app.copy_form(module, form, to_module, rename=True)
        if module['case_type'] != to_module['case_type']:
            messages.warning(request, CASE_TYPE_CONFLICT_MSG, extra_tags="html")
        to_app.save()
    except IncompatibleFormTypeException:
        # don't save!
        messages.error(request, _('This form could not be copied because it '
                                  'is not compatible with the selected module.'))
    else:
        to_app.save()

    if new_form:
        return back_to_main(request, domain, app_id=to_app._id, form_unique_id=new_form.unique_id)
    return HttpResponseRedirect(reverse('view_form', args=(domain, app._id, form.unique_id)))


@no_conflict_require_POST
@require_can_edit_apps
def undo_delete_form(request, domain, record_id):
    record = DeleteFormRecord.get(record_id)
    try:
        record.undo()
        messages.success(request, 'Form successfully restored.')
    except ModuleNotFoundException:
        messages.error(
            request,
            'Form could not be restored: module is missing.'
        )

    return back_to_main(
        request,
        domain,
        app_id=record.app_id,
        module_id=record.module_id,
        form_id=record.form_id
    )


@no_conflict_require_POST
@require_can_edit_apps
def edit_advanced_form_actions(request, domain, app_id, form_unique_id):
    # Handle edit for actions and arbitrary_datums
    app = get_app(domain, app_id)
    form = app.get_form(form_unique_id)
    json_loads = json.loads(request.POST.get('actions'))
    actions = AdvancedFormActions.wrap(json_loads)
    if form.form_type == "shadow_form":
        form.extra_actions = actions
    else:
        form.actions = actions
    for action in actions.load_update_cases:
        add_properties_to_data_dictionary(domain, action.case_type, list(action.case_properties.keys()))
    if advanced_actions_use_usercase(actions) and not is_usercase_in_use(domain):
        enable_usercase(domain)

    datums_json = json.loads(request.POST.get('arbitrary_datums'))
    datums = [ArbitraryDatum.wrap(item) for item in datums_json]
    form.arbitrary_datums = datums

    response_json = {}
    app.save(response_json)
    response_json['propertiesMap'] = get_all_case_properties(app)
    return json_response(response_json)


@no_conflict_require_POST
@require_can_edit_apps
def edit_form_actions(request, domain, app_id, form_unique_id):
    app = get_app(domain, app_id)
    form = app.get_form(form_unique_id)
    module = form.get_module()
    old_load_from_form = form.actions.load_from_form
    form.actions = FormActions.wrap(json.loads(request.POST['actions']))
    add_properties_to_data_dictionary(domain, module.case_type, list(form.actions.update_case.update.keys()))
    if old_load_from_form:
        form.actions.load_from_form = old_load_from_form

    for condition in (form.actions.open_case.condition, form.actions.close_case.condition):
        if isinstance(condition.answer, str):
            condition.answer = condition.answer.strip('"\'')
    form.requires = request.POST.get('requires', form.requires)
    if actions_use_usercase(form.actions):
        if not is_usercase_in_use(domain):
            enable_usercase(domain)
        add_properties_to_data_dictionary(domain, USERCASE_TYPE, list(form.actions.usercase_update.update.keys()))

    response_json = {}
    app.save(response_json)
    response_json['propertiesMap'] = get_all_case_properties(app)
    response_json['usercasePropertiesMap'] = get_usercase_properties(app)
    return json_response(response_json)


@waf_allow('XSS_BODY')
@csrf_exempt
@api_domain_view
def edit_form_attr_api(request, domain, app_id, form_unique_id, attr):
    return _edit_form_attr(request, domain, app_id, form_unique_id, attr)


@waf_allow('XSS_BODY')
@login_or_digest
def edit_form_attr(request, domain, app_id, form_unique_id, attr):
    return _edit_form_attr(request, domain, app_id, form_unique_id, attr)


@no_conflict_require_POST
@require_permission(HqPermissions.edit_apps, login_decorator=None)
@capture_user_errors
def _edit_form_attr(request, domain, app_id, form_unique_id, attr):
    """
    Called to edit any (supported) form attribute, given by attr

    """
    # HELPME
    #
    # This method has been flagged for refactoring due to its complexity and
    # frequency of touches in changesets
    #
    # If you are writing code that touches this method, your changeset
    # should leave the method better than you found it.
    #
    # Please remove this flag when this method no longer triggers an 'E' or 'F'
    # classification from the radon code static analysis

    ajax = json.loads(request.POST.get('ajax', 'true'))
    resp = {}

    app = get_app(domain, app_id)
    try:
        form = app.get_form(form_unique_id)
    except FormNotFoundException as e:
        if ajax:
            return HttpResponseBadRequest(str(e))
        else:
            messages.error(request, _("There was an error saving, please try again!"))
            return back_to_main(request, domain, app_id=app_id)
    lang = request.COOKIES.get('lang', app.langs[0])

    def should_edit(attribute):
        return attribute in request.POST

    if 'sha1' in request.POST and (should_edit("xform") or "xform" in request.FILES):
        conflict = _get_xform_conflict_response(form, request.POST['sha1'])
        if conflict is not None:
            return conflict

    if should_edit("name"):
        name = request.POST['name']
        form.name[lang] = name
        if not form.form_type == "shadow_form":
            xform = form.wrapped_xform()
            if xform.exists():
                xform.set_name(name)
                save_xform(app, form, xform.render())
        resp['update'] = {'.variable-form_name': clean_trans(form.name, [lang])}

    if should_edit('comment'):
        form.comment = request.POST['comment']

    if should_edit("xform") or "xform" in request.FILES:
        try:
            # support FILES for upload and POST for ajax post from Vellum
            try:
                xform = request.FILES.get('xform').read()
            except Exception:
                xform = request.POST.get('xform')
            else:
                try:
                    xform = str(xform, encoding="utf-8")
                except Exception:
                    raise Exception("Error uploading form: Please make sure your form is encoded in UTF-8")

            if request.POST.get('cleanup', False):
                try:
                    # First, we strip all newlines and reformat the DOM.
                    px = parseString(xform.replace('\r\n', '')).toprettyxml()
                    # Then we remove excess newlines from the DOM output.
                    text_re = re.compile(r'>\n\s+([^<>\s].*?)\n\s+</', re.DOTALL)
                    prettyXml = text_re.sub(r'>\g<1></', px)
                    xform = prettyXml
                except Exception:
                    pass
            if xform:
                if isinstance(xform, str):
                    xform = xform.encode('utf-8')
                save_xform(app, form, xform)
            else:
                raise Exception("You didn't select a form to upload")
        except Exception as e:
            notify_exception(request, str(e))
            if ajax:
                return HttpResponseBadRequest(str(e))
            else:
                messages.error(request, str(e))
    if should_edit("references") or should_edit("case_references"):
        form.case_references = _get_case_references(request.POST)
    if should_edit("show_count"):
        show_count = request.POST['show_count']
        form.show_count = True if show_count == "True" else False
    if should_edit("put_in_root"):
        put_in_root = request.POST['put_in_root']
        form.put_in_root = True if put_in_root == "True" else False
    if should_edit('form_filter'):
        form.form_filter = request.POST['form_filter']
    if should_edit('post_form_workflow'):
        form.post_form_workflow = request.POST['post_form_workflow']
    if should_edit('auto_gps_capture'):
        form.auto_gps_capture = request.POST['auto_gps_capture'] == 'true'
    if should_edit('is_release_notes_form'):
        form.is_release_notes_form = request.POST['is_release_notes_form'] == 'true'
    if should_edit('enable_release_notes'):
        form.enable_release_notes = request.POST['enable_release_notes'] == 'true'
        if not form.is_release_notes_form and form.enable_release_notes:
            raise AppMisconfigurationError(_(
                "You can't enable a form as release notes without allowing it as "
                "a release notes form <TODO messaging>"
            ))
    if (should_edit("form_links_xpath_expressions")
            and should_edit("form_links_form_ids")
            and domain_has_privilege(domain, privileges.FORM_LINK_WORKFLOW)):
        form_link_data = zip(
            request.POST.getlist('form_links_xpath_expressions'),
            request.POST.getlist('form_links_form_ids'),
            [
                json.loads(datum_json) if datum_json else []
                for datum_json in request.POST.getlist('datums_json')
            ],
        )
        module_unique_ids = [m.unique_id for m in app.get_modules()]
        form_links = []
        for link in form_link_data:
            xpath, unique_id, datums = link
            if '.' in unique_id:
                form_module_id, form_id = unique_id.split('.')
                module_unique_id = None
            else:
                form_id = unique_id if unique_id not in module_unique_ids else None
                module_unique_id = unique_id if unique_id in module_unique_ids else None
                form_module_id = None
            form_links.append(FormLink(
                xpath=xpath,
                form_id=form_id,
                form_module_id=form_module_id,
                module_unique_id=module_unique_id,
                datums=[
                    FormDatum(name=datum['name'], xpath=datum['xpath'])
                    for datum in datums
                ]
            ))
        form.form_links = form_links

    if should_edit('post_form_workflow_fallback'):
        form.post_form_workflow_fallback = request.POST.get('post_form_workflow_fallback')

    if should_edit('custom_instances'):
        instances = json.loads(request.POST.get('custom_instances'))
        try:  # validate that custom instances can be added into the XML
            for instance in instances:
                etree.fromstring(
                    "<instance id='{}' src='{}' />".format(
                        instance.get('instanceId'),
                        instance.get('instancePath')
                    )
                )
        except etree.XMLSyntaxError as error:
            raise AppMisconfigurationError(
                _("There was an issue with your custom instances: {}").format(error)
            )

        form.custom_instances = [
            CustomInstance(
                instance_id=instance.get("instanceId"),
                instance_path=instance.get("instancePath"),
            ) for instance in instances
        ]

    if should_edit("custom_assertions"):
        form.custom_assertions = validate_custom_assertions(
            request.POST.get('custom_assertions'),
            form.custom_assertions,
            lang,
        )

    if should_edit("shadow_parent"):
        form.shadow_parent_form_id = request.POST['shadow_parent']

    if should_edit("custom_icon_form"):
        handle_custom_icon_edits(request, form, lang)

    if should_edit('session_endpoint_id'):
        raw_endpoint_id = request.POST['session_endpoint_id']
        set_session_endpoint(form, raw_endpoint_id, app)

    if should_edit('access_hidden_forms'):
        form.respect_relevancy = not ('true' in request.POST.getlist('access_hidden_forms'))

    if should_edit('function_datum_endpoints'):
        if request.POST['function_datum_endpoints']:
            form.function_datum_endpoints = request.POST['function_datum_endpoints'].replace(" ", "").split(",")
        else:
            form.function_datum_endpoints = []

    handle_media_edits(request, form, should_edit, resp, lang)

    app.save(resp)
    notify_form_changed(domain, request.couch_user, app_id, form_unique_id)
    if ajax:
        return HttpResponse(json.dumps(resp))
    else:
        return back_to_main(request, domain, app_id=app_id, form_unique_id=form_unique_id)


@no_conflict_require_POST
@require_can_edit_apps
def new_form(request, domain, app_id, module_unique_id):
    """
    Adds a form to an app (under a module)
    """
    app = get_app(domain, app_id)

    try:
        module = app.get_module_by_unique_id(module_unique_id)
    except ModuleNotFoundException:
        raise HttpResponseBadRequest

    lang = request.COOKIES.get('lang', app.langs[0])
    form_type = request.POST.get('form_type', 'form')
    case_action = request.POST.get('case_action', 'none')

    if case_action == 'open':
        name = _('Register')
    elif case_action == 'update':
        name = _('Followup')
    elif module.is_training_module:
        name = _('Lesson')
    else:
        name = _('Survey')

    if form_type == "shadow":
        if module.module_type == "advanced":
            form = module.new_shadow_form(name, lang)
        else:
            raise Exception("Shadow forms may only be created under shadow modules")
    else:
        form = module.new_form(name, lang)

    if form_type != "shadow":
        if case_action == 'update':
            form.requires = 'case'
            form.actions.update_case = UpdateCaseAction(
                condition=FormActionCondition(type='always'))
        elif case_action == 'open':
            form.actions.open_case = OpenCaseAction(
                condition=FormActionCondition(type='always'))
            form.actions.update_case = UpdateCaseAction(
                condition=FormActionCondition(type='always'))

    app.save()
    return back_to_main(
        request, domain,
        app_id=app.id,
        module_unique_id=module.unique_id,
        form_unique_id=form.unique_id
    )


@waf_allow('XSS_BODY')
@no_conflict_require_POST
@login_or_digest
@require_permission(HqPermissions.edit_apps, login_decorator=None)
@track_domain_request(calculated_prop='cp_n_saved_app_changes')
def patch_xform(request, domain, app_id, form_unique_id):
    patch = request.POST['patch']
    sha1_checksum = request.POST['sha1']
    case_references = _get_case_references(request.POST)

    app = get_app(domain, app_id)
    form = app.get_form(form_unique_id)

    conflict = _get_xform_conflict_response(form, sha1_checksum)
    if conflict is not None:
        return conflict

    xml = apply_patch(patch, form.source)

    try:
        xml = save_xform(app, form, xml.encode('utf-8'))
    except XFormException:
        return JsonResponse({'status': 'error'}, status=HttpResponseBadRequest.status_code)

    if "case_references" in request.POST or "references" in request.POST:
        form.case_references = case_references

    response_json = {
        'status': 'ok',
        'sha1': hashlib.sha1(xml).hexdigest()
    }
    app.save(response_json)
    notify_form_changed(domain, request.couch_user, app_id, form_unique_id)
    return JsonResponse(response_json)


def apply_patch(patch, text):
    dmp = diff_match_patch()
    return dmp.patch_apply(dmp.patch_fromText(patch), text)[0]


def _get_xform_conflict_response(form, sha1_checksum):
    form_xml = form.source
    if hashlib.sha1(form_xml.encode('utf-8')).hexdigest() != sha1_checksum:
        return json_response({'status': 'conflict', 'xform': form_xml})
    return None


@require_GET
@require_can_edit_apps
def get_xform_source(request, domain, app_id, form_unique_id):
    app = get_app(domain, app_id)
    try:
        form = app.get_form(form_unique_id)
    except IndexError:
        raise Http404()

    lang = request.COOKIES.get('lang', app.langs[0])
    source = form.source
    response = HttpResponse(source)
    response['Content-Type'] = "application/xml"
    filename = form.default_name()
    for lc in [lang] + app.langs:
        if lc in form.name:
            filename = form.name[lc]
            break
    set_file_download(response, "%s.xml" % unidecode(filename))
    return response


@require_GET
@require_can_edit_apps
def get_form_questions(request, domain, app_id):
    form_unique_id = request.GET.get('form_unique_id')
    module_id_temp = request.GET.get('module_id')
    form_id_temp = request.GET.get('form_id')
    try:
        app = get_app(domain, app_id)
        if module_id_temp is not None and form_id_temp is not None:
            # temporary fallback
            form = app.get_module(module_id_temp).get_form(form_id_temp)
        else:
            form = app.get_form(form_unique_id)
        lang, langs = get_langs(request, app)
    except FormNotFoundException:
        raise Http404()
    xform_questions = form.get_questions(langs, include_triggers=True)
    return json_response(xform_questions)


def get_apps_modules(domain, current_app_id=None, current_module_id=None, app_doc_types=('Application',)):
    """
    Returns a domain's Applications and their modules.

    If current_app_id and current_module_id are given, "is_current" is
    set to True for them. The interface uses this to select the current
    app and module by default.

    Linked and remote apps are omitted. Use the app_doc_types parameter
    to change this behaviour. (Deleted apps are not returned because the
    underlying Couch view doesn't include them.)
    """
    return [
        {
            'app_id': app.id,
            'name': app.name,
            'is_current': app.id == current_app_id,
            'modules': [{
                'module_id': module.id,
                'name': clean_trans(module.name, app.langs),
                'is_current': module.unique_id == current_module_id,
            } for module in app.get_modules()]
        }
        for app in get_apps_in_domain(domain)
        # No linked, deleted or remote apps. (Use app.doc_type not
        # app.get_doc_type() so that the suffix isn't dropped.)
        if app.doc_type in app_doc_types
    ]


def get_form_view_context_and_template(request, domain, form, langs, current_lang, messages=messages):
    # HELPME
    #
    # This method has been flagged for refactoring due to its complexity and
    # frequency of touches in changesets
    #
    # If you are writing code that touches this method, your changeset
    # should leave the method better than you found it.
    #
    # Please remove this flag when this method no longer triggers an 'E' or 'F'
    # classification from the radon code static analysis

    xform_questions = []
    xform = None
    form_errors = []
    xform_validation_errored = False
    xform_validation_missing = False

    try:
        xform = form.wrapped_xform()
    except XFormException as e:
        form_errors.append("Error in form: %s" % e)
    except Exception as e:
        logging.exception(e)
        form_errors.append("Unexpected error in form: %s" % e)

    has_case_error = False
    if xform and xform.exists():
        if xform.already_has_meta():
            messages.warning(
                request,
                "This form has a meta block already! "
                "It may be replaced by CommCare HQ's standard meta block."
            )

        try:
            xform_questions = xform.get_questions(langs, include_triggers=True)
            form.validate_form()
        except etree.XMLSyntaxError as e:
            form_errors.append("Syntax Error: %s" % e)
        except AppEditingError as e:
            form_errors.append("Error in application: %s" % e)
        except XFormValidationError:
            xform_validation_errored = True
            # showing these messages is handled by validate_form_for_build ajax
        except XFormValidationFailed:
            xform_validation_missing = True
            messages.warning(request, _("Unable to validate form due to server error."))
        except XFormException as e:
            form_errors.append("Error in form: %s" % e)
        # any other kind of error should fail hard,
        # but for now there are too many for that to be practical
        except Exception as e:
            if settings.DEBUG:
                raise
            notify_exception(request, 'Unexpected Build Error')
            form_errors.append("Unexpected System Error: %s" % e)
        else:
            # remove upload questions (attachments) until MM Case Properties
            # are released to general public
            is_previewer = toggles.MM_CASE_PROPERTIES.enabled_for_request(request)
            xform_questions = [q for q in xform_questions
                               if q["tag"] != "upload" or is_previewer]

        if not form_errors and not xform_validation_missing and not xform_validation_errored:
            try:
                form_action_errors = form.validate_for_build()
                if not form_action_errors:
                    form.add_stuff_to_xform(xform)
            except CaseError as e:
                has_case_error = True
                messages.error(request, "Error in Case Management: %s" % e)
            except XFormException as e:
                messages.error(request, str(e))
            except Exception as e:
                if settings.DEBUG:
                    raise
                logging.exception(str(e))
                messages.error(request, "Unexpected Error: %s" % e)

    try:
        languages = xform.get_languages()
    except Exception:
        languages = []

    for err in form_errors:
        messages.error(request, err)

    module_case_types = []
    app = form.get_app()
    all_modules = list(app.get_modules())
    for module in all_modules:
        for case_type in module.get_case_types():
            module_case_types.append({
                'id': module.unique_id,
                'module_name': trans(module.name, langs),
                'case_type': case_type,
                'module_type': module.doc_type
            })
    module = form.get_module()

    if not form.unique_id:
        form.get_unique_id()
        app.save()

    allow_usercase = domain_has_privilege(request.domain, privileges.USERCASE)
    valid_index_names = list(DEFAULT_CASE_INDEX_IDENTIFIERS.values())
    if allow_usercase:
        valid_index_names.append(USERCASE_PREFIX[0:-1])     # strip trailing slash

    form_has_schedule = isinstance(form, AdvancedForm) and module.has_schedule

    try:
        case_properties_map = get_all_case_properties(app)
        usercase_properties_map = get_usercase_properties(app)
    except CaseError as e:
        case_properties_map = {}
        usercase_properties_map = {}
        if not has_case_error:
            messages.error(request, "Error in Case Management: %s" % e)

    form_workflows = {
        WORKFLOW_DEFAULT: _("Home Screen"),
        WORKFLOW_ROOT: _("First Menu"),
    }
    if not module.root_module_id or not module.root_module.is_multi_select():
        if not module.put_in_root:
            form_workflows[WORKFLOW_MODULE] = _("Menu: ") + trans(module.name, langs)
        if not (module.is_multi_select() or module_uses_inline_search(module)):
            form_workflows[WORKFLOW_PREVIOUS] = _("Previous Screen")
    if module.root_module_id and not module.root_module.put_in_root:
        if not module.root_module.is_multi_select():
            form_workflows[WORKFLOW_PARENT_MODULE] = _("Parent Menu: ") + trans(module.root_module.name, langs)
    allow_form_workflow = domain_has_privilege(domain, privileges.FORM_LINK_WORKFLOW)
    if allow_form_workflow or form.post_form_workflow == WORKFLOW_FORM:
        form_workflows[WORKFLOW_FORM] = _("Link to other form or menu")

    case_config_options = {
        'caseType': form.get_case_type(),
        'moduleCaseTypes': module_case_types,
        'propertiesMap': case_properties_map,
        'propertyDescriptions': get_case_property_description_dict(domain),
        'questions': xform_questions,
        'reserved_words': load_case_reserved_words(),
        'usercasePropertiesMap': usercase_properties_map,
    }
    context = {
        'nav_form': form,
        'xform_languages': languages,
        'form_errors': form_errors,
        'form_workflows': form_workflows,
        'xform_validation_errored': xform_validation_errored,
        'xform_validation_missing': xform_validation_missing,
        'allow_form_copy': isinstance(form, (Form, AdvancedForm)),
        'allow_form_filtering': not form_has_schedule,
        'allow_usercase': allow_usercase,
        'is_usercase_in_use': is_usercase_in_use(request.domain),
        'is_module_filter_enabled': app.enable_module_filtering,
        'is_training_module': module.is_training_module,
        'is_allowed_to_be_release_notes_form': form.is_allowed_to_be_release_notes_form,
        'root_requires_same_case': module.root_requires_same_case(),
        'is_case_list_form': form.is_case_list_form,
        'edit_name_url': reverse('edit_form_attr', args=[app.domain, app.id, form.unique_id, 'name']),
        'form_filter_patterns': {
            'case_substring': CASE_XPATH_SUBSTRING_MATCHES,
            'usercase_substring': USERCASE_XPATH_SUBSTRING_MATCHES,
        },
        'custom_instances': [
            {'instanceId': instance.instance_id, 'instancePath': instance.instance_path}
            for instance in form.custom_instances
        ],
        'custom_assertions': [
            {'test': assertion.test, 'text': assertion.text.get(current_lang)}
            for assertion in form.custom_assertions
        ],
        'form_icon': None,
        'session_endpoints_enabled': toggles.SESSION_ENDPOINTS.enabled(domain),
        'module_is_multi_select': module.is_multi_select(),
        'module_loads_registry_case': module_loads_registry_case(module),
    }

    if toggles.CUSTOM_ICON_BADGES.enabled(domain):
        context['form_icon'] = form.custom_icon if form.custom_icon else CustomIcon()

    if toggles.COPY_FORM_TO_APP.enabled_for_request(request):
        context['apps_modules'] = get_apps_modules(domain, app.id, module.unique_id)

    if allow_form_workflow:
        context.update(_get_form_link_context(app, module, form, langs))

    if isinstance(form, AdvancedForm):
        def commtrack_programs():
            if app.commtrack_enabled:
                programs = Program.by_domain(app.domain)
                return [{'value': program.get_id, 'label': program.name} for program in programs]
            else:
                return []

        all_programs = [{'value': '', 'label': _('All Programs')}]
        case_config_options.update({
            'commtrack_enabled': app.commtrack_enabled,
            'commtrack_programs': all_programs + commtrack_programs(),
            'module_id': module.unique_id,
            'save_url': reverse("edit_advanced_form_actions", args=[app.domain, app.id, form.unique_id]),
            'arbitrary_datums': form.arbitrary_datums,
        })
        if form.form_type == "shadow_form":
            case_config_options.update({
                'actions': form.extra_actions,
                'isShadowForm': True,
            })
        else:
            case_config_options.update({
                'actions': form.actions,
                'isShadowForm': False,
            })
        if getattr(module, 'has_schedule', False):
            schedule_options = get_schedule_context(form)
            schedule_options.update({
                'phase': schedule_options['schedule_phase'],
                'questions': xform_questions,
                'save_url': reverse("edit_visit_schedule", args=[app.domain, app.id, form.unique_id]),
                'schedule': form.schedule,
            })
            context.update({
                'schedule_options': schedule_options,
            })
    else:
        context.update({
            'show_custom_ref': toggles.APP_BUILDER_CUSTOM_PARENT_REF.enabled_for_request(request),
        })
        case_config_options.update({
            'actions': form.actions,
            'allowUsercase': allow_usercase,
            'save_url': reverse("edit_form_actions", args=[app.domain, app.id, form.unique_id]),
            'valid_index_names': valid_index_names,
        })

    context.update({'case_config_options': case_config_options})
    return "app_manager/form_view.html", context


def _get_form_link_context(app, module, form, langs):
    return {
        'linkable_forms': _get_linkable_forms_context(module, langs),
        'form_links': _get_form_links(app, form)
    }


def _get_form_links(app, form):
    """Augments the form link JSON with the 'unique_id' field
    which is dynamically generated.
    """
    links = []
    for link in form.form_links:
        link_context = link.to_json()
        try:
            link_context['uniqueId'] = link.get_unique_id(app)
        except FormNotFoundException:
            continue
        else:
            links.append(link_context)
    return links


def _get_linkable_forms_context(module, langs):
    def _module_name(module):
        return trans(module.name, langs)

    def _form_name(module, form):
        names = [_module_name(m) for m in _module_hierarchy(module)]
        module_names = " > ".join(names)
        form_name = trans(form.name, langs)
        return "{} > {}".format(module_names, form_name)

    def _module_hierarchy(module):
        if not module.root_module_id:
            return [module]
        else:
            return _module_hierarchy(module.root_module) + [module]

    linkable_items = []
    is_multi_select = module.is_multi_select()
    for candidate_module in module.get_app().get_modules():
        # Menus can be linked automatically if they're a top-level menu (no parent)
        # or their parent menu's case type matches the current menu's parent's case type.
        # Menus that use display-only forms can't be linked at all, since they don't have a
        # dedicated screen to navigate to. All other menus can be linked manually.
        if not candidate_module.put_in_root:
            is_top_level = candidate_module.root_module_id is None
            is_child_match = (
                not is_top_level
                and module.root_module_id is not None
                and module.root_module.case_type == candidate_module.root_module.case_type
            )
            parent_name = ""
            if candidate_module.root_module_id:
                parent_name = _module_name(candidate_module.root_module) + " > "
            auto_link = is_top_level or is_child_match
            if auto_link or toggles.FORM_LINK_ADVANCED_MODE.enabled(module.get_app().domain):
                linkable_items.append({
                    'unique_id': candidate_module.unique_id,
                    'name': parent_name + _module_name(candidate_module),
                    'auto_link': auto_link,
                    'allow_manual_linking': toggles.FORM_LINK_ADVANCED_MODE.enabled(module.get_app().domain),
                })

        for candidate_form in candidate_module.get_suite_forms():
            # Forms can be linked automatically if their module is the same case type as this module,
            # or if they belong to this module's parent module. All other forms can be linked manually.
            case_type_match = candidate_module.case_type == module.case_type
            is_parent = candidate_module.unique_id == module.root_module_id
            linkable_items.append({
                # this is necessary to disambiguate forms in shadow modules
                'unique_id': f'{candidate_module.unique_id}.{candidate_form.unique_id}',
                'name': _form_name(candidate_module, candidate_form),
                'auto_link': not is_multi_select and (case_type_match or is_parent),
                'allow_manual_linking': True,
            })

    return sorted(linkable_items, key=lambda link: link['name'])


@require_can_edit_apps
def get_form_datums(request, domain, app_id):
    form_id = request.GET.get('form_id')
    try:
        datums = _get_form_datums(domain, app_id, form_id)
    except Exception:
        notify_exception(request, "Error fetching form datums", details={
            "domain": domain, "app_id": app_id, "form_id": form_id
        })
        raise
    return JsonResponse(datums, safe=False)


def _get_form_datums(domain, app_id, form_id):
    from corehq.apps.app_manager.suite_xml.sections.entries import EntriesHelper
    app = get_app(domain, app_id)

    try:
        module_id, form_id = form_id.split('.')
    except ValueError:
        raise Http400

    try:
        module = app.get_module_by_unique_id(module_id)
        form = app.get_form(form_id)
    except (ModuleNotFoundException, FormNotFoundException) as e:
        raise Http404(str(e))

    def make_datum(datum):
        return {'name': datum.id, 'case_type': datum.case_type}

    helper = EntriesHelper(app)
    datums = [
        make_datum(datum) for datum in helper.get_datums_meta_for_form_generic(form, module)
        if datum.requires_selection
    ]
    return datums


@require_GET
@require_deploy_apps
def view_form_legacy(request, domain, app_id, module_id, form_id):
    """
    This view has been kept around to not break any documentation on example apps
    and partner-distributed documentation on existing apps.
    PLEASE DO NOT DELETE.
    """
    from corehq.apps.app_manager.views.view_generic import view_generic
    return view_generic(request, domain, app_id, module_id, form_id)


@require_GET
@require_deploy_apps
def view_form(request, domain, app_id, form_unique_id):
    from corehq.apps.app_manager.views.view_generic import view_generic
    return view_generic(
        request, domain, app_id,
        form_unique_id=form_unique_id
    )


def _get_case_references(data):
    if "references" in data:
        # old/deprecated format
        preload = json.loads(data['references'])["preload"]
        refs = {
            "load": {k: [v] for k, v in preload.items()}
        }
    else:
        refs = json.loads(data.get('case_references', '{}'))

    try:
        references = CaseReferences.wrap(refs)
        references.validate()
        return references
    except Exception:
        raise ValueError("bad case references data: {!r}".format(refs))


class FormHasSubmissionsView(LoginAndDomainMixin, View):
    urlname = 'form_has_submissions'

    def get(self, request, domain, app_id, form_unique_id):
        app = get_app(domain, app_id)
        try:
            form = app.get_form(form_unique_id)
        except FormNotFoundException:
            has_submissions = False
        else:
            has_submissions = form_has_submissions(domain, app_id, form.xmlns)
        return JsonResponse({
            'form_has_submissions': has_submissions,
        })
