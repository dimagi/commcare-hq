from __future__ import absolute_import
from __future__ import unicode_literals
from collections import defaultdict
import functools
from itertools import chain
import logging

from corehq import toggles
from corehq.apps.app_manager.const import USERCASE_TYPE
from corehq.apps.app_manager.dbaccessors import get_case_sharing_apps_in_domain
from corehq.apps.app_manager.util import is_usercase_in_use, all_apps_by_domain
from corehq.apps.data_dictionary.models import CaseProperty
from corehq.util.quickcache import quickcache
from memoized import memoized
import six


logger = logging.getLogger(__name__)


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

    @property
    @memoized
    def case_sharing_app_forms_info(self):
        forms_info = []
        for app in self.get_other_case_sharing_apps_in_domain():
            for module in app.get_modules():
                for form in module.get_forms():
                    forms_info.append((module.case_type, form))
        return forms_info

    @memoized
    def get_parent_types_and_contributed_properties(self, case_type, include_shared_properties=True):
        parent_types = set()
        case_properties = set()
        forms_info = self.forms_info
        if self.app.case_sharing and include_shared_properties:
            forms_info += self.case_sharing_app_forms_info

        for m_case_type, form in forms_info:
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
        return get_case_sharing_apps_in_domain(self.app.domain, self.app.id)

    @memoized
    def get_properties(self, case_type, already_visited=(),
                       include_shared_properties=True,
                       include_parent_properties=True):
        if case_type in already_visited:
            return ()

        case_properties = set(self.defaults) | set(self.per_type_defaults.get(case_type, []))

        for m_case_type, form in self.forms_info:
            updates = self.get_case_updates(form, case_type)
            if include_parent_properties:
                case_properties.update(updates)
            else:
                # HACK exclude case updates that reference properties like "parent/property_name"
                # TODO add parent property updates to the parent case type(s) of m_case_type
                # Currently if a property is only ever updated via parent property
                # reference, then I think it will not appear in the schema.
                case_properties.update(p for p in updates if "/" not in p)
            case_properties.update(self.get_save_to_case_updates(form, case_type))

        if toggles.DATA_DICTIONARY.enabled(self.app.domain):
            data_dict_props = CaseProperty.objects.filter(case_type__domain=self.app.domain,
                                                          case_type__name=case_type, deprecated=False)
            case_properties |= {prop.name for prop in data_dict_props}

        parent_types, contributed_properties = self.get_parent_types_and_contributed_properties(
            case_type, include_shared_properties=include_shared_properties
        )
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

    @memoized
    def get_save_to_case_updates(self, form, case_type):
        return form.get_save_to_case_updates(case_type)

    def get_parent_type_map(self, case_types, allow_multiple_parents=False):
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
                if allow_multiple_parents:
                    parent_map[case_type][relationship] = types
                else:
                    if len(types) > 1:
                        logger.error(
                            "Case Type '%s' in app '%s' has multiple parents for relationship '%s': %s",
                            case_type, self.app.id, relationship, types
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


def get_all_case_properties(app):
    return get_case_properties(app, app.get_case_types(), defaults=('name',))


def get_usercase_properties(app):
    if is_usercase_in_use(app.domain):
        # TODO: add name here once it is fixed to concatenate first and last in form builder
        default_properties = {'first_name', 'last_name', 'phone_number', 'username'}
        case_properties = get_case_properties(app, [USERCASE_TYPE])
        case_properties[USERCASE_TYPE] = list(set(case_properties[USERCASE_TYPE]) | default_properties)
        return case_properties
    return {USERCASE_TYPE: []}


def all_case_properties_by_domain(domain, case_types=None, include_parent_properties=True):
    result = {}
    for app in all_apps_by_domain(domain):
        if app.is_remote_app():
            continue

        if case_types is None:
            case_types = app.get_case_types()

        property_map = get_case_properties(app, case_types,
            defaults=('name',), include_parent_properties=include_parent_properties)

        for case_type, properties in six.iteritems(property_map):
            if case_type in result:
                result[case_type].extend(properties)
            else:
                result[case_type] = properties

    cleaned_result = {}
    for case_type, properties in six.iteritems(result):
        properties = list(set(properties))
        properties.sort()
        cleaned_result[case_type] = properties

    return cleaned_result


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


def get_shared_case_types(app):
    shared_case_types = set()

    if app.case_sharing:
        apps = get_case_sharing_apps_in_domain(app.domain, app.id)
        for app in apps:
            shared_case_types |= set(chain(*[m.get_case_types() for m in app.get_modules()]))

    return shared_case_types


@quickcache(['domain'])
def get_usercase_default_properties(domain):
    from corehq.apps.custom_data_fields.models import CustomDataFieldsDefinition
    from corehq.apps.users.views.mobile.custom_data_fields import CUSTOM_USER_DATA_FIELD_TYPE

    fields_def = CustomDataFieldsDefinition.get_or_create(domain, CUSTOM_USER_DATA_FIELD_TYPE)
    return [f.slug for f in fields_def.fields]
