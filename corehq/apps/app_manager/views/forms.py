import logging
import hashlib
import re
import json
from xml.dom.minidom import parseString
from couchdbkit import ResourceNotFound
from django.shortcuts import render
import itertools

from lxml import etree
from diff_match_patch import diff_match_patch
from django.utils.translation import ugettext as _
from django.http import HttpResponse, Http404, HttpResponseBadRequest
from django.core.urlresolvers import reverse
from django.views.decorators.http import require_GET
from django.conf import settings
from django.contrib import messages
from unidecode import unidecode
from corehq.apps.app_manager.views.media_utils import handle_media_edits
from corehq.apps.app_manager.views.schedules import get_schedule_context

from corehq.apps.app_manager.views.utils import back_to_main, \
    CASE_TYPE_CONFLICT_MSG

from corehq import toggles, privileges
from corehq.apps.accounting.utils import domain_has_privilege
from corehq.apps.app_manager.exceptions import (
    BlankXFormError,
    ConflictingCaseTypeError,
)
from corehq.apps.app_manager.templatetags.xforms_extras import trans
from corehq.apps.programs.models import Program
from corehq.apps.app_manager.const import (
    APP_V2,
)
from corehq.apps.app_manager.util import (
    get_all_case_properties,
    save_xform,
    is_usercase_in_use,
    enable_usercase,
    actions_use_usercase,
    advanced_actions_use_usercase,
    get_usercase_properties,
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
    login_or_digest,
)
from corehq.apps.app_manager.dbaccessors import get_app
from corehq.apps.app_manager.models import (
    AdvancedForm,
    AdvancedFormActions,
    AppEditingError,
    CareplanForm,
    DeleteFormRecord,
    Form,
    FormActions,
    FormLink,
    IncompatibleFormTypeException,
    ModuleNotFoundException,
    load_case_reserved_words,
    FormDatum)
from corehq.apps.app_manager.decorators import no_conflict_require_POST, \
    require_can_edit_apps, require_deploy_apps


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
        messages.warning(request, CASE_TYPE_CONFLICT_MSG,  extra_tags="html")
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
        messages.error(request,
                       'Form could not be restored: module is missing.')

    return back_to_main(request, domain, app_id=record.app_id,
                        module_id=record.module_id, form_id=record.form_id)


@no_conflict_require_POST
@require_can_edit_apps
def edit_advanced_form_actions(request, domain, app_id, module_id, form_id):
    app = get_app(domain, app_id)
    form = app.get_module(module_id).get_form(form_id)
    json_loads = json.loads(request.POST.get('actions'))
    actions = AdvancedFormActions.wrap(json_loads)
    form.actions = actions
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
    form = app.get_module(module_id).get_form(form_id)
    form.actions = FormActions.wrap(json.loads(request.POST['actions']))
    for condition in (form.actions.open_case.condition, form.actions.close_case.condition):
        if isinstance(condition.answer, basestring):
            condition.answer = condition.answer.strip('"\'')
    form.requires = request.POST.get('requires', form.requires)
    if actions_use_usercase(form.actions) and not is_usercase_in_use(domain):
        enable_usercase(domain)
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


@no_conflict_require_POST
@login_or_digest
@require_permission(Permissions.edit_apps, login_decorator=None)
def edit_form_attr(request, domain, app_id, unique_form_id, attr):
    """
    Called to edit any (supported) form attribute, given by attr

    """

    app = get_app(domain, app_id)
    form = app.get_form(unique_form_id)
    lang = request.COOKIES.get('lang', app.langs[0])
    ajax = json.loads(request.POST.get('ajax', 'true'))

    resp = {}

    def should_edit(attribute):
        if request.POST.has_key(attribute):
            return True
        elif request.FILES.has_key(attribute):
            return True
        else:
            return False

    if should_edit("user_reg_data"):
        # should be user_registrations only
        data = json.loads(request.POST['user_reg_data'])
        data_paths = data['data_paths']
        data_paths_dict = {}
        for path in data_paths:
            data_paths_dict[path.split('/')[-1]] = path
        form.data_paths = data_paths_dict

    if should_edit("name"):
        name = request.POST['name']
        form.name[lang] = name
        xform = form.wrapped_xform()
        if xform.exists():
            xform.set_name(name)
            save_xform(app, form, xform.render())
        resp['update'] = {'.variable-form_name': form.name[lang]}
    if should_edit("xform"):
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
        except Exception, e:
            if ajax:
                return HttpResponseBadRequest(unicode(e))
            else:
                messages.error(request, unicode(e))
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

    handle_media_edits(request, form, should_edit, resp, lang)

    app.save(resp)
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

    app = get_app(domain, app_id)
    form = app.get_form(unique_form_id)

    current_xml = form.source
    if hashlib.sha1(current_xml.encode('utf-8')).hexdigest() != sha1_checksum:
        return json_response({'status': 'conflict', 'xform': current_xml})

    dmp = diff_match_patch()
    xform, _ = dmp.patch_apply(dmp.patch_fromText(patch), current_xml)
    save_xform(app, form, xform)
    response_json = {
        'status': 'ok',
        'sha1': hashlib.sha1(form.source.encode('utf-8')).hexdigest()
    }
    app.save(response_json)
    return json_response(response_json)


@require_can_edit_apps
def get_xform_source(request, domain, app_id, module_id, form_id):
    app = get_app(domain, app_id)
    try:
        form = app.get_module(module_id).get_form(form_id)
    except IndexError:
        raise Http404()
    return _get_xform_source(request, app, form)


@require_can_edit_apps
def view_user_registration(request, domain, app_id):
    from corehq.apps.app_manager.views.view_generic import view_generic
    return view_generic(request, domain, app_id, is_user_registration=True)


def get_form_view_context_and_template(request, domain, form, langs, is_user_registration, messages=messages):
    xform_questions = []
    xform = None
    form_errors = []
    xform_validation_errored = False

    try:
        xform = form.wrapped_xform()
    except XFormException as e:
        form_errors.append(u"Error in form: %s" % e)
    except Exception as e:
        logging.exception(e)
        form_errors.append(u"Unexpected error in form: %s" % e)

    if xform and xform.exists():
        if xform.already_has_meta():
            messages.warning(request,
                "This form has a meta block already! "
                "It may be replaced by CommCare HQ's standard meta block."
            )

        try:
            form.validate_form()
            xform_questions = xform.get_questions(langs, include_triggers=True)
        except etree.XMLSyntaxError as e:
            form_errors.append(u"Syntax Error: %s" % e)
        except AppEditingError as e:
            form_errors.append(u"Error in application: %s" % e)
        except XFormValidationError:
            xform_validation_errored = True
            # showing these messages is handled by validate_form_for_build ajax
            pass
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
    if is_user_registration:
        module_case_types = None
    else:
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
        'is_user_registration': is_user_registration,
        'nav_form': form if not is_user_registration else '',
        'xform_languages': languages,
        "xform_questions": xform_questions,
        'case_reserved_words_json': load_case_reserved_words(),
        'module_case_types': module_case_types,
        'form_errors': form_errors,
        'xform_validation_errored': xform_validation_errored,
        'allow_cloudcare': app.application_version == APP_V2 and isinstance(form, Form),
        'allow_form_copy': isinstance(form, Form),
        'allow_form_filtering': not isinstance(form, CareplanForm) and not form_has_schedule,
        'allow_form_workflow': is_user_registration and not isinstance(form, CareplanForm),
        'allow_usercase': domain_has_privilege(request.domain, privileges.USER_CASE),
        'is_usercase_in_use': is_usercase_in_use(request.domain),
    }
    
    if context['allow_form_workflow'] and toggles.FORM_LINK_WORKFLOW.enabled(domain):
        module = form.get_module()

        def qualified_form_name(form, auto_link):
            module_name = trans(form.get_module().name, langs)
            form_name = trans(form.name, app.langs)
            star = '* ' if auto_link else '  '
            return u"{}{} -> {}".format(star, module_name, form_name)

        modules = filter(lambda m: m.case_type == module.case_type, all_modules)
        if getattr(module, 'root_module_id', None) and module.root_module not in modules:
            modules.append(module.root_module)
        modules.extend([mod for mod in module.get_child_modules() if mod not in modules])
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
            'custom_case_properties': [{'key': key, 'path': path} for key, path in form.custom_case_updates.items()],
            'case_preload': [{'key': key, 'path': path} for key, path in form.case_preload.items()],
        })
        return "app_manager/form_view_careplan.html", context
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
        return "app_manager/form_view_advanced.html", context
    else:
        context.update({
            'show_custom_ref': toggles.APP_BUILDER_CUSTOM_PARENT_REF.enabled(request.user.username),
        })
        return "app_manager/form_view.html", context


@require_can_edit_apps
def get_form_datums(request, domain, app_id):
    from corehq.apps.app_manager.suite_xml import SuiteGenerator
    form_id = request.GET.get('form_id')
    app = get_app(domain, app_id)
    form = app.get_form(form_id)

    def make_datum(datum):
        return {'name': datum.datum.id, 'case_type': datum.case_type}

    gen = SuiteGenerator(app)
    datums = []
    root_module = form.get_module().root_module
    if root_module:
        datums.extend([
            make_datum(datum) for datum in gen.get_datums_meta_for_form_generic(root_module.get_form(0))
            if datum.requires_selection
        ])
    datums.extend([
        make_datum(datum) for datum in gen.get_datums_meta_for_form_generic(form)
        if datum.requires_selection
    ])
    return json_response(datums)


@require_GET
@require_deploy_apps
def view_form(request, domain, app_id, module_id, form_id):
    from corehq.apps.app_manager.views.view_generic import view_generic
    return view_generic(request, domain, app_id, module_id, form_id)


@require_can_edit_apps
def get_user_registration_source(request, domain, app_id):
    app = get_app(domain, app_id)
    form = app.get_user_registration()
    return _get_xform_source(request, app, form, filename="User Registration.xml")


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

        return render(request, 'app_manager/xform_display.html', {
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
