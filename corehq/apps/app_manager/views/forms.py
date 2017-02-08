from builtins import zip
from builtins import str
from past.builtins import basestring
import logging
import hashlib
import re
import json
import uuid
from xml.dom.minidom import parseString
from couchdbkit import ResourceNotFound
from django.shortcuts import render
import itertools

from django.template.loader import render_to_string
from lxml import etree
from diff_match_patch import diff_match_patch
from django.utils.translation import ugettext as _
from django.http import HttpResponse, Http404, HttpResponseBadRequest
from django.core.urlresolvers import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET
from django.conf import settings
from django.contrib import messages
from unidecode import unidecode
from corehq.apps.app_manager.views.media_utils import handle_media_edits
from corehq.apps.app_manager.views.notifications import notify_form_changed
from corehq.apps.app_manager.views.schedules import get_schedule_context

from corehq.apps.app_manager.views.utils import back_to_main, \
    CASE_TYPE_CONFLICT_MSG, get_langs

from corehq import toggles, privileges
from corehq.apps.accounting.utils import domain_has_privilege
from corehq.apps.app_manager.exceptions import (
    BlankXFormError,
    ConflictingCaseTypeError,
    FormNotFoundException, XFormValidationFailed)
from corehq.apps.app_manager.templatetags.xforms_extras import trans
from corehq.apps.programs.models import Program
from corehq.apps.app_manager.util import (
    get_all_case_properties,
    save_xform,
    is_usercase_in_use,
    enable_usercase,
    actions_use_usercase,
    advanced_actions_use_usercase,
    get_usercase_properties,
    CASE_XPATH_PATTERN_MATCHES,
    CASE_XPATH_SUBSTRING_MATCHES,
    USER_CASE_XPATH_PATTERN_MATCHES,
    USER_CASE_XPATH_SUBSTRING_MATCHES,
    get_app_manager_template,
)
from corehq.apps.app_manager.xform import (
    CaseError,
    XFormException,
    XFormValidationError)
from corehq.apps.reports.formdetails.readable import FormQuestionResponse, \
    questions_in_hierarchy
from corehq.apps.users.decorators import require_permission
from corehq.apps.users.models import Permissions
from corehq.util.view_utils import set_file_download
from dimagi.utils.logging import notify_exception
from dimagi.utils.web import json_response
from corehq.apps.domain.decorators import (
    login_or_digest, api_domain_view
)
from corehq.apps.app_manager.const import USERCASE_TYPE
from corehq.apps.app_manager.dbaccessors import get_app
from corehq.apps.app_manager.models import (
    AdvancedForm,
    AdvancedFormActions,
    AppEditingError,
    CareplanForm,
    DeleteFormRecord,
    Form,
    FormActions,
    FormActionCondition,
    FormDatum,
    FormLink,
    UpdateCaseAction,
    IncompatibleFormTypeException,
    ModuleNotFoundException,
    load_case_reserved_words,
    WORKFLOW_FORM,
    CustomInstance,
    CaseReferences)
from corehq.apps.app_manager.decorators import no_conflict_require_POST, \
    require_can_edit_apps, require_deploy_apps
from corehq.apps.data_dictionary.util import add_properties_to_data_dictionary
from corehq.apps.tour import tours


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
    return back_to_main(
        request, domain, app_id=app_id,
        module_id=app.get_module_by_unique_id(module_unique_id).id)


@no_conflict_require_POST
@require_can_edit_apps
def copy_form(request, domain, app_id, module_id, form_id):
    app = get_app(domain, app_id)
    to_module_id = int(request.POST['to_module_id'])
    try:
        app.copy_form(int(module_id), int(form_id), to_module_id)
    except ConflictingCaseTypeError:
        messages.warning(request, CASE_TYPE_CONFLICT_MSG, extra_tags="html")
        app.save()
    except BlankXFormError:
        # don't save!
        messages.error(request, _('We could not copy this form, because it is blank.'
                                  'In order to copy this form, please add some questions first.'))
    except IncompatibleFormTypeException:
        # don't save!
        messages.error(request, _('This form could not be copied because it '
                                  'is not compatible with the selected module.'))
    else:
        app.save()

    return back_to_main(request, domain, app_id=app_id, module_id=module_id,
                        form_id=form_id)


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
def edit_advanced_form_actions(request, domain, app_id, module_id, form_id):
    app = get_app(domain, app_id)
    form = app.get_module(module_id).get_form(form_id)
    json_loads = json.loads(request.POST.get('actions'))
    actions = AdvancedFormActions.wrap(json_loads)
    form.actions = actions
    for action in actions.load_update_cases:
        add_properties_to_data_dictionary(domain, action.case_type, list(action.case_properties))
    if advanced_actions_use_usercase(form.actions) and not is_usercase_in_use(domain):
        enable_usercase(domain)
    response_json = {}
    app.save(response_json)
    response_json['propertiesMap'] = get_all_case_properties(app)
    return json_response(response_json)


@no_conflict_require_POST
@require_can_edit_apps
def edit_form_actions(request, domain, app_id, module_id, form_id):
    app = get_app(domain, app_id)
    module = app.get_module(module_id)
    form = module.get_form(form_id)
    old_load_from_form = form.actions.load_from_form
    form.actions = FormActions.wrap(json.loads(request.POST['actions']))
    add_properties_to_data_dictionary(domain, module.case_type, list(form.actions.update_case.update))
    if old_load_from_form:
        form.actions.load_from_form = old_load_from_form

    for condition in (form.actions.open_case.condition, form.actions.close_case.condition):
        if isinstance(condition.answer, basestring):
            condition.answer = condition.answer.strip('"\'')
    form.requires = request.POST.get('requires', form.requires)
    if actions_use_usercase(form.actions):
        if not is_usercase_in_use(domain):
            enable_usercase(domain)
        add_properties_to_data_dictionary(domain, USERCASE_TYPE, list(form.actions.usercase_update.update))

    response_json = {}
    app.save(response_json)
    response_json['propertiesMap'] = get_all_case_properties(app)
    response_json['usercasePropertiesMap'] = get_usercase_properties(app)
    return json_response(response_json)


@no_conflict_require_POST
@require_can_edit_apps
def edit_careplan_form_actions(request, domain, app_id, module_id, form_id):
    app = get_app(domain, app_id)
    form = app.get_module(module_id).get_form(form_id)
    transaction = json.loads(request.POST.get('transaction'))

    for question in transaction['fixedQuestions']:
        setattr(form, question['name'], question['path'])

    def to_dict(properties):
        return dict((p['key'], p['path']) for p in properties)

    form.custom_case_updates = to_dict(transaction['case_properties'])
    form.case_preload = to_dict(transaction['case_preload'])

    response_json = {}
    app.save(response_json)
    return json_response(response_json)


@csrf_exempt
@api_domain_view
def edit_form_attr_api(request, domain, app_id, unique_form_id, attr):
    return _edit_form_attr(request, domain, app_id, unique_form_id, attr)


@login_or_digest
def edit_form_attr(request, domain, app_id, unique_form_id, attr):
    return _edit_form_attr(request, domain, app_id, unique_form_id, attr)


@no_conflict_require_POST
@require_permission(Permissions.edit_apps, login_decorator=None)
def _edit_form_attr(request, domain, app_id, unique_form_id, attr):
    """
    Called to edit any (supported) form attribute, given by attr

    """

    ajax = json.loads(request.POST.get('ajax', 'true'))
    resp = {}

    app = get_app(domain, app_id)
    try:
        form = app.get_form(unique_form_id)
    except FormNotFoundException as e:
        if ajax:
            return HttpResponseBadRequest(str(e))
        else:
            messages.error(request, _("There was an error saving, please try again!"))
            return back_to_main(request, domain, app_id=app_id)
    lang = request.COOKIES.get('lang', app.langs[0])

    def should_edit(attribute):
        return attribute in request.POST

    if should_edit("name"):
        name = request.POST['name']
        form.name[lang] = name
        xform = form.wrapped_xform()
        if xform.exists():
            xform.set_name(name)
            save_xform(app, form, xform.render())
        resp['update'] = {'.variable-form_name': trans(form.name, [lang], use_delim=False)}
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
                    text_re = re.compile('>\n\s+([^<>\s].*?)\n\s+</', re.DOTALL)
                    prettyXml = text_re.sub('>\g<1></', px)
                    xform = prettyXml
                except Exception:
                    pass
            if xform:
                save_xform(app, form, xform)
            else:
                raise Exception("You didn't select a form to upload")
        except Exception as e:
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
    if should_edit('no_vellum'):
        form.no_vellum = request.POST['no_vellum'] == 'true'
    if (should_edit("form_links_xpath_expressions") and
            should_edit("form_links_form_ids") and
            toggles.FORM_LINK_WORKFLOW.enabled(domain)):
        form_links = list(zip(
            request.POST.getlist('form_links_xpath_expressions'),
            request.POST.getlist('form_links_form_ids'),
            [
                json.loads(datum_json) if datum_json else []
                for datum_json in request.POST.getlist('datums_json')
            ],
        ))
        form.form_links = [FormLink(
            xpath=link[0],
            form_id=link[1],
            datums=[
                FormDatum(name=datum['name'], xpath=datum['xpath'])
                for datum in link[2]
            ]
        ) for link in form_links]

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
            return json_response(
                {'message': _("There was an issue with your custom instances: {}").format(error.message)},
                status_code=400
            )

        form.custom_instances = [
            CustomInstance(
                instance_id=instance.get("instanceId"),
                instance_path=instance.get("instancePath"),
            ) for instance in instances
        ]

    handle_media_edits(request, form, should_edit, resp, lang)

    app.save(resp)
    notify_form_changed(domain, request.couch_user, app_id, unique_form_id)
    if ajax:
        return HttpResponse(json.dumps(resp))
    else:
        return back_to_main(request, domain, app_id=app_id, unique_form_id=unique_form_id)


@no_conflict_require_POST
@require_can_edit_apps
def new_form(request, domain, app_id, module_id):
    "Adds a form to an app (under a module)"
    app = get_app(domain, app_id)
    lang = request.COOKIES.get('lang', app.langs[0])
    name = request.POST.get('name')
    form = app.new_form(module_id, name, lang)

    blank_form = render_to_string("app_manager/blank_form.xml", context={
        'xmlns': str(uuid.uuid4()).upper(),
        'name': form.name[lang],
        'lang': lang,
    })
    form.source = blank_form

    if toggles.APP_MANAGER_V2.enabled(domain):
        case_action = request.POST.get('case_action', 'none')
        if case_action == 'update':
            form.requires = 'case'
            form.actions.update_case = UpdateCaseAction(
                condition=FormActionCondition(type='always'))

    app.save()
    # add form_id to locals()
    form_id = form.id
    response = back_to_main(request, domain, app_id=app_id, module_id=module_id,
                            form_id=form_id)
    return response


@no_conflict_require_POST
@login_or_digest
@require_permission(Permissions.edit_apps, login_decorator=None)
def patch_xform(request, domain, app_id, unique_form_id):
    patch = request.POST['patch']
    sha1_checksum = request.POST['sha1']
    case_references = _get_case_references(request.POST)

    app = get_app(domain, app_id)
    form = app.get_form(unique_form_id)

    current_xml = form.source
    if hashlib.sha1(current_xml.encode('utf-8')).hexdigest() != sha1_checksum:
        return json_response({'status': 'conflict', 'xform': current_xml})

    dmp = diff_match_patch()
    xform, _ = dmp.patch_apply(dmp.patch_fromText(patch), current_xml)
    save_xform(app, form, xform)
    if "case_references" in request.POST or "references" in request.POST:
        form.case_references = case_references

    response_json = {
        'status': 'ok',
        'sha1': hashlib.sha1(form.source.encode('utf-8')).hexdigest()
    }
    app.save(response_json)
    notify_form_changed(domain, request.couch_user, app_id, unique_form_id)
    return json_response(response_json)


@require_GET
@require_can_edit_apps
def get_xform_source(request, domain, app_id, module_id, form_id):
    app = get_app(domain, app_id)
    try:
        form = app.get_module(module_id).get_form(form_id)
    except IndexError:
        raise Http404()
    return _get_xform_source(request, app, form)


@require_GET
@require_can_edit_apps
def get_form_questions(request, domain, app_id):
    module_id = request.GET.get('module_id')
    form_id = request.GET.get('form_id')
    try:
        app = get_app(domain, app_id)
        form = app.get_module(module_id).get_form(form_id)
        lang, langs = get_langs(request, app)
    except (ModuleNotFoundException, IndexError):
        raise Http404()
    xform_questions = form.get_questions(langs, include_triggers=True)
    return json_response(xform_questions)


def get_form_view_context_and_template(request, domain, form, langs, messages=messages):
    xform_questions = []
    xform = None
    form_errors = []
    xform_validation_errored = False
    xform_validation_missing = False

    try:
        xform = form.wrapped_xform()
    except XFormException as e:
        form_errors.append(u"Error in form: %s" % e)
    except Exception as e:
        logging.exception(e)
        form_errors.append(u"Unexpected error in form: %s" % e)

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
            form_errors.append(u"Syntax Error: %s" % e)
        except AppEditingError as e:
            form_errors.append(u"Error in application: %s" % e)
        except XFormValidationError:
            xform_validation_errored = True
            # showing these messages is handled by validate_form_for_build ajax
            pass
        except XFormValidationFailed:
            xform_validation_missing = True
            messages.warning(request, _("Unable to validate form due to server error."))
        except XFormException as e:
            form_errors.append(u"Error in form: %s" % e)
        # any other kind of error should fail hard,
        # but for now there are too many for that to be practical
        except Exception as e:
            if settings.DEBUG:
                raise
            notify_exception(request, 'Unexpected Build Error')
            form_errors.append(u"Unexpected System Error: %s" % e)
        else:
            # remove upload questions (attachemnts) until MM Case Properties
            # are released to general public
            is_previewer = toggles.MM_CASE_PROPERTIES.enabled(request.user.username)
            xform_questions = [q for q in xform_questions
                               if q["tag"] != "upload" or is_previewer]

        if not form_errors and not xform_validation_missing and not xform_validation_errored:
            try:
                form_action_errors = form.validate_for_build()
                if not form_action_errors:
                    form.add_stuff_to_xform(xform)
            except CaseError as e:
                messages.error(request, u"Error in Case Management: %s" % e)
            except XFormException as e:
                messages.error(request, str(e))
            except Exception as e:
                if settings.DEBUG:
                    raise
                logging.exception(str(e))
                messages.error(request, u"Unexpected Error: %s" % e)

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

    if not form.unique_id:
        form.get_unique_id()
        app.save()

    form_has_schedule = isinstance(form, AdvancedForm) and form.get_module().has_schedule
    context = {
        'nav_form': form,
        'xform_languages': languages,
        "xform_questions": xform_questions,
        'case_reserved_words_json': load_case_reserved_words(),
        'module_case_types': module_case_types,
        'form_errors': form_errors,
        'xform_validation_errored': xform_validation_errored,
        'xform_validation_missing': xform_validation_missing,
        'allow_cloudcare': isinstance(form, Form),
        'allow_form_copy': isinstance(form, (Form, AdvancedForm)),
        'allow_form_filtering': not isinstance(form, CareplanForm) and not form_has_schedule,
        'allow_form_workflow': not isinstance(form, CareplanForm),
        'uses_form_workflow': form.post_form_workflow == WORKFLOW_FORM,
        'allow_usercase': (
            domain_has_privilege(request.domain, privileges.USER_CASE)
            and not toggles.USER_TESTING_SIMPLIFY.enabled(request.domain)
        ),
        'is_usercase_in_use': is_usercase_in_use(request.domain),
        'is_module_filter_enabled': app.enable_module_filtering,
        'is_case_list_form': form.is_case_list_form,
        'edit_name_url': reverse('edit_form_attr', args=[app.domain, app.id, form.unique_id, 'name']),
        'case_xpath_pattern_matches': CASE_XPATH_PATTERN_MATCHES,
        'case_xpath_substring_matches': CASE_XPATH_SUBSTRING_MATCHES,
        'user_case_xpath_pattern_matches': USER_CASE_XPATH_PATTERN_MATCHES,
        'user_case_xpath_substring_matches': USER_CASE_XPATH_SUBSTRING_MATCHES,
        'custom_instances': [
            {'instanceId': instance.instance_id, 'instancePath': instance.instance_path}
            for instance in form.custom_instances
        ],
        'can_preview_form': request.couch_user.has_permission(domain, 'edit_data')
    }

    if tours.NEW_APP.is_enabled(request.user):
        request.guided_tour = tours.NEW_APP.get_tour_data()

    if context['allow_form_workflow'] and toggles.FORM_LINK_WORKFLOW.enabled(domain):
        module = form.get_module()

        def qualified_form_name(form, auto_link):
            module_name = trans(form.get_module().name, langs)
            form_name = trans(form.name, langs)
            star = '* ' if auto_link else '  '
            return u"{}{} -> {}".format(star, module_name, form_name)

        modules = [m for m in all_modules if m.case_type == module.case_type]
        if getattr(module, 'root_module_id', None) and module.root_module not in modules:
            modules.append(module.root_module)
        auto_linkable_forms = list(itertools.chain.from_iterable(list(m.get_forms()) for m in modules))

        def linkable_form(candidate_form):
            auto_link = candidate_form in auto_linkable_forms
            return {
                'unique_id': candidate_form.unique_id,
                'name': qualified_form_name(candidate_form, auto_link),
                'auto_link': auto_link
            }

        context['linkable_forms'] = [
            linkable_form(candidate_form) for candidate_module in all_modules
            for candidate_form in candidate_module.get_forms()
        ]

    if isinstance(form, CareplanForm):
        context.update({
            'mode': form.mode,
            'fixed_questions': form.get_fixed_questions(),
            'custom_case_properties': [
                {'key': key, 'path': path} for key, path in form.custom_case_updates.items()
            ],
            'case_preload': [
                {'key': key, 'path': path} for key, path in form.case_preload.items()
            ],
        })
        template = get_app_manager_template(
            domain,
            "app_manager/v1/form_view_careplan.html",
            "app_manager/v2/form_view_careplan.html",
        )
        return template, context
    elif isinstance(form, AdvancedForm):
        def commtrack_programs():
            if app.commtrack_enabled:
                programs = Program.by_domain(app.domain)
                return [{'value': program.get_id, 'label': program.name} for program in programs]
            else:
                return []

        all_programs = [{'value': '', 'label': _('All Programs')}]
        context.update({
            'show_custom_ref': toggles.APP_BUILDER_CUSTOM_PARENT_REF.enabled(request.user.username),
            'commtrack_programs': all_programs + commtrack_programs(),
        })
        context.update(get_schedule_context(form))
        template = get_app_manager_template(
            domain,
            "app_manager/v1/form_view_advanced.html",
            "app_manager/v2/form_view_advanced.html",
        )
        return template, context
    else:
        context.update({
            'show_custom_ref': toggles.APP_BUILDER_CUSTOM_PARENT_REF.enabled(request.user.username),
        })
        template = get_app_manager_template(
            domain,
            "app_manager/v1/form_view.html",
            "app_manager/v2/form_view.html",
        )
        return template, context


@require_can_edit_apps
def get_form_datums(request, domain, app_id):
    from corehq.apps.app_manager.suite_xml.sections.entries import EntriesHelper
    form_id = request.GET.get('form_id')
    app = get_app(domain, app_id)
    form = app.get_form(form_id)

    def make_datum(datum):
        return {'name': datum.datum.id, 'case_type': datum.case_type}

    helper = EntriesHelper(app)
    datums = []
    root_module = form.get_module().root_module
    if root_module:
        datums.extend([
            make_datum(datum) for datum in helper.get_datums_meta_for_form_generic(root_module.get_form(0))
            if datum.requires_selection
        ])
    datums.extend([
        make_datum(datum) for datum in helper.get_datums_meta_for_form_generic(form)
        if datum.requires_selection
    ])
    return json_response(datums)


@require_GET
@require_deploy_apps
def view_form(request, domain, app_id, module_id, form_id):
    from corehq.apps.app_manager.views.view_generic import view_generic
    return view_generic(request, domain, app_id, module_id, form_id)


def _get_xform_source(request, app, form, filename="form.xml"):
    download = json.loads(request.GET.get('download', 'false'))
    lang = request.COOKIES.get('lang', app.langs[0])
    source = form.source
    if download:
        response = HttpResponse(source)
        response['Content-Type'] = "application/xml"
        for lc in [lang] + app.langs:
            if lc in form.name:
                filename = "%s.xml" % unidecode(form.name[lc])
                break
        set_file_download(response, filename)
        return response
    else:
        return json_response(source)


def xform_display(request, domain, form_unique_id):
    try:
        form, app = Form.get_form(form_unique_id, and_app=True)
    except ResourceNotFound:
        raise Http404()
    if domain != app.domain:
        raise Http404()
    langs = [request.GET.get('lang')] + app.langs

    questions = form.get_questions(langs, include_triggers=True,
                                   include_groups=True)

    if request.GET.get('format') == 'html':
        questions = [FormQuestionResponse(q) for q in questions]
        template = get_app_manager_template(
            domain,
            'app_manager/v1/xform_display.html',
            'app_manager/v2/xform_display.html',
        )
        return render(request, template, {
            'questions': questions_in_hierarchy(questions)
        })
    else:
        return json_response(questions)


@require_can_edit_apps
def form_casexml(request, domain, form_unique_id):
    try:
        form, app = Form.get_form(form_unique_id, and_app=True)
    except ResourceNotFound:
        raise Http404()
    if domain != app.domain:
        raise Http404()
    return HttpResponse(form.create_casexml())


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
