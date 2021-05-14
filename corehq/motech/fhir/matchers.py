from collections import namedtuple
from decimal import Decimal
from typing import Iterable, List, Optional, Type

import attr

from corehq.motech.finders import le_days_diff, le_levenshtein_percent
from jsonpath_ng.ext.parser import parse as jsonpath_parse

from corehq.motech.utils import simplify_list

CandidateScore = namedtuple('CandidateScore', 'candidate score')


class DuplicateWarning(Warning):
    pass


class ResourceMatcher:
    """
    Finds matching FHIR resources.

    The properties of resources are compared. Each matching property has
    a weight. The sum of the weights give a score. If the score is
    greater than 1, the resources are considered a match.

    If more than one candidate matches, but one has a significantly
    higher score than the rest, it is the match. Otherwise a
    ``DuplicateWarning`` exception is raised.
    """

    property_weights: List['PropertyWeight']
    confidence_margin = 0.5

    def __init__(self, resource: dict):
        self.resource = resource

    def find_match(self, candidates: Iterable[dict]):
        matches = self.find_matches(candidates, keep_dups=False)
        match = simplify_list(matches)
        if isinstance(match, list):
            raise DuplicateWarning('Duplicate matches found for resource '
                                   f'{self.resource}')
        return match

    def find_matches(self, candidates: Iterable[dict], *, keep_dups=True):
        """
        Returns a list of matches.

        If ``keep_dups`` is False, allows for an arbitrary number of
        candidates but only returns the best two, or fewer.
        """

        def top_two(list_):
            return sorted(list_, key=lambda l: l.score, reverse=True)[:2]

        candidates_scores = []
        for candidate in candidates:
            score = self.get_score(candidate)
            if score >= 1:
                candidates_scores.append(CandidateScore(candidate, score))
            if not keep_dups:
                candidates_scores = top_two(candidates_scores)

        if len(candidates_scores) > 1:
            best, second = top_two(candidates_scores)
            if best.score / second.score >= 1 + self.confidence_margin:
                return [best.candidate]
        return [cs.candidate for cs in candidates_scores]

    def get_score(self, candidate):
        return sum(self.iter_weights(candidate))

    def iter_weights(self, candidate):
        for pw in self.property_weights:
            is_match = pw.method.is_match(self.resource, candidate)
            if is_match is None:
                # method was unable to compare values
                continue
            yield pw.weight if is_match else -1 * pw.negative_weight


class ComparisonMethod:
    """
    A method of comparing resource properties.
    """

    def __init__(self, jsonpath: str):
        self.jsonpath = jsonpath_parse(jsonpath)

    def is_match(self, resource: dict, candidate: dict) -> Optional[bool]:
        a = simplify_list([x.value for x in self.jsonpath.find(resource)])
        b = simplify_list([x.value for x in self.jsonpath.find(candidate)])
        if a is None or b is None:
            return None
        return self.compare(a, b)

    @staticmethod
    def compare(a, b) -> bool:
        raise NotImplementedError


class IsEqual(ComparisonMethod):

    @staticmethod
    def compare(a, b):
        return a == b


class GivenName(ComparisonMethod):

    @staticmethod
    def compare(a, b):
        return any(a_name == b_name for a_name, b_name in zip(a, b))


class AnyGivenName(ComparisonMethod):
    """
    This ComparisonMethod might be better suited to negative weights
    because the chances of false positives are high.

    e.g.

    >>> AnyGivenName.compare(['H.', 'John'], ['Santa', 'H.'])
    True

    """

    @staticmethod
    def compare(a, b):
        return bool(set(a) & set(b))


class Age(ComparisonMethod):

    @staticmethod
    def compare(a, b):
        max_days = 364
        return le_days_diff(max_days, a, b)


class OrganizationName(ComparisonMethod):

    @staticmethod
    def compare(a, b):
        percent = 0.2
        return le_levenshtein_percent(percent, a.lower(), b.lower())


class NegativeIdentifier(ComparisonMethod):
    """
    Returns False if the identifier system is the same, and the
    identifier value is not close.

    Used for giving a negative score to candidates with different IDs
    from the same system.
    """

    @staticmethod
    def compare(a, b):
        system_a, value_a = a.split('|')
        system_b, value_b = b.split('|')
        return not (
            system_a == system_b
            and not le_levenshtein_percent(0.2, value_a, value_b)
        )


def _value_ge_zero(instance, attrib, value):
    return value >= 0


@attr.s
class PropertyWeight:
    """
    Associates a matching property with a weight
    """
    jsonpath = attr.ib(type=str)
    weight = attr.ib(type=Decimal, validator=_value_ge_zero)
    method_class = attr.ib(type=Type[ComparisonMethod], default=IsEqual)
    # Score negatively if values are different
    negative_weight = attr.ib(type=Decimal,
                              default=Decimal('0'),
                              validator=_value_ge_zero)

    @property
    def method(self):
        return self.method_class(self.jsonpath)


class PersonMatcher(ResourceMatcher):
    """
    Finds matching FHIR Persons
    """
    property_weights = [
        PropertyWeight(
            '$.identifier[0].system + "|" + $.identifier[0].value',
            Decimal('0.8'),
        ),
        PropertyWeight(
            '$.identifier[0].system + "|" + $.identifier[0].value',
            Decimal('0'),
            NegativeIdentifier,
            negative_weight=Decimal('1.1'),
        ),
        PropertyWeight('$.name[0].given', Decimal('0.3'), GivenName),
        PropertyWeight(
            '$.name[0].given',
            Decimal('0'),
            AnyGivenName,
            negative_weight=Decimal('0.3'),
        ),
        PropertyWeight('$.name[0].family', Decimal('0.4')),
        PropertyWeight('$.telecom[0].value', Decimal('0.4')),
        PropertyWeight(
            '$.gender',
            Decimal('0.05'),
            negative_weight=Decimal('0.6')
        ),
        PropertyWeight('$.birthDate', Decimal('0.1')),
        PropertyWeight(
            '$.birthDate',
            Decimal('0.05'),
            Age,
            negative_weight=Decimal('0.2')
        ),
    ]


class PatientMatcher(ResourceMatcher):
    """
    Finds matching FHIR Patients
    """
    property_weights = PersonMatcher.property_weights + [
        PropertyWeight('$.multipleBirthInteger', Decimal('0.1'))
    ]


class OrganizationMatcher(ResourceMatcher):
    property_weights = [
        PropertyWeight('$.name', Decimal('0.8'), OrganizationName),
        PropertyWeight('$.telecom[0].value', Decimal('0.4')),
    ]
