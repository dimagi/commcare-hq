import json
import logging
import os
import re
import uuid
from collections import OrderedDict, namedtuple
from copy import deepcopy

from django.core.cache import cache
from django.db.models import Max
from django.http import Http404
from django.urls import reverse
from django.utils.translation import gettext as _

import yaml
from couchdbkit import ResourceNotFound
from couchdbkit.exceptions import DocTypeError

from dimagi.utils.couch import CriticalSection

from corehq import toggles
from corehq.apps.app_manager.const import (
    AUTO_SELECT_USERCASE,
    CALCULATED_SORT_FIELD_RX,
    REGISTRY_WORKFLOW_LOAD_CASE,
    REGISTRY_WORKFLOW_SMART_LINK,
    USERCASE_ID,
    USERCASE_PREFIX,
    USERCASE_TYPE,
)
from corehq.apps.app_manager.dbaccessors import get_app, get_apps_in_domain
from corehq.apps.app_manager.exceptions import (
    AppManagerException,
    PracticeUserException,
    SuiteError,
    SuiteValidationError,
    XFormException,
)
from corehq.apps.app_manager.tasks import create_usercases
from corehq.apps.app_manager.xform import XForm, parse_xml
from corehq.apps.app_manager.xpath import UsercaseXPath
from corehq.apps.builds.models import CommCareBuildConfig
from corehq.apps.domain.models import Domain
from corehq.apps.locations.models import SQLLocation
from corehq.apps.users.models import CommCareUser
from corehq.util.quickcache import quickcache
from corehq.util.soft_assert import soft_assert

logger = logging.getLogger(__name__)

CASE_XPATH_SUBSTRING_MATCHES = [
    "instance('casedb')",
    'session/data/case_id',
    "#case",
    "#parent",
    "#host",
]

USERCASE_XPATH_SUBSTRING_MATCHES = [
    "#user",
    UsercaseXPath().case(),
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


def is_linked_app(app_or_doc, include_deleted=False):
    return _get_doc_type(app_or_doc) in ('LinkedApplication', 'LinkedApplication-Deleted')


def is_remote_app(app_or_doc, include_deleted=False):
    return _get_doc_type(app_or_doc) in ('RemoteApp', 'RemoteApp-Deleted')


def _get_doc_type(app_or_doc):
    if hasattr(app_or_doc, 'doc_type'):
        doc_type = app_or_doc.doc_type
    elif 'doc_type' in app_or_doc:
        doc_type = app_or_doc['doc_type']
    assert doc_type
    return doc_type


def _prepare_xpath_for_validation(xpath):
    prepared_xpath = xpath.lower()
    prepared_xpath = prepared_xpath.replace('"', "'")
    prepared_xpath = re.compile(r'\s').sub('', prepared_xpath)
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
    # case, see xpath_references_usercase()
    # Assumes xpath has already been dot interpolated as needed.
    for substring in USERCASE_XPATH_SUBSTRING_MATCHES:
        xpath = xpath.replace(substring, '')

    return _check_xpath_for_matches(
        xpath,
        substring_matches=CASE_XPATH_SUBSTRING_MATCHES,
    )


def xpath_references_usercase(xpath):
    # Assumes xpath has already been dot interpolated as needed.
    return _check_xpath_for_matches(
        xpath,
        substring_matches=USERCASE_XPATH_SUBSTRING_MATCHES,
    )


def split_path(path):
    path_parts = path.split('/')
    name = path_parts.pop(-1)
    path = '/'.join(path_parts)
    return path, name


def first_elem(elem_list):
    return elem_list[0] if elem_list else None


def generate_xmlns():
    return str(uuid.uuid4()).upper()


def save_xform(app, form, xml):

    def change_xmlns(xform, old_xmlns, new_xmlns):
        data = xform.data_node.render().decode('utf-8')
        data = data.replace(old_xmlns, new_xmlns, 1)
        xform.instance_node.remove(xform.data_node.xml)
        xform.instance_node.append(parse_xml(data))
        return xform.render()

    try:
        xform = XForm(xml, domain=app.domain)
    except XFormException:
        pass
    else:
        GENERIC_XMLNS = "http://www.w3.org/2002/xforms"
        uid = generate_xmlns()
        tag_xmlns = xform.data_node.tag_xmlns
        new_xmlns = form.xmlns or "http://openrosa.org/formdesigner/%s" % uid
        if not tag_xmlns or tag_xmlns == GENERIC_XMLNS:  # no xmlns
            xml = change_xmlns(xform, GENERIC_XMLNS, new_xmlns)
        else:
            forms = [form_
                for form_ in app.get_xmlns_map().get(tag_xmlns, [])
                if form_.form_type != 'shadow_form']
            if len(forms) > 1 or (len(forms) == 1 and forms[0] is not form):
                if new_xmlns == tag_xmlns:
                    new_xmlns = "http://openrosa.org/formdesigner/%s" % uid
                # form most likely created by app.copy_form(...)
                # or form is being updated with source copied from other form
                xml = change_xmlns(xform, tag_xmlns, new_xmlns)

    form.source = xml.decode('utf-8')

    from corehq.apps.app_manager.models import ConditionalCaseUpdate
    if form.is_registration_form():
        # For registration forms, assume that the first question is the
        # case name unless something else has been specified
        questions = form.get_questions([app.default_language])
        if hasattr(form.actions, 'open_case'):
            path = getattr(form.actions.open_case.name_update, 'question_path', None)
            if path:
                name_questions = [q for q in questions if q['value'] == path]
                if not len(name_questions):
                    path = None
            if not path and len(questions):
                form.actions.open_case.name_update = ConditionalCaseUpdate(question_path=questions[0]['value'])

    return xml


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
    domain_obj = Domain.get_by_name(domain_name) if domain_name else None
    return domain_obj and domain_obj.usercase_enabled


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
    hq_settings['mobile_ucr_restore_version'] = str(hq_settings.get('mobile_ucr_restore_version', '1.0'))

    domain_obj = Domain.get_by_name(app.domain)
    return {
        'properties': profile.get('properties', {}),
        'features': profile.get('features', {}),
        'hq': hq_settings,
        '$parent': {
            'doc_type': app.get_doc_type(),
            '_id': app.get_id,
            'domain': app.domain,
            'commtrack_enabled': domain_obj.commtrack_enabled,
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


def languages_mapping():
    mapping = cache.get('__languages_mapping')
    if not mapping:
        with open('submodules/langcodes/langs.json', encoding='utf-8') as langs_file:
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
    versions = [i.version for i in get_commcare_builds(request_user)]
    return sorted(versions, key=version_key)


def get_commcare_builds(request_user):
    can_view_superuser_builds = (request_user.is_superuser
                                 or toggles.IS_CONTRACTOR.enabled(request_user.username))
    return [
        i.build
        for i in CommCareBuildConfig.fetch().menu
        if can_view_superuser_builds or not i.superuser_only
    ]


def actions_use_usercase(actions):
    return (('usercase_update' in actions and actions['usercase_update'].update) or
            ('usercase_preload' in actions and actions['usercase_preload'].preload))


def advanced_actions_use_usercase(actions):
    return any(c.auto_select and c.auto_select.mode == AUTO_SELECT_USERCASE for c in actions.load_update_cases)


def enable_usercase(domain_name):
    with CriticalSection(['enable_usercase_' + domain_name]):
        domain_obj = Domain.get_by_name(domain_name, strict=True)
        if not domain_obj:  # copying domains passes in an id before name is saved
            domain_obj = Domain.get(domain_name)
        if not domain_obj.usercase_enabled:
            domain_obj.usercase_enabled = True
            domain_obj.save()
            create_usercases.delay(domain_name)


def prefix_usercase_properties(properties):
    return {'{}{}'.format(USERCASE_PREFIX, prop) for prop in properties}


def module_offers_registry_search(module):
    return (
        module_offers_search(module)
        and module.get_app().supports_data_registry
        and module.search_config.data_registry
    )


def module_loads_registry_case(module):
    return (
        module_offers_registry_search(module)
        and module.search_config.data_registry_workflow == REGISTRY_WORKFLOW_LOAD_CASE
    )


def module_uses_smart_links(module):
    return (
        module_offers_registry_search(module)
        and module.search_config.data_registry_workflow == REGISTRY_WORKFLOW_SMART_LINK
    )


def module_offers_search(module):
    from corehq.apps.app_manager.models import AdvancedModule, Module, ShadowModule

    return (
        isinstance(module, (Module, AdvancedModule, ShadowModule)) and
        module.search_config
        and (module.search_config.properties
        or module.search_config.default_properties)
    )


def module_uses_inline_search(module):
    """In 'inline search' mode the query and post are added to the form entry directly instead
    of creating a separate RemoteRequest entry."""
    return (
        module_offers_search(module)
        and module.search_config.inline_search
        and module.search_config.auto_launch
    )


def module_uses_inline_search_with_parent_relationship_parent_select(module):
    return (
        module_uses_inline_search(module)
        and hasattr(module, 'parent_select')
        and module.parent_select.active
        and module.parent_select.relationship == 'parent'
    )


def module_uses_include_all_related_cases(module):
    return (
        module_offers_search(module)
        and module.search_config.include_all_related_cases
    )


def get_cloudcare_session_data(domain_name, form, couch_user):
    from corehq.apps.app_manager.suite_xml.sections.entries import EntriesHelper

    datums = EntriesHelper.get_new_case_id_datums_meta(form)
    session_data = {datum.id: uuid.uuid4().hex for datum in datums}
    if couch_user.doc_type in ('CommCareUser', 'WebUser'):  # smsforms.app.start_session could pass a CommCareCase
        try:
            extra_datums = EntriesHelper.get_extra_case_id_datums(form)
        except SuiteError as err:
            _assert = soft_assert(['nhooper_at_dimagi_dot_com'.replace('_at_', '@').replace('_dot_', '.')])
            _assert(False, 'Domain "%s": %s' % (domain_name, err))
        else:
            if EntriesHelper.any_usercase_datums(extra_datums):
                restore_user = couch_user.to_ota_restore_user(domain_name)
                usercase_id = restore_user.get_usercase_id()
                if usercase_id:
                    session_data[USERCASE_ID] = usercase_id
    return session_data


def update_form_unique_ids(app_source, ids_map, update_all=True):
    """
    Accepts an ids_map translating IDs in app_source to the desired replacement
    ID. Form IDs not present in ids_map will be given new random UUIDs.
    """
    from corehq.apps.app_manager.models import form_id_references, jsonpath_update

    app_source = deepcopy(app_source)
    attachments = app_source['_attachments']

    def change_form_unique_id(form, old_id, new_id):
        form['unique_id'] = new_id
        if f"{old_id}.xml" in attachments:
            attachments[f"{new_id}.xml"] = attachments.pop(f"{old_id}.xml")

    # once Application.wrap includes deleting user_registration
    # we can remove this
    if 'user_registration' in app_source:
        del app_source['user_registration']

    new_ids_by_old = {}
    for m, module in enumerate(app_source['modules']):
        for f, form in enumerate(module['forms']):
            old_id = form['unique_id']
            if update_all or old_id in ids_map:
                new_id = ids_map.get(old_id, uuid.uuid4().hex)
                new_ids_by_old[old_id] = new_id
                change_form_unique_id(form, old_id, new_id)

    for reference_path in form_id_references:
        for reference in reference_path.find(app_source):
            if reference.value in new_ids_by_old:
                jsonpath_update(reference, new_ids_by_old[reference.value])

    return app_source


def update_report_module_ids(app_source):
    """Make new report UUIDs so they stay unique

    Otherwise there would be multiple reports in the restore with the same UUID
    Set the report slug to the old UUID so any xpath expressions referencing
    the report by ID continue to work, if only in mobile UCR v2
    """
    app_source = deepcopy(app_source)
    for module in app_source['modules']:
        if module['module_type'] == 'report':
            for config in module['report_configs']:
                if not config.get('report_slug'):
                    config['report_slug'] = config['uuid']
                config['uuid'] = uuid.uuid4().hex
    return app_source


def _app_callout_templates():
    """Load app callout templates from config file on disk

    Generator function defers file access until needed, acts like a
    constant thereafter.
    """
    path = os.path.join(
        os.path.dirname(__file__),
        'static', 'app_manager', 'json', 'vellum-app-callout-templates.yml'
    )
    if os.path.exists(path):
        with open(path, encoding='utf-8') as f:
            data = yaml.safe_load(f)
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


def get_sort_and_sort_only_columns(detail_columns, sort_elements):
    """
    extracts out info about columns that are added as only sort fields and columns added as both
    sort and display fields
    """
    sort_elements = OrderedDict((s.field, (s, i + 1)) for i, s in enumerate(sort_elements))
    sort_columns = {}
    for column in detail_columns:
        sort_element, order = sort_elements.pop(column.field, (None, None))
        if sort_element:
            sort_columns[column.field] = (sort_element, order)

    # pull out sort elements that refer to calculated columns
    for field in list(sort_elements):
        match = re.match(CALCULATED_SORT_FIELD_RX, field)
        if match:
            element, element_order = sort_elements.pop(field)
            column_index = int(match.group(1))
            try:
                column = detail_columns[column_index]
            except IndexError:
                raise AppManagerException(f"Sort column references an unknown column at index: {column_index}")
            if not column.useXpathExpression:
                raise AppManagerException(f"Calculation sort column references an incorrect column: {column.field}")
            sort_columns[column.field] = (element, element_order)

    sort_only_elements = [
        SortOnlyElement(field, element, element_order)
        for field, (element, element_order) in sort_elements.items()
    ]
    return sort_only_elements, sort_columns


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


def get_form_source_download_url(xform):
    """Returns the download url for the form source for a submitted XForm
    """
    if not xform.build_id:
        return None

    try:
        app = get_app(xform.domain, xform.build_id)
    except Http404:
        return None
    if app.is_remote_app():
        return None

    try:
        form = app.get_forms_by_xmlns(xform.xmlns)[0]
    except IndexError:
        return None

    return reverse("app_download_file", args=[
        xform.domain,
        xform.build_id,
        app.get_form_filename(module=form.get_module(), form=form),
    ])


@quickcache(['domain', 'profile_id'], timeout=24 * 60 * 60)
def get_latest_enabled_build_for_profile(domain, profile_id):
    from corehq.apps.app_manager.models import LatestEnabledBuildProfiles
    latest_enabled_build = (LatestEnabledBuildProfiles.objects.
                            filter(build_profile_id=profile_id, active=True)
                            .order_by('-version')
                            .first())
    if latest_enabled_build:
        return get_app(domain, latest_enabled_build.build_id)


@quickcache(['domain', 'location_id', 'app_id'], timeout=24 * 60 * 60)
def get_latest_app_release_by_location(domain, location_id, app_id):
    """
    for a location search for enabled app releases for all parent locations.
    Child location's setting takes precedence over parent
    """
    from corehq.apps.app_manager.models import AppReleaseByLocation
    location = SQLLocation.active_objects.get(location_id=location_id)
    location_and_ancestor_ids = location.get_ancestors(include_self=True).values_list(
        'location_id', flat=True).reverse()
    # get all active enabled releases and order by version desc to get one with the highest version in the end
    # for a location. Do not use the first object itself in order to respect the location hierarchy and use
    # the closest location to determine the valid active release
    latest_enabled_releases = {
        release.location_id: release.build_id
        for release in
        AppReleaseByLocation.objects.filter(
            location_id__in=location_and_ancestor_ids, app_id=app_id, domain=domain, active=True).order_by(
            'version')
    }
    for loc_id in location_and_ancestor_ids:
        build_id = latest_enabled_releases.get(loc_id)
        if build_id:
            return get_app(domain, build_id)


def expire_get_latest_app_release_by_location_cache(app_release_by_location):
    """
    expire cache for the location and its descendants for the app corresponding to this enabled app release
    why? : Latest enabled release for a location is dependent on restrictions added for
    itself and its ancestors. Hence we expire the cache for location and its descendants for which the
    latest enabled release would depend on this location
    """
    location = SQLLocation.active_objects.get(location_id=app_release_by_location.location_id)
    location_and_descendants = location.get_descendants(include_self=True)
    for loc in location_and_descendants:
        get_latest_app_release_by_location.clear(app_release_by_location.domain, loc.location_id,
                                          app_release_by_location.app_id)


@quickcache(['app_id'], timeout=24 * 60 * 60)
def get_latest_enabled_versions_per_profile(app_id):
    from corehq.apps.app_manager.models import LatestEnabledBuildProfiles
    # a dict with each profile id mapped to its latest enabled version number, if present
    return {
        build_profile['build_profile_id']: build_profile['version__max']
        for build_profile in
        LatestEnabledBuildProfiles.objects.filter(app_id=app_id, active=True).values('build_profile_id').annotate(
            Max('version'))
    }


def get_app_id_from_form_unique_id(domain, form_unique_id):
    """
    Do not use. This is here to support migrations and temporary cose for *removing*
    the constraint that form ids be lgobally unique. It will stop working as more
    duplicated form unique ids appear.
    """
    return _get_app_ids_by_form_unique_id(domain).get(form_unique_id)


@quickcache(['domain'], timeout=1 * 60 * 60)
def _get_app_ids_by_form_unique_id(domain):
    apps = get_apps_in_domain(domain, include_remote=False)
    app_ids = {}
    for app in apps:
        for module in app.modules:
            for form in module.get_forms():
                if form.unique_id in app_ids:
                    raise AppManagerException("Could not identify app for form {}".format(form.unique_id))
                app_ids[form.unique_id] = app.get_id
    return app_ids


def extract_instance_id_from_nodeset_ref(nodeset):
    # note: for simplicity, this only returns the first instance ref in the event there are multiple.
    # if that's ever a problem this method could be changed in the future to return a list
    if nodeset:
        matches = re.findall(r"instance\('(.*?)'\)", nodeset)
        return matches[0] if matches else None
