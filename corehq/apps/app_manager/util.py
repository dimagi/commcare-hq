from collections import namedtuple, OrderedDict
from copy import deepcopy, copy
from couchdbkit import ResourceNotFound
import json
import os
import uuid
import re
import logging

import yaml
from django.urls import reverse
from couchdbkit.exceptions import DocTypeError
from django.core.cache import cache
from django.utils.translation import ugettext as _

from corehq import toggles
from corehq.apps.app_manager.dbaccessors import (
    get_apps_in_domain
)
from corehq.apps.app_manager.exceptions import SuiteError, SuiteValidationError, PracticeUserException
from corehq.apps.app_manager.xpath import DOT_INTERPOLATE_PATTERN, UserCaseXPath
from corehq.apps.builds.models import CommCareBuildConfig
from corehq.apps.app_manager.tasks import create_user_cases
from corehq.util.soft_assert import soft_assert
from corehq.apps.domain.models import Domain
from corehq.apps.app_manager.const import (
    AUTO_SELECT_USERCASE,
    USERCASE_TYPE,
    USERCASE_ID,
    USERCASE_PREFIX)
from corehq.apps.app_manager.xform import XForm, XFormException, parse_xml
from corehq.apps.users.models import CommCareUser
from dimagi.utils.couch import CriticalSection
from dimagi.utils.make_uuid import random_hex


logger = logging.getLogger(__name__)

CASE_XPATH_PATTERN_MATCHES = [
    DOT_INTERPOLATE_PATTERN
]

CASE_XPATH_SUBSTRING_MATCHES = [
    "instance('casedb')",
    'session/data/case_id',
    "#case",
    "#parent",
    "#host",
]


USER_CASE_XPATH_PATTERN_MATCHES = []

USER_CASE_XPATH_SUBSTRING_MATCHES = [
    "#user",
    UserCaseXPath().case(),
]


def app_doc_types():
    from corehq.apps.app_manager.models import Application, RemoteApp, LinkedApplication
    return {
        'Application': Application,
        'Application-Deleted': Application,
        'RemoteApp': RemoteApp,
        'RemoteApp-Deleted': RemoteApp,
        'LinkedApplication': LinkedApplication,
        'LinkedApplication-Deleted': LinkedApplication
    }


def _prepare_xpath_for_validation(xpath):
    prepared_xpath = xpath.lower()
    prepared_xpath = prepared_xpath.replace('"', "'")
    prepared_xpath = re.compile('\s').sub('', prepared_xpath)
    return prepared_xpath


def _check_xpath_for_matches(xpath, substring_matches=None, pattern_matches=None):
    prepared_xpath = _prepare_xpath_for_validation(xpath)

    substring_matches = substring_matches or []
    pattern_matches = pattern_matches or []

    return any([
        re.compile(pattern).search(prepared_xpath) for pattern in pattern_matches
    ] + [
        substring in prepared_xpath for substring in substring_matches
    ])


def xpath_references_case(xpath):
    # We want to determine here if the xpath references any cases other
    # than the user case. To determine if the xpath references the user
    # case, see xpath_references_user_case()
    for substring in USER_CASE_XPATH_SUBSTRING_MATCHES:
        xpath = xpath.replace(substring, '')

    return _check_xpath_for_matches(
        xpath,
        substring_matches=CASE_XPATH_SUBSTRING_MATCHES,
        pattern_matches=CASE_XPATH_PATTERN_MATCHES
    )


def xpath_references_user_case(xpath):
    return _check_xpath_for_matches(
        xpath,
        substring_matches=USER_CASE_XPATH_SUBSTRING_MATCHES,
        pattern_matches=USER_CASE_XPATH_PATTERN_MATCHES,
    )


def split_path(path):
    path_parts = path.split('/')
    name = path_parts.pop(-1)
    path = '/'.join(path_parts)
    return path, name


def save_xform(app, form, xml):
    def change_xmlns(xform, replacing):
        data = xform.data_node.render()
        xmlns = "http://openrosa.org/formdesigner/%s" % form.get_unique_id()
        data = data.replace(replacing, xmlns, 1)
        xform.instance_node.remove(xform.data_node.xml)
        xform.instance_node.append(parse_xml(data))
        xml = xform.render()
        return xform, xml

    try:
        xform = XForm(xml)
    except XFormException:
        pass
    else:
        duplicates = app.get_xmlns_map()[xform.data_node.tag_xmlns]
        for duplicate in duplicates:
            if form == duplicate:
                continue
            else:
                xform, xml = change_xmlns(xform, xform.data_node.tag_xmlns)
                break

        GENERIC_XMLNS = "http://www.w3.org/2002/xforms"
        if not xform.data_node.tag_xmlns or xform.data_node.tag_xmlns == GENERIC_XMLNS:  #no xmlns
            xform, xml = change_xmlns(xform, GENERIC_XMLNS)

    form.source = xml

    # For registration forms, assume that the first question is the case name
    # unless something else has been specified
    if form.is_registration_form():
        questions = form.get_questions([app.default_language])
        if hasattr(form.actions, 'open_case'):
            path = form.actions.open_case.name_path
            if path:
                name_questions = [q for q in questions if q['value'] == path]
                if not len(name_questions):
                    path = None
            if not path and len(questions):
                form.actions.open_case.name_path = questions[0]['value']

CASE_TYPE_REGEX = r'^[\w-]+$'
_case_type_regex = re.compile(CASE_TYPE_REGEX)


def is_valid_case_type(case_type, module):
    """
    >>> from corehq.apps.app_manager.models import Module, AdvancedModule
    >>> is_valid_case_type('foo', Module())
    True
    >>> is_valid_case_type('foo-bar', Module())
    True
    >>> is_valid_case_type('foo bar', Module())
    False
    >>> is_valid_case_type('', Module())
    False
    >>> is_valid_case_type(None, Module())
    False
    >>> is_valid_case_type('commcare-user', Module())
    False
    >>> is_valid_case_type('commcare-user', AdvancedModule())
    True
    """
    from corehq.apps.app_manager.models import AdvancedModule
    matches_regex = bool(_case_type_regex.match(case_type or ''))
    prevent_usercase_type = (case_type != USERCASE_TYPE or isinstance(module, AdvancedModule))
    return matches_regex and prevent_usercase_type


def module_case_hierarchy_has_circular_reference(module):
    from corehq.apps.app_manager.suite_xml.utils import get_select_chain
    try:
        get_select_chain(module.get_app(), module)
        return False
    except SuiteValidationError:
        return True


def is_usercase_in_use(domain_name):
    domain = Domain.get_by_name(domain_name) if domain_name else None
    return domain and domain.usercase_enabled


def get_settings_values(app):
    try:
        profile = app.profile
    except AttributeError:
        profile = {}
    hq_settings = dict([
        (attr, app[attr])
        for attr in app.properties() if not hasattr(app[attr], 'pop')
    ])
    if getattr(app, 'use_custom_suite', False):
        hq_settings.update({'custom_suite': getattr(app, 'custom_suite', None)})

    hq_settings['build_spec'] = app.build_spec.to_string()
    # the admin_password hash shouldn't be sent to the client
    hq_settings.pop('admin_password', None)
    # convert int to string
    hq_settings['mobile_ucr_sync_interval'] = str(hq_settings.get('mobile_ucr_sync_interval', 'none'))

    domain = Domain.get_by_name(app.domain)
    return {
        'properties': profile.get('properties', {}),
        'features': profile.get('features', {}),
        'hq': hq_settings,
        '$parent': {
            'doc_type': app.get_doc_type(),
            '_id': app.get_id,
            'domain': app.domain,
            'commtrack_enabled': domain.commtrack_enabled,
        }
    }


def add_odk_profile_after_build(app_build):
    """caller must save"""

    profile = app_build.create_profile(is_odk=True)
    app_build.lazy_put_attachment(profile, 'files/profile.ccpr')
    # hack this in for records
    app_build.odk_profile_created_after_build = True


def create_temp_sort_column(sort_element, order):
    """
    Used to create a column for the sort only properties to
    add the field to the list of properties and app strings but
    not persist anything to the detail data.
    """
    from corehq.apps.app_manager.models import DetailColumn
    col = DetailColumn(
        model='case',
        field=sort_element.field,
        format='invisible',
        header=sort_element.display,
    )
    col._i = order
    return col


def get_correct_app_class(doc):
    try:
        return app_doc_types()[doc['doc_type']]
    except KeyError:
        raise DocTypeError(doc['doc_type'])


def all_apps_by_domain(domain):
    from corehq.apps.app_manager.models import ApplicationBase
    rows = ApplicationBase.get_db().view(
        'app_manager/applications',
        startkey=[domain, None],
        endkey=[domain, None, {}],
        include_docs=True,
    ).all()
    for row in rows:
        doc = row['doc']
        yield get_correct_app_class(doc).wrap(doc)


def new_careplan_module(app, name, lang, target_module):
    from corehq.apps.app_manager.models import CareplanModule, CareplanGoalForm, CareplanTaskForm
    module = app.add_module(CareplanModule.new_module(
        name,
        lang,
        target_module.unique_id,
        target_module.case_type
    ))

    forms = [form_class.new_form(lang, name, mode)
                for form_class in [CareplanGoalForm, CareplanTaskForm]
                for mode in ['create', 'update']]

    for form, source in forms:
        module.forms.append(form)
        form = module.get_form(-1)
        form.source = source

    return module


def languages_mapping():
    mapping = cache.get('__languages_mapping')
    if not mapping:
        with open('submodules/langcodes/langs.json') as langs_file:
            lang_data = json.load(langs_file)
            mapping = dict([(l["two"], l["names"]) for l in lang_data])
        mapping["default"] = ["Default Language"]
        cache.set('__languages_mapping', mapping, 12*60*60)
    return mapping


def version_key(ver):
    """
    A key function that takes a version and returns a numeric value that can
    be used for sorting

    >>> version_key('2')
    2000000
    >>> version_key('2.9')
    2009000
    >>> version_key('2.10')
    2010000
    >>> version_key('2.9.1')
    2009001
    >>> version_key('2.9.1.1')
    2009001
    >>> version_key('2.9B')
    Traceback (most recent call last):
      ...
    ValueError: invalid literal for int() with base 10: '9B'

    """
    padded = ver + '.0.0'
    values = padded.split('.')
    return int(values[0]) * 1000000 + int(values[1]) * 1000 + int(values[2])


def get_commcare_versions(request_user):
    versions = [i.build.version for i in CommCareBuildConfig.fetch().menu
                if request_user.is_superuser or not i.superuser_only]
    return sorted(versions, key=version_key)


def actions_use_usercase(actions):
    return (('usercase_update' in actions and actions['usercase_update'].update) or
            ('usercase_preload' in actions and actions['usercase_preload'].preload))


def advanced_actions_use_usercase(actions):
    return any(c.auto_select and c.auto_select.mode == AUTO_SELECT_USERCASE for c in actions.load_update_cases)


def enable_usercase(domain_name):
    with CriticalSection(['enable_usercase_' + domain_name]):
        domain = Domain.get_by_name(domain_name, strict=True)
        if not domain:  # copying domains passes in an id before name is saved
            domain = Domain.get(domain_name)
        if not domain.usercase_enabled:
            domain.usercase_enabled = True
            domain.save()
            create_user_cases.delay(domain_name)





def prefix_usercase_properties(properties):
    return {'{}{}'.format(USERCASE_PREFIX, prop) for prop in properties}


def module_offers_search(module):
    from corehq.apps.app_manager.models import AdvancedModule, Module, ShadowModule

    return (
        isinstance(module, (Module, AdvancedModule, ShadowModule)) and
        module.search_config and
        (module.search_config.properties or
         module.search_config.default_properties)
    )


def get_cloudcare_session_data(domain_name, form, couch_user):
    from corehq.apps.app_manager.suite_xml.sections.entries import EntriesHelper

    datums = EntriesHelper.get_new_case_id_datums_meta(form)
    session_data = {datum.datum.id: uuid.uuid4().hex for datum in datums}
    if couch_user.doc_type == 'CommCareUser':  # smsforms.app.start_session could pass a CommCareCase
        try:
            extra_datums = EntriesHelper.get_extra_case_id_datums(form)
        except SuiteError as err:
            _assert = soft_assert(['nhooper_at_dimagi_dot_com'.replace('_at_', '@').replace('_dot_', '.')])
            _assert(False, 'Domain "%s": %s' % (domain_name, err))
        else:
            if EntriesHelper.any_usercase_datums(extra_datums):
                usercase_id = couch_user.get_usercase_id()
                if usercase_id:
                    session_data[USERCASE_ID] = usercase_id
    return session_data


def update_unique_ids(app_source):
    from corehq.apps.app_manager.models import form_id_references, jsonpath_update

    app_source = deepcopy(app_source)

    def change_form_unique_id(form):
        unique_id = form['unique_id']
        new_unique_id = random_hex()
        form['unique_id'] = new_unique_id
        if ("%s.xml" % unique_id) in app_source['_attachments']:
            app_source['_attachments']["%s.xml" % new_unique_id] = app_source['_attachments'].pop("%s.xml" % unique_id)
        return new_unique_id

    # once Application.wrap includes deleting user_registration
    # we can remove this
    if 'user_registration' in app_source:
        del app_source['user_registration']

    id_changes = {}
    for m, module in enumerate(app_source['modules']):
        for f, form in enumerate(module['forms']):
            old_id = form['unique_id']
            new_id = change_form_unique_id(app_source['modules'][m]['forms'][f])
            id_changes[old_id] = new_id

    for reference_path in form_id_references:
        for reference in reference_path.find(app_source):
            if reference.value in id_changes:
                jsonpath_update(reference, id_changes[reference.value])

    return app_source


def _app_callout_templates():
    """Load app callout templates from config file on disk

    Generator function defers file access until needed, acts like a
    constant thereafter.
    """
    path = os.path.join(
        os.path.dirname(__file__),
        'static', 'app_manager', 'json', 'vellum-app-callout-templates.yaml'
    )
    if os.path.exists(path):
        with open(path) as f:
            data = yaml.load(f)
    else:
        logger.info("not found: %s", path)
        data = []
    while True:
        yield data
app_callout_templates = _app_callout_templates()


def purge_report_from_mobile_ucr(report_config):
    """
    Called when a report is deleted, this will remove any references to it in
    mobile UCR modules.
    """
    if not toggles.MOBILE_UCR.enabled(report_config.domain):
        return False

    did_purge_something = False
    for app in get_apps_in_domain(report_config.domain):
        save_app = False
        for module in app.modules:
            if module.module_type == 'report':
                valid_report_configs = [
                    app_config for app_config in module.report_configs
                    if app_config.report_id != report_config._id
                ]
                if len(valid_report_configs) != len(module.report_configs):
                    module.report_configs = valid_report_configs
                    save_app = True
        if save_app:
            app.save()
            did_purge_something = True
    return did_purge_something


SortOnlyElement = namedtuple("SortOnlyElement", "field, sort_element, order")


def get_sort_and_sort_only_columns(detail, sort_elements):
    """
    extracts out info about columns that are added as only sort fields and columns added as both
    sort and display fields
    """
    sort_elements = OrderedDict((s.field, (s, i + 1)) for i, s in enumerate(sort_elements))
    sort_columns = {}
    for column in detail.get_columns():
        sort_element, order = sort_elements.pop(column.field, (None, None))
        if sort_element:
            sort_columns[column.field] = (sort_element, order)

    sort_only_elements = [
        SortOnlyElement(field, element, element_order)
        for field, (element, element_order) in sort_elements.items()
    ]
    return sort_only_elements, sort_columns


def get_app_manager_template(user, v1, v2):
    """
    Given the user, a template string v1, and a template string v2,
    return the template for V2 if the APP_MANAGER_V2 toggle is enabled.

    :param user: WebUser
    :param v1: String, template name for V1
    :param v2: String, template name for V2
    :return: String, either v1 or v2 depending on toggle
    """
    if user is not None and toggles.APP_MANAGER_V1.enabled(user.username):
        return v1
    return v2


def get_form_data(domain, app, include_shadow_forms=True):
    from corehq.apps.reports.formdetails.readable import FormQuestionResponse
    from corehq.apps.app_manager.models import ShadowForm

    modules = []
    errors = []
    for module in app.get_modules():
        forms = []
        module_meta = {
            'id': module.unique_id,
            'name': module.name,
            'short_comment': module.short_comment,
            'module_type': module.module_type,
            'is_surveys': module.is_surveys,
        }

        form_list = module.get_forms()
        if not include_shadow_forms:
            form_list = [f for f in form_list if not isinstance(f, ShadowForm)]
        for form in form_list:
            form_meta = {
                'id': form.unique_id,
                'name': form.name,
                'short_comment': form.short_comment,
                'action_type': form.get_action_type(),
            }
            try:
                questions = form.get_questions(
                    app.langs,
                    include_triggers=True,
                    include_groups=True,
                    include_translations=True
                )
                form_meta['questions'] = [FormQuestionResponse(q).to_json() for q in questions]
            except XFormException as e:
                form_meta['error'] = {
                    'details': unicode(e),
                    'edit_url': reverse('form_source', args=[domain, app._id, module.id, form.id])
                }
                form_meta['module'] = copy(module_meta)
                errors.append(form_meta)
            else:
                forms.append(form_meta)

        module_meta['forms'] = forms
        modules.append(module_meta)
    return modules, errors


def get_and_assert_practice_user_in_domain(practice_user_id, domain):
    # raises PracticeUserException if CommCareUser with practice_user_id is not a practice mode user
    #   or if user doesn't belong to domain
    try:
        user = CommCareUser.get(practice_user_id)
        if not user.domain == domain:
            raise ResourceNotFound
    except ResourceNotFound:
        raise PracticeUserException(
            _("Practice User with id {id} not found, please make sure you have not deleted this user").format(
                id=practice_user_id)
        )
    if not user.is_demo_user:
        raise PracticeUserException(
            _("User {username} is not a practice user, please turn on practice mode for this user").format(
                username=user.username)
        )
    if user.is_deleted():
        raise PracticeUserException(
            _("User {username} has been deleted, you can't use that user as practice user").format(
                username=user.username)
        )
    if not user.is_active:
        raise PracticeUserException(
            _("User {username} has been deactivated, you can't use that user as practice user").format(
                username=user.username)
        )
    return user
