from collections import defaultdict
import functools
import json
import itertools
import uuid
from corehq.apps.app_manager.exceptions import SuiteError
from corehq.apps.builds.models import CommCareBuildConfig
from corehq.apps.app_manager.tasks import create_user_cases
from corehq.util.quickcache import quickcache
from corehq.util.soft_assert import soft_assert
from couchdbkit.exceptions import DocTypeError
from corehq import Domain
from corehq.apps.app_manager.const import (
    CT_REQUISITION_MODE_3,
    CT_LEDGER_STOCK,
    CT_LEDGER_REQUESTED,
    CT_REQUISITION_MODE_4,
    CT_LEDGER_APPROVED,
    CT_LEDGER_PREFIX,
    AUTO_SELECT_USERCASE,
    USERCASE_TYPE,
    USERCASE_ID,
    USERCASE_PREFIX)
from corehq.apps.app_manager.xform import XForm, XFormException, parse_xml
from dimagi.utils.couch import CriticalSection
import re
from dimagi.utils.decorators.memoized import memoized
from django.core.cache import cache
import logging

logger = logging.getLogger(__name__)


def get_app_id(form):
    """
    Given an XForm instance, try to grab the app id, returning
    None if not available. This is just a shortcut since the app_id
    might not always be set.
    """
    return getattr(form, "app_id", None)


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

CASE_TYPE_REGEX = r'^[\w-]+$'
_case_type_regex = re.compile(CASE_TYPE_REGEX)

def is_valid_case_type(case_type):
    """
    >>> is_valid_case_type('foo')
    True
    >>> is_valid_case_type('foo-bar')
    True
    >>> is_valid_case_type('foo bar')
    False
    >>> is_valid_case_type('')
    False
    >>> is_valid_case_type(None)
    False
    >>> is_valid_case_type('commcare-user')
    False

    """
    return bool(_case_type_regex.match(case_type or '')) and case_type != USERCASE_TYPE


class ParentCasePropertyBuilder(object):
    def __init__(self, app, defaults=(), per_type_defaults=None):
        self.app = app
        self.defaults = defaults
        self.per_type_defaults = per_type_defaults or {}

    @property
    @memoized
    def forms_info(self):
        # unfortunate, but biggest speed issue is accessing couchdbkit properties
        # so compute them once

        forms_info = []
        if self.app.doc_type == 'RemoteApp':
            return forms_info
        for module in self.app.get_modules():
            for form in module.get_forms():
                forms_info.append((module.case_type, form))
        return forms_info

    @memoized
    def get_parent_types_and_contributed_properties(self, case_type):
        parent_types = set()
        case_properties = set()
        for m_case_type, form in self.forms_info:
            p_types, c_props = form.get_parent_types_and_contributed_properties(m_case_type, case_type)
            parent_types.update(p_types)
            case_properties.update(c_props)
        return parent_types, case_properties

    def get_parent_types(self, case_type):
        parent_types, _ = \
            self.get_parent_types_and_contributed_properties(case_type)
        return set(p[0] for p in parent_types)

    @memoized
    def get_other_case_sharing_apps_in_domain(self):
        from corehq.apps.app_manager.models import get_apps_in_domain
        apps = get_apps_in_domain(self.app.domain, include_remote=False)
        return [a for a in apps if a.case_sharing and a.id != self.app.id]

    @memoized
    def get_properties(self, case_type, already_visited=(),
                       include_shared_properties=True,
                       include_parent_properties=True):
        if case_type in already_visited:
            return ()

        case_properties = set(self.defaults) | set(self.per_type_defaults.get(case_type, []))

        for m_case_type, form in self.forms_info:
            case_properties.update(self.get_case_updates(form, case_type))

        parent_types, contributed_properties = \
            self.get_parent_types_and_contributed_properties(case_type)
        case_properties.update(contributed_properties)
        if include_parent_properties:
            get_properties_recursive = functools.partial(
                self.get_properties,
                already_visited=already_visited + (case_type,),
                include_shared_properties=include_shared_properties
            )
            for parent_type in parent_types:
                for property in get_properties_recursive(parent_type[0]):
                    case_properties.add('%s/%s' % (parent_type[1], property))
        if self.app.case_sharing and include_shared_properties:
            from corehq.apps.app_manager.models import get_apps_in_domain
            for app in self.get_other_case_sharing_apps_in_domain():
                case_properties.update(
                    get_case_properties(
                        app, [case_type],
                        include_shared_properties=False,
                        include_parent_properties=include_parent_properties,
                    ).get(case_type, [])
                )
        return case_properties

    @memoized
    def get_case_updates(self, form, case_type):
        return form.get_case_updates(case_type)

    def get_parent_type_map(self, case_types):
        """
        :returns: A dict
        ```
        {<case_type>: {<relationship>: <parent_type>, ...}, ...}
        ```
        """
        parent_map = defaultdict(dict)
        for case_type in case_types:
            parent_types, _ = self.get_parent_types_and_contributed_properties(case_type)
            rel_map = defaultdict(list)
            for parent_type, relationship in parent_types:
                rel_map[relationship].append(parent_type)

            for relationship, types in rel_map.items():
                if len(types) > 1:
                    logger.error(
                        "Case Type '%s' has multiple parents for relationship '%s': %s",
                        case_type, relationship, types
                    )
                parent_map[case_type][relationship] = types[0]

        return parent_map

    def get_case_property_map(self, case_types,
                              include_shared_properties=True,
                              include_parent_properties=True):
        case_types = sorted(case_types)
        return {
            case_type: sorted(self.get_properties(
                case_type,
                include_shared_properties=include_shared_properties,
                include_parent_properties=include_parent_properties,
            ))
            for case_type in case_types
        }


def get_case_properties(app, case_types, defaults=(),
                        include_shared_properties=True,
                        include_parent_properties=True):
    per_type_defaults = get_per_type_defaults(app.domain, case_types)
    builder = ParentCasePropertyBuilder(app, defaults, per_type_defaults=per_type_defaults)
    return builder.get_case_property_map(
        case_types,
        include_shared_properties=include_shared_properties,
        include_parent_properties=include_parent_properties,
    )


def get_per_type_defaults(domain, case_types=None):
    from corehq.apps.callcenter.utils import get_call_center_case_type_if_enabled

    per_type_defaults = {}
    if (not case_types and is_usercase_in_use(domain)) or USERCASE_TYPE in case_types:
        per_type_defaults = {
            USERCASE_TYPE: get_usercase_default_properties(domain)
        }

    callcenter_case_type = get_call_center_case_type_if_enabled(domain)
    if callcenter_case_type and (not case_types or callcenter_case_type in case_types):
        per_type_defaults[callcenter_case_type] = get_usercase_default_properties(domain)

    return per_type_defaults


def is_usercase_in_use(domain_name):
    domain = Domain.get_by_name(domain_name) if domain_name else None
    return domain and domain.usercase_enabled


def get_all_case_properties(app):
    return get_case_properties(app, app.get_case_types(), defaults=('name',))


def get_casedb_schema(app):
    """Get case database schema definition

    This lists all case types and their properties for the given app.
    """
    case_types = app.get_case_types()
    per_type_defaults = get_per_type_defaults(app.domain, case_types)
    builder = ParentCasePropertyBuilder(app, ['name'], per_type_defaults)
    related = builder.get_parent_type_map(case_types)
    map = builder.get_case_property_map(case_types, include_parent_properties=False)
    return {
        "id": "casedb",
        "uri": "jr://instance/casedb",
        "name": "case",
        "path": "/casedb/case",
        "structure": {},
        "subsets": [{
            "id": ctype,
            "key": "@case_type",
            "structure": {p: {} for p in props},
            "related": related.get(ctype),  # {<relationship>: <parent_type>, ...}
        } for ctype, props in sorted(map.iteritems())],
    }


def get_session_schema(form):
    """Get form session schema definition
    """
    structure = {}
    # TODO handle advanced modules with more than one case
    case_type = form.get_module().case_type
    if case_type:
        structure["case_id"] = {
            "reference": {
                "source": "casedb",
                "subset": case_type,
                "key": "@case_id",
            },
        }
    return {
        "id": "commcaresession",
        "uri": "jr://instance/session",
        "name": "Session",
        "path": "/session/data",
        "structure": structure,
    }


def get_usercase_properties(app):
    if is_usercase_in_use(app.domain):
        return get_case_properties(app, [USERCASE_TYPE])
    return {USERCASE_TYPE: []}


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


def create_temp_sort_column(field, index):
    """
    Used to create a column for the sort only properties to
    add the field to the list of properties and app strings but
    not persist anything to the detail data.
    """
    from corehq.apps.app_manager.models import SortOnlyDetailColumn
    return SortOnlyDetailColumn(
        model='case',
        field=field,
        format='invisible',
        header=None,
    )


def is_sort_only_column(column):
    from corehq.apps.app_manager.models import SortOnlyDetailColumn
    return isinstance(column, SortOnlyDetailColumn)


def get_correct_app_class(doc):
    from corehq.apps.app_manager.models import Application, RemoteApp
    try:
        return {
            'Application': Application,
            'Application-Deleted': Application,
            "RemoteApp": RemoteApp,
            "RemoteApp-Deleted": RemoteApp,
        }[doc['doc_type']]
    except KeyError:
        raise DocTypeError()


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


def commtrack_ledger_sections(mode):
    sections = [CT_LEDGER_STOCK]
    if mode == CT_REQUISITION_MODE_3:
        sections += [CT_LEDGER_REQUESTED]
    elif mode == CT_REQUISITION_MODE_4:
        sections += [CT_LEDGER_REQUESTED, CT_LEDGER_APPROVED]

    return ['{}{}'.format(CT_LEDGER_PREFIX, s) for s in sections]


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
    ValueError: invalid literal for int() ...

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
        if not domain.usercase_enabled:
            domain.usercase_enabled = True
            domain.save()
            create_user_cases.delay(domain_name)


@quickcache(['domain'])
def get_usercase_default_properties(domain):
    from corehq.apps.custom_data_fields.models import CustomDataFieldsDefinition
    from corehq.apps.users.views.mobile.custom_data_fields import CUSTOM_USER_DATA_FIELD_TYPE

    fields_def = CustomDataFieldsDefinition.get_or_create(domain, CUSTOM_USER_DATA_FIELD_TYPE)
    return [f.slug for f in fields_def.fields]


def prefix_usercase_properties(properties):
    return {'{}{}'.format(USERCASE_PREFIX, prop) for prop in properties}


def get_cloudcare_session_data(suite_gen, domain_name, form, couch_user):
    from corehq.apps.hqcase.utils import get_case_by_domain_hq_user_id

    datums = suite_gen.get_new_case_id_datums_meta(form)
    session_data = {datum['datum'].id: uuid.uuid4().hex for datum in datums}
    if couch_user.doc_type == 'CommCareUser':  # smsforms.app.start_session could pass a CommCareCase
        try:
            extra_datums = suite_gen.get_extra_case_id_datums(form)
        except SuiteError as err:
            _assert = soft_assert(['nhooper_at_dimagi_dot_com'.replace('_at_', '@').replace('_dot_', '.')])
            _assert(False, 'Domain "%s": %s' % (domain_name, err))
        else:
            if suite_gen.any_usercase_datums(extra_datums):
                usercase = get_case_by_domain_hq_user_id(domain_name, couch_user.get_id, USERCASE_TYPE)
                if usercase:
                    session_data[USERCASE_ID] = usercase.get_id
    return session_data
