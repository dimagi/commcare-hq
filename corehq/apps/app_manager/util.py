from __future__ import absolute_import
from __future__ import unicode_literals

import json
import os
import uuid
import re
import logging
import yaml
from collections import OrderedDict, namedtuple
from copy import deepcopy
from io import open


from couchdbkit import ResourceNotFound
from couchdbkit.exceptions import DocTypeError
from memoized import memoized

from django.urls import reverse
from django.core.cache import cache
from django.http import Http404
from django.utils.translation import ugettext as _
from django.db.models import Max

from corehq import toggles
from corehq.apps.app_manager.dbaccessors import (
    get_apps_in_domain, get_app
)
from corehq.apps.app_manager.exceptions import SuiteError, SuiteValidationError, PracticeUserException
from corehq.apps.app_manager.xpath import UserCaseXPath
from corehq.apps.builds.models import CommCareBuildConfig
from corehq.apps.app_manager.tasks import create_user_cases
from corehq.apps.locations.models import SQLLocation
from corehq.util.soft_assert import soft_assert
from corehq.apps.domain.models import Domain
from corehq.apps.app_manager.const import (
    AUTO_SELECT_USERCASE,
    USERCASE_TYPE,
    USERCASE_ID,
    USERCASE_PREFIX,
)
from corehq.apps.app_manager.exceptions import XFormException
from corehq.apps.app_manager.xform import XForm, parse_xml
from corehq.apps.users.models import CommCareUser
from corehq.util.quickcache import quickcache
from dimagi.utils.couch import CriticalSection


logger = logging.getLogger(__name__)

CASE_XPATH_SUBSTRING_MATCHES = [
    "instance('casedb')",
    'session/data/case_id',
    "#case",
    "#parent",
    "#host",
]

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
    # case, see xpath_references_user_case()
    # Assumes xpath has already been dot interpolated as needed.
    for substring in USER_CASE_XPATH_SUBSTRING_MATCHES:
        xpath = xpath.replace(substring, '')

    return _check_xpath_for_matches(
        xpath,
        substring_matches=CASE_XPATH_SUBSTRING_MATCHES,
    )


def xpath_references_user_case(xpath):
    # Assumes xpath has already been dot interpolated as needed.
    return _check_xpath_for_matches(
        xpath,
        substring_matches=USER_CASE_XPATH_SUBSTRING_MATCHES,
    )


def split_path(path):
    path_parts = path.split('/')
    name = path_parts.pop(-1)
    path = '/'.join(path_parts)
    return path, name


def first_elem(elem_list):
    return elem_list[0] if elem_list else None


def save_xform(app, form, xml):

    def change_xmlns(xform, old_xmlns, new_xmlns):
        data = xform.data_node.render().decode('utf-8')
        data = data.replace(old_xmlns, new_xmlns, 1)
        xform.instance_node.remove(xform.data_node.xml)
        xform.instance_node.append(parse_xml(data))
        return xform.render()

    try:
        xform = XForm(xml)
    except XFormException:
        pass
    else:
        GENERIC_XMLNS = "http://www.w3.org/2002/xforms"
        # we assume form.get_unique_id() is unique across all of HQ and
        # therefore is suitable to create an XMLNS that will not confict
        # with any other form
        uid = form.get_unique_id()
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

    if form.is_registration_form():
        # For registration forms, assume that the first question is the
        # case name unless something else has been specified
        questions = form.get_questions([app.default_language])
        if hasattr(form.actions, 'open_case'):
            path = form.actions.open_case.name_path
            if path:
                name_questions = [q for q in questions if q['value'] == path]
                if not len(name_questions):
                    path = None
            if not path and len(questions):
                form.actions.open_case.name_path = questions[0]['value']

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


def update_form_unique_ids(app_source, form_ids_by_xmlns=None):
    from corehq.apps.app_manager.models import form_id_references, jsonpath_update

    app_source = deepcopy(app_source)

    def change_form_unique_id(form, ids_by_xmlns):
        unique_id = form['unique_id']
        new_unique_id = ids_by_xmlns.get(form['xmlns'], uuid.uuid4().hex)
        form['unique_id'] = new_unique_id
        if ("%s.xml" % unique_id) in app_source['_attachments']:
            app_source['_attachments']["%s.xml" % new_unique_id] = app_source['_attachments'].pop("%s.xml" % unique_id)
        return new_unique_id

    # once Application.wrap includes deleting user_registration
    # we can remove this
    if 'user_registration' in app_source:
        del app_source['user_registration']

    id_changes = {}
    if form_ids_by_xmlns is None:
        form_ids_by_xmlns = {}
    for m, module in enumerate(app_source['modules']):
        for f, form in enumerate(module['forms']):
            old_id = form['unique_id']
            new_id = change_form_unique_id(app_source['modules'][m]['forms'][f], form_ids_by_xmlns)
            id_changes[old_id] = new_id

    for reference_path in form_id_references:
        for reference in reference_path.find(app_source):
            if reference.value in id_changes:
                jsonpath_update(reference, id_changes[reference.value])

    return app_source


def update_report_module_ids(app_source):
    app_source = deepcopy(app_source)
    for module in app_source['modules']:
        if module['module_type'] == 'report':
            for config in module['report_configs']:
                config['uuid'] = uuid.uuid4().hex
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


class LatestAppInfo(object):

    def __init__(self, brief_app_id, domain):
        """
        Wrapper to get latest app version and CommCare APK version info

        args:
            brief_app_id: id of an app that is not copy (to facilitate quickcaching)

        raises Http404 error if id is not valid
        raises assertion error if an id of app copy is passed
        """
        self.app_id = brief_app_id
        self.domain = domain

    @property
    @memoized
    def app(self):
        app = get_app(self.domain, self.app_id, latest=True, target='release')
        # quickache based on a copy app_id will have to be updated too fast
        is_app_id_brief = self.app_id == app.master_id
        assert is_app_id_brief, "this class doesn't handle copy app ids"
        return app

    def clear_caches(self):
        self.get_latest_app_version.clear(self)

    def get_latest_apk_version(self):
        from corehq.apps.app_manager.models import LATEST_APK_VALUE
        from corehq.apps.builds.models import BuildSpec
        from corehq.apps.builds.utils import get_default_build_spec
        if self.app.global_app_config.apk_prompt == "off":
            return {}
        else:
            configured_version = self.app.global_app_config.apk_version
            if configured_version == LATEST_APK_VALUE:
                value = get_default_build_spec().version
            else:
                value = BuildSpec.from_string(configured_version).version
            force = self.app.global_app_config.apk_prompt == "forced"
            return {"value": value, "force": force}

    @quickcache(vary_on=['self.app_id'])
    def get_latest_app_version(self):
        from corehq.apps.app_manager.models import LATEST_APP_VALUE
        if self.app.global_app_config.app_prompt == "off":
            return {}
        else:
            force = self.app.global_app_config.app_prompt == "forced"
            app_version = self.app.global_app_config.app_version
            if app_version != LATEST_APP_VALUE:
                return {"value": app_version, "force": force}
            else:
                if not self.app or not self.app.is_released:
                    return {}
                else:
                    return {"value": self.app.version, "force": force}

    def get_info(self):
        return {
            "latest_apk_version": self.get_latest_apk_version(),
            "latest_ccz_version": self.get_latest_app_version(),
        }


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
    except KeyError:
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
