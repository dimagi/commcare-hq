import logging
from collections import defaultdict, deque, namedtuple

from memoized import memoized

from corehq.apps.app_manager.const import USERCASE_TYPE
from corehq.apps.app_manager.dbaccessors import (
    get_apps_in_domain,
    get_case_sharing_apps_in_domain,
)
from corehq.apps.app_manager.util import is_remote_app, is_usercase_in_use
from corehq.util.quickcache import quickcache
from corehq.apps.accounting.utils import domain_has_privilege
from corehq import privileges

logger = logging.getLogger(__name__)


def _get_forms(app):
    """
    Return list of forms in the app
    """
    if is_remote_app(app):
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


class _CaseTypeEquivalence(namedtuple('_CaseTypeEquivalence', ['case_type', 'expansion'])):
    """
    A statement of equivalence between a single doc type and a parent reference

    _CaseTypeEquivalence(case_type='household', expansion=_CaseTypeRef('referral', ('parent', 'parent'))
    is read "a `household` is a `referral`'s `parent`'s `parent`"

    A single case type may have _many_ expansions, and so many (true) _CaseTypeEquivalence may be
    formulated with the same case type. At the very least,

    _CaseTypeEquivalence(case_type='household', expansion=_CaseTypeRef('household', ())
    (read "A `household` is a `household`") is true for any case_type.

    """
    pass


class _CaseRelationshipManager(object):
    """
    Lets you convert between a case_type and its expansions (and vice versa)

    If referral is a child case of patient, which is the child case of a household,
    you can instantiate it like this:

    >>> case_relationship_manager = _CaseRelationshipManager({
    ...     'patient': {'parent': ['household']},
    ...     'referral': {'parent': ['patient']},
    ... }, case_types=['patient', 'referral', 'household'])

    You can then ask "what are the different ways a `patient` can be referred to?":

    >>> expansions = case_relationship_manager.expand_case_type('patient')
    >>> expansions == {
    ...     _CaseTypeRef(case_type='patient', relationship_path=()),
    ...     _CaseTypeRef(case_type='referral', relationship_path=('parent',))
    ... }
    True

    This is read "`patient` and `referral`'s parent are the two ways to refer to `patient`".


    You can also ask "What are all of the case_types a `referral`'s `parent` can be?":

    >>> case_relationship_manager.resolve_expansion(_CaseTypeRef('referral', ('parent',)))
    {'patient'}

    This is read "a `referral`'s parent can only be a `patient`".

    """
    def __init__(self, parent_type_map, case_types=()):
        self.parent_type_map = defaultdict(dict)
        self.parent_type_map.update(parent_type_map)
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
        Returns the set all possible case_type <=> case_type_ref equivalences

        for the parent_type_map and case_types given to this class.
        Using the referral > patient > household example above, all possible equivalences are:

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

        class TmpEquivalence(namedtuple('TmpEquivalence',
                                        ['case_type', 'expansion', 'visited_case_types'])):
            """same as a _CaseTypeEquivalence but with a memory of the case types visited"""

        equivalence_queue = deque(
            TmpEquivalence(case_type, _CaseTypeRef(case_type, ()), visited_case_types=frozenset())
            for case_type in self.parent_type_map
        )

        while True:
            try:
                eq = equivalence_queue.popleft()
            except IndexError:
                break
            all_possible_equivalences.add(eq)
            for relationship, parents in self.parent_type_map[eq.case_type].items():
                for parent in parents:
                    if parent in eq.visited_case_types:
                        continue
                    new_equivalence = TmpEquivalence(
                        case_type=parent,
                        expansion=_CaseTypeRef(
                            eq.expansion.case_type,
                            eq.expansion.relationship_path + (relationship,)
                        ),
                        visited_case_types=eq.visited_case_types | {parent}
                    )
                    already_visited = (new_equivalence in all_possible_equivalences)
                    if not already_visited:
                        equivalence_queue.append(new_equivalence)
        return {_CaseTypeEquivalence(case_type=eq.case_type, expansion=eq.expansion)
                for eq in all_possible_equivalences}

    @property
    @memoized
    def _case_type_to_expansions(self):
        """Organize equivalences as case_type => set of expansions mapping"""
        case_type_to_expansions = defaultdict(set)
        for equivalence in self._all_possible_equivalences:
            case_type_to_expansions[equivalence.case_type].add(equivalence.expansion)
        return case_type_to_expansions

    @property
    @memoized
    def _expansion_to_case_types(self):
        """Organize equivalences as expansion => set of case_types mapping"""
        expansion_to_case_types = defaultdict(set)
        for equivalence in self._all_possible_equivalences:
            expansion_to_case_types[equivalence.expansion].add(equivalence.case_type)
        return expansion_to_case_types


def _flatten_case_properties(case_properties_by_case_type):
    """Turn nested case_type => set of properties mapping into set of `_CasePropertyRef`s"""
    result = set()
    for case_type, properties in case_properties_by_case_type.items():
        for case_property in properties:
            case_property_parts = tuple(case_property.split('/'))
            result.add(_PropertyRef(
                case_type_ref=_CaseTypeRef(case_type, relationship_path=case_property_parts[:-1]),
                case_property=case_property_parts[-1]
            ))
    return result


def _propagate_and_normalize_case_properties(case_properties_by_case_type, parent_type_map,
                                             include_parent_properties):
    """
    Analyze and propagate all parent refs in `case_properties_by_case_type`

    and return something in the same format but with all parent refs propagated
    up (and if `include_parent_properties`, down) the chain

    A note about *implementation*. The approach used here is to first receive all possible
    case properties from all sources, but with inconsistent parent/<property> strewn about.
    (For example child may have parent/<foo> but parent does not have <foo>.)
    Then (in this method), the mapping of case types to property sets is flattened
    to a single set of `_CasePropertyRef`s, which represents each property
    (conceptually "parent/<property> relative to <case_type>")
    as a pair of
      - _CaseTypeRef ('parent' [or parent/parent, etc.] relative to <case_type>)
      - case property (the string)
    Finally, this set is copied over to a new set, but with each case_type_ref of each
    case_property_ref replaced with its most canonical form
    (or forms in the rare case that a case_type_ref resolves to more than one case_type,
    i.e. a child case has more than one case type that can be its parent).
    Additionally, if include_parent_properties is True, each canonical form is then splatted
    out into all of the other forms it can take: (child, 'parent/parent', property) becomes
    (parent, 'parent', property) and (grandparent, '', property) as well. (Note I'm using
    conceptual notation here, whereas in the code each of these is a `_CasePropertyRef`.)

    :param case_properties_by_case_type: {case_type: set(case_property)} mapping,
           where case_property is a string of the form "(parent/)*<case_property>"
    :param parent_type_map: {case_type: {relationship: [parent_type]}}
           note that for each relationship (almost always "parent"), there can be *multiple*
           possible parent_types
    :param include_parent_properties: If this is set to True, then propagate parents'
           properties down (as parent/<property>), in addition to propagating
           parent/<property> on the child up to <property> on the parent
           (which happens regardless of this flag). If set to True, all `parent/<property>`
           cases are also *removed* from the child, unless it cannot be determined what
           it refers to.

    :return: {case_type: set(case_property)} mapping (with the propagated properties)
    """
    case_relationship_manager = _CaseRelationshipManager(
        parent_type_map, case_types=list(case_properties_by_case_type.keys()))
    flattened_case_properties = _flatten_case_properties(case_properties_by_case_type)
    normalized_case_properties = set()
    for property_ref in flattened_case_properties:
        resolved_case_types = case_relationship_manager.resolve_expansion(property_ref.case_type_ref)
        if resolved_case_types:
            if include_parent_properties:
                normalized_case_properties.update(
                    _PropertyRef(expansion, property_ref.case_property)
                    for case_type in resolved_case_types
                    for expansion in case_relationship_manager.expand_case_type(case_type)
                )
            else:
                normalized_case_properties.update(
                    _PropertyRef(_CaseTypeRef(case_type, ()), property_ref.case_property)
                    for case_type in resolved_case_types
                )
        else:
            # if #case/parent doesn't match any known case type, leave the property_ref as is
            normalized_case_properties.add(property_ref)

    normalized_case_properties_by_case_type = defaultdict(set)
    for property_ref in normalized_case_properties:
        normalized_case_properties_by_case_type[property_ref.case_type_ref.case_type].add(
            '/'.join(property_ref.case_type_ref.relationship_path + (property_ref.case_property,)))
    return normalized_case_properties_by_case_type


class ParentCasePropertyBuilder(object):
    """
    Helper for detecting case relationships and case properties

    This class is not intended to be used directly, but rather through the functions below.
    todo: remove all usages outside of this package and replaces with function calls.

    Full functionality is documented in the individual methods.

    """
    def __init__(self, domain, apps, defaults=(), include_parent_properties=True,
                 exclude_invalid_properties=False, exclude_deprecated_properties=True):
        self.domain = domain
        self.apps = apps
        self.defaults = defaults
        self.include_parent_properties = include_parent_properties
        self.exclude_invalid_properties = exclude_invalid_properties
        self.exclude_deprecated_properties = exclude_deprecated_properties

    @classmethod
    def for_app(cls, app, defaults=(), include_parent_properties=True,
                exclude_invalid_properties=False):
        apps = [app]
        if app.case_sharing:
            apps.extend(get_case_sharing_apps_in_domain(app.domain, app.id))
        return cls(app.domain,
                   apps,
                   defaults=defaults,
                   include_parent_properties=include_parent_properties,
                   exclude_invalid_properties=exclude_invalid_properties)

    @classmethod
    def for_domain(cls, domain, include_parent_properties=True, exclude_deprecated_properties=True):
        apps = get_apps_in_domain(domain, include_remote=False)
        return cls(domain,
                   apps,
                   defaults=('name',),
                   include_parent_properties=include_parent_properties,
                   exclude_invalid_properties=False,
                   exclude_deprecated_properties=exclude_deprecated_properties)

    @memoized
    def _get_relevant_forms(self):
        forms = []
        for app in self.apps:
            forms.extend(_get_forms(app))
        return forms

    def _get_all_case_updates(self):
        all_case_updates = defaultdict(set)
        for form in self._get_relevant_forms():
            for case_type, case_properties in form.get_all_case_updates().items():
                all_case_updates[case_type].update(case_properties)
        return all_case_updates

    def get_case_relationships_for_case_type(self, case_type):
        """
        Like get_case_relationships, but filters down to a single case type

        :param case_type: case type to get relationships for
        :return: set of (parent_type, relationship) for this case. See get_case_relationships below.

        """
        return self.get_case_relationships()[case_type]

    @memoized
    def get_case_relationships(self):
        """
        Returns a `defaultdict(set)` of case_type => set of (parent_type, relationship)

        where relationship is almost always "parent" (but can technically be any word-string).

        This based on all case-subcase relationships appearing in all relevant forms.

        """
        case_relationships_by_child_type = defaultdict(set)

        for form in self._get_relevant_forms():
            for case_type, case_relationships in form.get_contributed_case_relationships().items():
                case_relationships_by_child_type[case_type].update(case_relationships)
        return case_relationships_by_child_type

    def get_parent_types(self, case_type):
        """
        Get a list of all possible parent types for a case type

        Unlike `get_case_relationships`, it doesn't include the `relationship`.
        That is because it is almost always "parent". Presumably, if this method is used
        without care, it will cause bugs in the rarer case when relationship is *not* "parent".
        # todo audit usage to see if such bugs can occur

        :param case_type: case type to get the parent types of
        :return: set of parent types (strings)

        """
        parent_types = self.get_case_relationships_for_case_type(case_type)
        return set(p[0] for p in parent_types)

    @memoized
    def get_properties(self, case_type):
        """
        Get all possible properties of case_type

        Has all of the same behavior as `get_properties_by_case_type` in terms of
        its abilities and limitations.

        :param case_type: case type to get properties for
        :return: set([<property>])

        """
        return self.get_properties_by_case_type()[case_type]

    @memoized
    def get_properties_by_case_type(self):
        """
        Get all possible properties for each case type

        Data sources for this are (limited to):
        - the app given
        - all other case sharing apps if app.case_sharing
        - the Data Dictionary case properties if domain has DATA_DICTIONARY privilege
        - the `defaults` passed in to the class
        - the `per_type_defaults` for usercases and call center cases, if applicable

        Notably, it propagates parent/<property> on a child up to the <property> on the parent,
        and, only if `include_parent_properties` was not passed in as False to the class,
        also propagates <property> on the parent down to parent/<property> on the child.
        This propagation is (conceptually) recursive, going all the way up (and down) the chain.
        (In actuality, the implementation is iterative,
        for ease of reasoning and pobably also efficiency.)

        :return: {<case_type>: set([<property>])} for all case types found
        """
        from corehq.apps.data_dictionary.util import get_data_dict_props_by_case_type
        case_properties_by_case_type = defaultdict(set)

        _zip_update(case_properties_by_case_type, self._get_all_case_updates())

        _zip_update(case_properties_by_case_type, get_per_type_defaults(self.domain))

        if domain_has_privilege(self.domain, privileges.DATA_DICTIONARY):
            _zip_update(case_properties_by_case_type,
                        get_data_dict_props_by_case_type(self.domain, self.exclude_deprecated_properties))

        for case_properties in case_properties_by_case_type.values():
            case_properties.update(self.defaults)

        if self.exclude_invalid_properties:
            from corehq.apps.app_manager.helpers.validators import validate_property
            for case_type, case_properties in case_properties_by_case_type.items():
                to_remove = []
                for prop in case_properties:
                    try:
                        validate_property(prop)
                    except ValueError:
                        to_remove.append(prop)
                for prop in to_remove:
                    case_properties_by_case_type[case_type].remove(prop)

        # this is where all the sweet, sweet child-parent property propagation happens
        return _propagate_and_normalize_case_properties(
            case_properties_by_case_type,
            parent_type_map=self.get_parent_type_map(case_types=None),
            include_parent_properties=self.include_parent_properties
        )

    def get_parent_type_map(self, case_types):
        """
        :param case_types: Case types to filter on. Setting to None will include all.
               todo: including all should be the default behavior since it isn't more work.
        :return: {<case_type>: {<relationship>: [<parent_type>], ...}, ...}
                 if allow_multiple_parents; otherwise
                 {<case_type>: {<relationship>: <parent_type>, ...}, ...}
                 and if there is more than one possible parent type, it arbitrarily picks one
                 and complains quietly with logger.error. Todo: this seems like bad behavior.

        """
        parent_map = defaultdict(dict)

        for case_type, case_relationships in self.get_case_relationships().items():
            rel_map = defaultdict(list)
            for parent_type, relationship in case_relationships:
                rel_map[relationship].append(parent_type)

            for relationship, types in rel_map.items():
                parent_map[case_type][relationship] = types

        if case_types is not None:
            return {case_type: rel_map for case_type, rel_map in parent_map.items()
                    if case_type in case_types}
        return parent_map

    def get_case_property_map(self, case_types):
        """
        Same data as self.get_properties_by_case_type, filtered and sorted.

        Include only `case_type`s mentioned in `case_types`,
        and put properties in a sorted list.

        :param case_types: case_types to filter on

        :return: {case_type: [property]}, with the property list sorted alphabetically.
        """
        case_types = sorted(case_types)
        return {
            case_type: sorted(self.get_properties(case_type))
            for case_type in case_types
        }


def get_parent_type_map(app):
    builder = ParentCasePropertyBuilder.for_app(app)
    return builder.get_parent_type_map(app.get_case_types())


def get_case_properties(app, case_types, defaults=(), include_parent_properties=True,
                        exclude_invalid_properties=False):
    builder = ParentCasePropertyBuilder.for_app(
        app,
        defaults=defaults,
        include_parent_properties=include_parent_properties,
        exclude_invalid_properties=exclude_invalid_properties
    )
    return builder.get_case_property_map(case_types)


@quickcache(vary_on=['app.get_id', 'exclude_invalid_properties'])
def get_all_case_properties(app, exclude_invalid_properties=True):
    return get_case_properties(
        app, app.get_case_types(), defaults=('name',), exclude_invalid_properties=exclude_invalid_properties
    )


def get_all_case_properties_for_case_type(domain, case_type, exclude_deprecated_properties=True):
    return all_case_properties_by_domain(
        domain, exclude_deprecated_properties=exclude_deprecated_properties).get(case_type, [])


@quickcache(vary_on=['app.get_id'])
def get_usercase_properties(app):
    if is_usercase_in_use(app.domain):
        # TODO: add name here once it is fixed to concatenate first and last in form builder
        default_properties = {'first_name', 'last_name', 'phone_number', 'username'}
        case_properties = get_case_properties(app, [USERCASE_TYPE])
        case_properties[USERCASE_TYPE] = list(set(case_properties[USERCASE_TYPE]) | default_properties)
        return case_properties
    return {USERCASE_TYPE: []}


@quickcache(vary_on=['domain', 'include_parent_properties', 'exclude_deprecated_properties'])
def all_case_properties_by_domain(domain, include_parent_properties=True, exclude_deprecated_properties=True):
    builder = ParentCasePropertyBuilder.for_domain(
        domain, include_parent_properties=include_parent_properties,
        exclude_deprecated_properties=exclude_deprecated_properties)
    return {
        case_type: sorted(properties)
        for case_type, properties in builder.get_properties_by_case_type().items()
    }


def get_per_type_defaults(domain):
    """Get default properties for callcenter and usercases"""
    from corehq.apps.callcenter.utils import get_call_center_case_type_if_enabled

    per_type_defaults = {}
    if is_usercase_in_use(domain):
        per_type_defaults = {
            USERCASE_TYPE: _get_usercase_default_properties(domain)
        }

    callcenter_case_type = get_call_center_case_type_if_enabled(domain)
    if callcenter_case_type:
        per_type_defaults[callcenter_case_type] = _get_usercase_default_properties(domain)

    return per_type_defaults


@quickcache(['domain'])
def _get_usercase_default_properties(domain):
    from corehq.apps.custom_data_fields.models import CustomDataFieldsDefinition
    from corehq.apps.users.views.mobile.custom_data_fields import CUSTOM_USER_DATA_FIELD_TYPE

    fields_def = CustomDataFieldsDefinition.get_or_create(domain, CUSTOM_USER_DATA_FIELD_TYPE)
    return [f.slug for f in fields_def.get_fields()]


def expire_case_properties_caches(domain):
    # expire all possible combinations of arguments
    all_case_properties_by_domain.clear(domain=domain,
                                        include_parent_properties=True, exclude_deprecated_properties=True)
    all_case_properties_by_domain.clear(domain=domain,
                                        include_parent_properties=True, exclude_deprecated_properties=False)
    all_case_properties_by_domain.clear(domain=domain,
                                        include_parent_properties=False, exclude_deprecated_properties=True)
    all_case_properties_by_domain.clear(domain=domain,
                                        include_parent_properties=False, exclude_deprecated_properties=False)
