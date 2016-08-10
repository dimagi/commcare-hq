import uuid
from datetime import datetime

from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from casexml.apps.case.const import CASE_INDEX_EXTENSION
from corehq.form_processor.exceptions import CaseNotFound
from dimagi.utils.decorators.memoized import memoized

from casexml.apps.case.mock import CaseFactory, CaseStructure, CaseIndex
from custom.enikshay.integrations.ninetyninedots.exceptions import AdherenceException


class AdherenceCaseFactory(object):
    """
    Creates new adherence cases for a given person

    Only for use by the 99DOTS integration with eNikshay
    """
    DEFAULT_ADHERENCE_CONFIDENCE = "medium"
    ADHERENCE_CASE_TYPE = "adherence"
    DEFAULT_ADHERENCE_VALUE = "unobserved_dose"

    def __init__(self, domain, person_id, adherence_points, adherence_source):
        self.domain = domain
        self.person_id = person_id
        self.adherence_points = adherence_points
        self.adherence_source = adherence_source

        self.case_accessor = CaseAccessors(domain)
        self.case_factory = CaseFactory(domain)

    @property
    @memoized
    def _person_case(self):
        try:
            return self.case_accessor.get_case(self.person_id)
        except CaseNotFound:
            raise AdherenceException(message="No patient exists with this beneficiary ID")

    @property
    @memoized
    def _default_adherence_confidence(self):
        return self._person_case.dynamic_case_properties().get(
            'default_adherence_confidence', self.DEFAULT_ADHERENCE_CONFIDENCE
        )

    @property
    @memoized
    def _episode_case(self):
        try:
            return get_open_episode_case(self.domain, self._person_case.case_id)
        except CaseNotFound:
            raise AdherenceException(message="No patient exists with this beneficiary ID")

    def create_adherence_cases(self):
        return self.case_factory.create_or_update_cases([
            CaseStructure(
                case_id=uuid.uuid4().hex,
                attrs={
                    "case_type": self.ADHERENCE_CASE_TYPE,
                    "create": True,
                    "update": self._get_adherence_case_properties(adherence_point),
                },
                indices=[CaseIndex(
                    CaseStructure(case_id=self._episode_case.case_id, attrs={"create": False}),
                    identifier='host',
                    relationship=CASE_INDEX_EXTENSION,
                    related_type=self._episode_case.type,
                )],
            )
            for adherence_point in self.adherence_points
        ])

    def _get_adherence_case_properties(self, adherence_point):
        return {
            "name": datetime.utcnow(),
            "adherence_value": self.DEFAULT_ADHERENCE_VALUE,
            "adherence_source": self.adherence_source,
            "adherence_date": adherence_point["timestamp"],
            "person_name": self._person_case.name,
            "dots99_adherence_confidence": self._default_adherence_confidence,
            "dots99_shared_number": adherence_point["sharedNumber"],
        }


def create_adherence_cases(domain, person_id, adherence_points, adherence_source="99DOTS"):
    return AdherenceCaseFactory(domain, person_id, adherence_points, adherence_source).create_adherence_cases()


def get_open_episode_case(domain, person_case_id):
    """
    Gets the first open 'episode' case for the person

    Assumes the following case structure:
    Person <--ext-- Occurrence <--ext-- Episode

    """
    case_accessor = CaseAccessors(domain)
    occurrence_cases = case_accessor.get_reverse_indexed_cases([person_case_id])
    open_occurrence_cases = [case for case in occurrence_cases
                             if not case.closed and case.type == "occurrence"]
    if not open_occurrence_cases:
        raise CaseNotFound
    occurence_case = open_occurrence_cases[0]
    episode_cases = case_accessor.get_reverse_indexed_cases([occurence_case.case_id])
    open_episode_cases = [case for case in episode_cases
                          if not case.closed and case.type == "episode" and
                          case.dynamic_case_properties().get('episode_type') == "confirmed_tb"]
    if open_episode_cases:
        return open_episode_cases[0]
    else:
        raise CaseNotFound
