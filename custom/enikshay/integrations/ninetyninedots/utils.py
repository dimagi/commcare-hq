import uuid
import pytz
from django.utils.dateparse import parse_datetime

from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from casexml.apps.case.const import CASE_INDEX_EXTENSION, UNOWNED_EXTENSION_OWNER_ID
from corehq.form_processor.exceptions import CaseNotFound
from dimagi.utils.decorators.memoized import memoized

from casexml.apps.case.mock import CaseFactory, CaseStructure, CaseIndex
from custom.enikshay.integrations.ninetyninedots.exceptions import AdherenceException


class AdherenceCaseFactory(object):
    """
    Creates and updates adherence cases for a given person

    Only for use by the 99DOTS integration with eNikshay
    """
    DEFAULT_ADHERENCE_CONFIDENCE = "medium"
    ADHERENCE_CASE_TYPE = "adherence"
    DEFAULT_ADHERENCE_VALUE = "unobserved_dose"

    def __init__(self, domain, person_id):
        self.domain = domain
        self.person_id = person_id

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
        return self._episode_case.dynamic_case_properties().get(
            'default_adherence_confidence', self.DEFAULT_ADHERENCE_CONFIDENCE
        )

    @property
    @memoized
    def _episode_case(self):
        return get_open_episode_case(self.domain, self._person_case.case_id)

    def create_adherence_cases(self, adherence_points, adherence_source):
        return self.case_factory.create_or_update_cases([
            CaseStructure(
                case_id=uuid.uuid4().hex,
                attrs={
                    "case_type": self.ADHERENCE_CASE_TYPE,
                    "owner_id": UNOWNED_EXTENSION_OWNER_ID,
                    "create": True,
                    "update": self._get_adherence_case_properties(adherence_point, adherence_source),
                },
                indices=[CaseIndex(
                    CaseStructure(case_id=self._episode_case.case_id, attrs={"create": False}),
                    identifier='host',
                    relationship=CASE_INDEX_EXTENSION,
                    related_type=self._episode_case.type,
                )],
                walk_related=False,
            )
            for adherence_point in adherence_points
        ])

    def _get_adherence_case_properties(self, adherence_point, adherence_source):
        return {
            "name": adherence_point["timestamp"],
            "adherence_value": self.DEFAULT_ADHERENCE_VALUE,
            "adherence_source": adherence_source,
            "adherence_date": adherence_point["timestamp"],
            "person_name": self._person_case.name,
            "adherence_confidence": self._default_adherence_confidence,
            "shared_number_99_dots": adherence_point["sharedNumber"],
        }

    def update_adherence_cases(self, start_date, end_date, confidence_level):
        adherence_cases = get_adherence_cases_between_dates(self.domain, self.person_id, start_date, end_date)
        adherence_case_ids = [case.case_id for case in adherence_cases]
        return self.case_factory.create_or_update_cases([
            CaseStructure(
                case_id=adherence_case_id,
                attrs={
                    "create": False,
                    "update": {
                        "adherence_confidence": confidence_level
                    },
                },
                walk_related=False
            ) for adherence_case_id in adherence_case_ids
        ])

    def update_default_confidence_level(self, confidence_level):
        return self.case_factory.create_or_update_cases([
            CaseStructure(
                case_id=self._episode_case.case_id,
                attrs={
                    "create": False,
                    "update": {
                        "default_adherence_confidence": confidence_level
                    },
                },
                walk_related=False
            )
        ])


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
        raise AdherenceException(
            message="Person with id: {} exists but has no open occurence cases".format(person_case_id)
        )
    occurence_case = open_occurrence_cases[0]
    episode_cases = case_accessor.get_reverse_indexed_cases([occurence_case.case_id])
    open_episode_cases = [case for case in episode_cases
                          if not case.closed and case.type == "episode" and
                          case.dynamic_case_properties().get('episode_type') == "confirmed_tb"]
    if open_episode_cases:
        return open_episode_cases[0]
    else:
        raise AdherenceException(
            message="Person with id: {} exists but has no open episode cases".format(person_case_id)
        )


def get_adherence_cases_between_dates(domain, person_case_id, start_date, end_date):
    case_accessor = CaseAccessors(domain)
    episode = get_open_episode_case(domain, person_case_id)
    indexed_cases = case_accessor.get_reverse_indexed_cases([episode.case_id])
    open_pertinent_adherence_cases = [
        case for case in indexed_cases
        if not case.closed and case.type == "adherence" and
        (start_date.astimezone(pytz.UTC) <=
         parse_datetime(case.dynamic_case_properties().get('adherence_date')).astimezone(pytz.UTC) <=
         end_date.astimezone(pytz.UTC))
    ]

    return open_pertinent_adherence_cases


def create_adherence_cases(domain, person_id, adherence_points, adherence_source="99DOTS"):
    return AdherenceCaseFactory(domain, person_id).create_adherence_cases(adherence_points, adherence_source)


def update_adherence_confidence_level(domain, person_id, start_date, end_date, new_confidence):
    return AdherenceCaseFactory(domain, person_id).update_adherence_cases(start_date, end_date, new_confidence)


def update_default_confidence_level(domain, person_id, new_confidence):
    return AdherenceCaseFactory(domain, person_id).update_default_confidence_level(new_confidence)
