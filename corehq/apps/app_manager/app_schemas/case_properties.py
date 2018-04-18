from __future__ import absolute_import
from __future__ import unicode_literals
from __future__ import print_function
from collections import defaultdict, deque, namedtuple
import functools
from itertools import chain, groupby
from operator import attrgetter
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


def _get_forms(app):
    """
    Return list of forms in the app
    """
    if app.doc_type == 'RemoteApp':
        return []
    forms = []
    for module in app.get_modules():
        forms.extend(module.get_forms())
    return forms


def _zip_update(properties_by_case_type, additional_properties_by_case_type):
    for case_type, case_properties in additional_properties_by_case_type.items():
        properties_by_case_type[case_type].update(case_properties)


_CaseTypeRef = namedtuple('_CaseTypeRef', ['case_type', 'relationship_path'])
_PropertyRef = namedtuple('_PropertyRef', ['case_type_ref', 'case_property'])
_CaseTypeEquivalence = namedtuple('_CaseTypeEquivalence', ['case_type', 'expansion'])


class _CaseRelationshipManager(object):

    def __init__(self, parent_type_map, case_types=()):
        self.parent_type_map = parent_type_map
        for case_type in case_types:
            self.parent_type_map[case_type].update({})

    def expand_case_type(self, case_type):
        return self._case_type_to_expansions[case_type]

    def resolve_expansion(self, case_type_ref):
        return self._expansion_to_case_types[case_type_ref]

    @property
    @memoized
    def _all_possible_equivalences(self):
        """
        If referral is a child case of patient, which is the child case of a household,
        then this will return

        {
            # a referral is a referral
            _CaseTypeEquivalence('referral', _CaseTypeRef('referral', ())),
            # a patient is a patient
            _CaseTypeEquivalence('patient', _CaseTypeRef('patient', ())),
            # a patient is a referal's parent
            _CaseTypeEquivalence('patient', _CaseTypeRef('referral', ('parent',)))
            # a household is a household
            _CaseTypeEquivalence('household', _CaseTypeRef('household', ())),
            # a household is a patient's parent
            _CaseTypeEquivalence('household', _CaseTypeRef('patient', ('parent'))),
            # a houseold is a referral's parent's parent
            _CaseTypeEquivalence('household', _CaseTypeRef('referral', ('parent', 'parent')))
        }
        """
        all_possible_equivalences = set()
        equivalence_queue = deque(_CaseTypeEquivalence(case_type, _CaseTypeRef(case_type, ()))
                                  for case_type in self.parent_type_map)
        while True:
            try:
                equivalence = equivalence_queue.popleft()
            except IndexError:
                break
            all_possible_equivalences.add(equivalence)
            parent, (child, relationship_path) = equivalence
            for relationship, grandparents in self.parent_type_map[parent].items():
                for grandparent in grandparents:
                    new_equivalence = _CaseTypeEquivalence(
                        case_type=grandparent,
                        expansion=_CaseTypeRef(child, relationship_path + (relationship,))
                    )
                    cycle_found = (grandparent == child)
                    already_visited = (new_equivalence in all_possible_equivalences)
                    if not cycle_found and not already_visited:
                        equivalence_queue.append(new_equivalence)
        return all_possible_equivalences

    @property
    @memoized
    def _case_type_to_expansions(self):
        case_type_to_expansions = defaultdict(set)
        for equivalence in self._all_possible_equivalences:
            case_type_to_expansions[equivalence.case_type].add(equivalence.expansion)
        return case_type_to_expansions

    @property
    @memoized
    def _expansion_to_case_types(self):
        expansion_to_case_types = defaultdict(set)
        for equivalence in self._all_possible_equivalences:
            expansion_to_case_types[equivalence.expansion].add(equivalence.case_type)
        return expansion_to_case_types


def _flatten_case_properties(case_properties_by_case_type):
    result = set()
    for case_type, properties in case_properties_by_case_type.items():
        for case_property in properties:
            case_property_parts = tuple(case_property.split('/'))
            result.add(_PropertyRef(
                case_type_ref=_CaseTypeRef(case_type, relationship_path=case_property_parts[:-1]),
                case_property=case_property_parts[-1]
            ))
    return result


def _normalize_case_properties(case_properties_by_case_type, parent_type_map,
                               include_parent_properties):
    case_relationship_manager = _CaseRelationshipManager(
        parent_type_map, case_types=case_properties_by_case_type.keys())
    flattened_case_properties = _flatten_case_properties(case_properties_by_case_type)
    normalized_case_properties = set()
    for property_ref in flattened_case_properties:
        resolved_case_types = case_relationship_manager.resolve_expansion(property_ref.case_type_ref)
        if resolved_case_types:
            if include_parent_properties:
                normalized_case_properties.update({
                    _PropertyRef(expansion, property_ref.case_property)
                    for case_type in resolved_case_types
                    for expansion in case_relationship_manager.expand_case_type(case_type)
                })
            else:
                normalized_case_properties.update({
                    _PropertyRef(_CaseTypeRef(case_type, ()), property_ref.case_property)
                    for case_type in resolved_case_types
                })
        else:
            # if #case/parent doesn't match any known case type, leave the property_ref as is
            normalized_case_properties.add(property_ref)

    normalized_case_properties_by_case_type = defaultdict(set)
    for property_ref in normalized_case_properties:
        normalized_case_properties_by_case_type[property_ref.case_type_ref.case_type].add(
            '/'.join(property_ref.case_type_ref.relationship_path + (property_ref.case_property,)))
    return normalized_case_properties_by_case_type


class ParentCasePropertyBuilder(object):

    def __init__(self, app, defaults=(), per_type_defaults=None, include_parent_properties=True):
        self.app = app
        self.defaults = defaults
        self.per_type_defaults = per_type_defaults or {}
        self.include_parent_properties = include_parent_properties

    def _get_relevant_apps(self):
        apps = [self.app]
        if self.app.case_sharing:
            apps.extend(self._get_other_case_sharing_apps_in_domain())
        return apps

    @memoized
    def _get_relevant_forms(self):
        forms = []
        for app in self._get_relevant_apps():
            forms.extend(_get_forms(app))
        return forms

    @memoized
    def _get_all_case_updates(self):
        all_case_updates = defaultdict(set)
        for form in self._get_relevant_forms():
            for case_type, case_properties in form.get_all_case_updates().items():
                all_case_updates[case_type].update(case_properties)
        return all_case_updates

    @memoized
    def _get_data_dictionary_properties_by_case_type(self):
        return {
            case_type: {prop.name for prop in props} for case_type, props in groupby(
                CaseProperty.objects
                .filter(case_type__domain=self.app.domain, deprecated=False)
                .order_by('case_type__name'),
                key=attrgetter('case_type.name')
            )
        }

    def get_case_relationships_for_case_type(self, case_type):
        return self.get_case_relationships()[case_type]

    @memoized
    def get_case_relationships(self):
        case_relationships_by_child_type = defaultdict(set)

        for form in self._get_relevant_forms():
            for case_type, case_relationships in form.get_contributed_case_relationships().items():
                case_relationships_by_child_type[case_type].update(case_relationships)
        return case_relationships_by_child_type

    def get_parent_types(self, case_type):
        parent_types = self.get_case_relationships_for_case_type(case_type)
        return set(p[0] for p in parent_types)

    @memoized
    def _get_other_case_sharing_apps_in_domain(self):
        return get_case_sharing_apps_in_domain(self.app.domain, self.app.id)

    @memoized
    def get_properties(self, case_type):
        return self.get_properties_by_case_type()[case_type]

    @memoized
    def get_properties_by_case_type(self):
        case_properties_by_case_type = defaultdict(set)

        _zip_update(case_properties_by_case_type, self._get_all_case_updates())

        _zip_update(case_properties_by_case_type, self.per_type_defaults)

        if toggles.DATA_DICTIONARY.enabled(self.app.domain):
            _zip_update(case_properties_by_case_type, self._get_data_dictionary_properties_by_case_type())

        for case_properties in case_properties_by_case_type.values():
            case_properties.update(self.defaults)

        return _normalize_case_properties(
            case_properties_by_case_type,
            parent_type_map=self.get_parent_type_map(case_types=None, allow_multiple_parents=True),
            include_parent_properties=self.include_parent_properties
        )

    def get_parent_type_map(self, case_types, allow_multiple_parents=False):
        """
        :returns: A dict
        ```
        {<case_type>: {<relationship>: <parent_type>, ...}, ...}

        if case_types is None, then all available case types will be included
        ```
        """
        parent_map = defaultdict(dict)

        for case_type, case_relationships in self.get_case_relationships().items():
            rel_map = defaultdict(list)
            for parent_type, relationship in case_relationships:
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

        if case_types is not None:
            return {case_type: rel_map for case_type, rel_map in parent_map.items()
                    if case_type in case_types}
        return parent_map

    def get_case_property_map(self, case_types):
        case_types = sorted(case_types)
        return {
            case_type: sorted(self.get_properties(case_type))
            for case_type in case_types
        }


def get_case_relationships(app):
    builder = ParentCasePropertyBuilder(app)
    return builder.get_parent_type_map(app.get_case_types())


def get_case_properties(app, case_types, defaults=(), include_parent_properties=True):
    per_type_defaults = get_per_type_defaults(app.domain, case_types)
    builder = ParentCasePropertyBuilder(app, defaults, per_type_defaults=per_type_defaults,
                                        include_parent_properties=include_parent_properties)
    return builder.get_case_property_map(case_types)


def get_all_case_properties(app):
    return get_case_properties(app, app.get_case_types(), defaults=('name',))


def get_all_case_properties_for_case_type(domain, case_type):
    return all_case_properties_by_domain(domain, [case_type]).get(case_type, [])


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
            USERCASE_TYPE: _get_usercase_default_properties(domain)
        }

    callcenter_case_type = get_call_center_case_type_if_enabled(domain)
    if callcenter_case_type and (not case_types or callcenter_case_type in case_types):
        per_type_defaults[callcenter_case_type] = _get_usercase_default_properties(domain)

    return per_type_defaults


def get_shared_case_types(app):
    shared_case_types = set()

    if app.case_sharing:
        apps = get_case_sharing_apps_in_domain(app.domain, app.id)
        for app in apps:
            shared_case_types |= set(chain(*[m.get_case_types() for m in app.get_modules()]))

    return shared_case_types


@quickcache(['domain'])
def _get_usercase_default_properties(domain):
    from corehq.apps.custom_data_fields.models import CustomDataFieldsDefinition
    from corehq.apps.users.views.mobile.custom_data_fields import CUSTOM_USER_DATA_FIELD_TYPE

    fields_def = CustomDataFieldsDefinition.get_or_create(domain, CUSTOM_USER_DATA_FIELD_TYPE)
    return [f.slug for f in fields_def.fields]
