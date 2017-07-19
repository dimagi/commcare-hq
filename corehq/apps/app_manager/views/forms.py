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
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET
from django.conf import settings
from django.contrib import messages
from unidecode import unidecode
from corehq.apps.app_manager.app_schemas.case_properties import get_all_case_properties, \
    get_usercase_properties
from corehq.apps.app_manager.views.media_utils import handle_media_edits
from corehq.apps.app_manager.views.notifications import notify_form_changed
from corehq.apps.app_manager.views.schedules import get_schedule_context

from corehq.apps.app_manager.views.utils import back_to_main, \
    CASE_TYPE_CONFLICT_MSG, get_langs

from casexml.apps.case.const import DEFAULT_CASE_INDEX_IDENTIFIERS
from corehq import toggles, privileges
from corehq.apps.accounting.utils import domain_has_privilege
from corehq.apps.app_manager.exceptions import (
    ConflictingCaseTypeError,
    FormNotFoundException, XFormValidationFailed)
from corehq.apps.app_manager.templatetags.xforms_extras import trans
from corehq.apps.programs.models import Program
from corehq.apps.app_manager.util import (
    save_xform,
    is_usercase_in_use,
    enable_usercase,
    actions_use_usercase,
    advanced_actions_use_usercase,
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
from corehq.apps.app_manager.const import USERCASE_PREFIX, USERCASE_TYPE
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
    OpenCaseAction,
    IncompatibleFormTypeException,
    ModuleNotFoundException,
    UpdateCaseAction,
    load_case_reserved_words,
    WORKFLOW_FORM,
    CustomInstance,
    CaseReferences,
    AdvancedModule,
    ShadowForm,
)
from corehq.apps.app_manager.decorators import no_conflict_require_POST, \
    require_can_edit_apps, require_deploy_apps
from corehq.apps.data_dictionary.util import add_properties_to_data_dictionary, get_case_property_description_dict
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
    try:
        module_id = app.get_module_by_unique_id(module_unique_id).id
    except ModuleNotFoundException as e:
        messages.error(request, e.message)
        module_id = None

    return back_to_main(request, domain, app_id=app_id, module_id=module_id)


@no_conflict_require_POST
@require_can_edit_apps
def copy_form(request, domain, app_id, form_unique_id):
    app = get_app(domain, app_id)
    form = app.get_form(form_unique_id)
    module = form.get_module()
    to_module_id = int(request.POST['to_module_id'])
    new_form = None
    try:
        new_form = app.copy_form(module.id, form.id, to_module_id)
    except ConflictingCaseTypeError:
        messages.warning(request, CASE_TYPE_CONFLICT_MSG, extra_tags="html")
        app.save()
    except IncompatibleFormTypeException:
        # don't save!
        messages.error(request, _('This form could not be copied because it '
                                  'is not compatible with the selected module.'))
    else:
        app.save()

    if new_form:
        return back_to_main(request, domain, app_id=app_id, form_unique_id=new_form.unique_id)
    return back_to_main(request, domain, app_id=app_id, module_id=module.id,
                        form_id=form.id)


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
    app = get_app(domain, app_id)
    form = app.get_form(form_unique_id)
    json_loads = json.loads(request.POST.get('actions'))
    actions = AdvancedFormActions.wrap(json_loads)
    if form.form_type == "shadow_form":
        form.extra_actions = actions
    else:
        form.actions = actions
    for action in actions.load_update_cases:
        add_properties_to_data_dictionary(domain, action.case_type, action.case_properties.keys())
    if advanced_actions_use_usercase(actions) and not is_usercase_in_use(domain):
        enable_usercase(domain)
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
    add_properties_to_data_dictionary(domain, module.case_type, form.actions.update_case.update.keys())
    if old_load_from_form:
        form.actions.load_from_form = old_load_from_form

    for condition in (form.actions.open_case.condition, form.actions.close_case.condition):
        if isinstance(condition.answer, basestring):
            condition.answer = condition.answer.strip('"\'')
    form.requires = request.POST.get('requires', form.requires)
    if actions_use_usercase(form.actions):
        if not is_usercase_in_use(domain):
            enable_usercase(domain)
        add_properties_to_data_dictionary(domain, USERCASE_TYPE, form.actions.usercase_update.update.keys())

    response_json = {}
    app.save(response_json)
    response_json['propertiesMap'] = get_all_case_properties(app)
    response_json['usercasePropertiesMap'] = get_usercase_properties(app)
    return json_response(response_json)


@no_conflict_require_POST
@require_can_edit_apps
def edit_careplan_form_actions(request, domain, app_id, form_unique_id):
    app = get_app(domain, app_id)
    form = app.get_form(form_unique_id)
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
def edit_form_attr_api(request, domain, app_id, form_unique_id, attr):
    return _edit_form_attr(request, domain, app_id, form_unique_id, attr)


@login_or_digest
def edit_form_attr(request, domain, app_id, form_unique_id, attr):
    return _edit_form_attr(request, domain, app_id, form_unique_id, attr)


@no_conflict_require_POST
@require_permission(Permissions.edit_apps, login_decorator=None)
def _edit_form_attr(request, domain, app_id, form_unique_id, attr):
    """
    Called to edit any (supported) form attribute, given by attr

    """

    ajax = json.loads(request.POST.get('ajax', 'true'))
    resp = {}

    app = get_app(domain, app_id)
    try:
        form = app.get_form(form_unique_id)
    except FormNotFoundException as e:
        if ajax:
            return HttpResponseBadRequest(unicode(e))
        else:
            messages.error(request, _("There was an error saving, please try again!"))
            return back_to_main(request, domain, app_id=app_id)
    lang = request.COOKIES.get('lang', app.langs[0])

    def should_edit(attribute):
        return attribute in request.POST

    if should_edit("name"):
        name = request.POST['name']
        form.name[lang] = name
        if not form.form_type == "shadow_form":
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
                    xform = unicode(xform, encoding="utf-8")
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
                return HttpResponseBadRequest(unicode(e))
            else:
                messages.error(request, unicode(e))
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
        form_links = zip(
            request.POST.getlist('form_links_xpath_expressions'),
            request.POST.getlist('form_links_form_ids'),
            [
                json.loads(datum_json) if datum_json else []
                for datum_json in request.POST.getlist('datums_json')
            ],
        )
        form.form_links = [FormLink(
            xpath=link[0],
            form_id=link[1],
            datums=[
                FormDatum(name=datum['name'], xpath=datum['xpath'])
                for datum in link[2]
            ]
        ) for link in form_links]

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
    if should_edit("shadow_parent"):
        form.shadow_parent_form_id = request.POST['shadow_parent']

    handle_media_edits(request, form, should_edit, resp, lang)

    app.save(resp)
    notify_form_changed(domain, request.couch_user, app_id, form_unique_id)
    if ajax:
        return HttpResponse(json.dumps(resp))
    else:
        return back_to_main(request, domain, app_id=app_id, form_unique_id=form_unique_id)


@no_conflict_require_POST
@require_can_edit_apps
def new_form(request, domain, app_id, module_id):
    "Adds a form to an app (under a module)"
    app = get_app(domain, app_id)
    lang = request.COOKIES.get('lang', app.langs[0])
    form_type = request.POST.get('form_type', 'form')
    case_action = request.POST.get('case_action', 'none')
    name = _("Register") if case_action == 'open' else (_("Followup") if case_action == 'update' else "Survey")
    if form_type == "shadow":
        app = get_app(domain, app_id)
        module = app.get_module(module_id)
        if module.module_type == "advanced":
            form = module.new_shadow_form(name, lang)
        else:
            raise Exception("Shadow forms may only be created under shadow modules")
    else:
        form = app.new_form(module_id, name, lang)

    if toggles.APP_MANAGER_V2.enabled(request.user.username) and form_type != "shadow":
        if case_action == 'update':
            form.requires = 'case'
            form.actions.update_case = UpdateCaseAction(
                condition=FormActionCondition(type='always'))
        elif case_action == 'open':
            form.actions.open_case = OpenCaseAction(condition=FormActionCondition(type='always'))
            form.actions.update_case = UpdateCaseAction(condition=FormActionCondition(type='always'))

    app.save()
    # add form_id to locals()
    form_id = form.id
    response = back_to_main(request, domain, app_id=app_id, module_id=module_id,
                            form_id=form_id)
    return response


@no_conflict_require_POST
@login_or_digest
@require_permission(Permissions.edit_apps, login_decorator=None)
def patch_xform(request, domain, app_id, form_unique_id):
    patch = request.POST['patch']
    sha1_checksum = request.POST['sha1']
    case_references = _get_case_references(request.POST)

    app = get_app(domain, app_id)
    form = app.get_form(form_unique_id)

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
    notify_form_changed(domain, request.couch_user, app_id, form_unique_id)
    return json_response(response_json)


@require_GET
@require_can_edit_apps
def get_xform_source(request, domain, app_id, form_unique_id):
    app = get_app(domain, app_id)
    try:
        form = app.get_form(form_unique_id)
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
                messages.error(request, unicode(e))
            except Exception as e:
                if settings.DEBUG:
                    raise
                logging.exception(unicode(e))
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

    allow_usercase = domain_has_privilege(request.domain, privileges.USER_CASE)
    valid_index_names = DEFAULT_CASE_INDEX_IDENTIFIERS.values()
    if allow_usercase:
        valid_index_names.append(USERCASE_PREFIX[0:-1])     # strip trailing slash

    form_has_schedule = isinstance(form, AdvancedForm) and form.get_module().has_schedule
    case_config_options = {
        'caseType': form.get_case_type(),
        'moduleCaseTypes': module_case_types,
        'propertiesMap': get_all_case_properties(app),
        'propertyDescriptions': get_case_property_description_dict(domain),
        'questions': xform_questions,
        'reserved_words': load_case_reserved_words(),
        'usercasePropertiesMap': get_usercase_properties(app),
    }
    context = {
        'nav_form': form,
        'xform_languages': languages,
        'form_errors': form_errors,
        'xform_validation_errored': xform_validation_errored,
        'xform_validation_missing': xform_validation_missing,
        'allow_cloudcare': isinstance(form, Form),
        'allow_form_copy': isinstance(form, (Form, AdvancedForm)),
        'allow_form_filtering': not isinstance(form, CareplanForm) and not form_has_schedule,
        'allow_form_workflow': not isinstance(form, CareplanForm),
        'uses_form_workflow': form.post_form_workflow == WORKFLOW_FORM,
        'allow_usercase': allow_usercase,
        'is_usercase_in_use': is_usercase_in_use(request.domain),
        'is_module_filter_enabled': app.enable_module_filtering,
        'is_case_list_form': form.is_case_list_form,
        'edit_name_url': reverse('edit_form_attr', args=[app.domain, app.id, form.unique_id, 'name']),
        'form_filter_patterns': {
            'case': CASE_XPATH_PATTERN_MATCHES,
            'case_substring': CASE_XPATH_SUBSTRING_MATCHES,
            'usercase': USER_CASE_XPATH_PATTERN_MATCHES,
            'usercase_substring': USER_CASE_XPATH_SUBSTRING_MATCHES,
        },
        'custom_instances': [
            {'instanceId': instance.instance_id, 'instancePath': instance.instance_path}
            for instance in form.custom_instances
        ],
        'can_preview_form': request.couch_user.has_permission(domain, 'edit_data')
    }

    if tours.NEW_APP.is_enabled(request.user) and not toggles.APP_MANAGER_V2.enabled(request.user.username):
        request.guided_tour = tours.NEW_APP.get_tour_data()

    if context['allow_form_workflow'] and toggles.FORM_LINK_WORKFLOW.enabled(domain):
        module = form.get_module()

        def qualified_form_name(form, auto_link):
            module_name = trans(form.get_module().name, langs)
            form_name = trans(form.name, langs)
            star = '* ' if auto_link else '  '
            return u"{}{} -> {}".format(star, module_name, form_name)

        modules = filter(lambda m: m.case_type == module.case_type, all_modules)
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
        case_config_options.update({
            'case_preload': [
                {'key': key, 'path': path} for key, path in form.case_preload.items()
            ],
            'customCaseUpdates': [
                {'key': key, 'path': path} for key, path in form.custom_case_updates.items()
            ],
            'fixedQuestions': form.get_fixed_questions(),
            'mode': form.mode,
            'save_url': reverse("edit_careplan_form_actions", args=[app.domain, app.id, form.unique_id]),
        })
    elif isinstance(form, AdvancedForm):
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
    template = get_app_manager_template(
        request.user,
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
            request.user,
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
