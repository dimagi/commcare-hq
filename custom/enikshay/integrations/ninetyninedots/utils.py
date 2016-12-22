import uuid
from dateutil import parser
from pytz import timezone

from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from casexml.apps.case.const import CASE_INDEX_EXTENSION, UNOWNED_EXTENSION_OWNER_ID
from corehq.form_processor.exceptions import CaseNotFound
from dimagi.utils.decorators.memoized import memoized

from casexml.apps.case.mock import CaseFactory, CaseStructure, CaseIndex
from custom.enikshay.integrations.ninetyninedots.exceptions import AdherenceException
from custom.enikshay.case_utils import get_open_episode_case_from_person, get_adherence_cases_between_dates
from custom.enikshay.exceptions import ENikshayCaseNotFound


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
            raise AdherenceException("No patient exists with this beneficiary ID")

    @property
    @memoized
    def _default_adherence_confidence(self):
        return self._episode_case.dynamic_case_properties().get(
            'default_adherence_confidence', self.DEFAULT_ADHERENCE_CONFIDENCE
        )

    @property
    @memoized
    def _episode_case(self):
        try:
            return get_open_episode_case_from_person(self.domain, self._person_case.case_id)
        except ENikshayCaseNotFound as e:
            raise AdherenceException(e.message)

    def create_adherence_cases(self, adherence_points):
        return self.case_factory.create_or_update_cases([
            CaseStructure(
                case_id=uuid.uuid4().hex,
                attrs={
                    "case_type": self.ADHERENCE_CASE_TYPE,
                    "owner_id": UNOWNED_EXTENSION_OWNER_ID,
                    "create": True,
                    "update": self._get_adherence_case_properties(adherence_point),
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

    def _get_adherence_case_properties(self, adherence_point):
        return {
            "name": adherence_point.get("timestamp", None),
            "adherence_value": self.DEFAULT_ADHERENCE_VALUE,
            "adherence_source": adherence_point.get('adherenceSource', '99DOTS'),
            "adherence_date": self._parse_adherence_date(adherence_point["timestamp"]),
            "person_name": self._person_case.name,
            "adherence_confidence": self._default_adherence_confidence,
            "shared_number_99_dots": adherence_point["sharedNumber"],
        }

    def _parse_adherence_date(self, iso_datestring):
        tz = timezone('Asia/Kolkata')
        try:
            datetime_from_adherence = parser.parse(iso_datestring)
            datetime_in_india = datetime_from_adherence.astimezone(tz)
        except ValueError:
            raise AdherenceException(
                "Adherence date should be an ISO8601 formated string with timezone information."
            )
        return datetime_in_india.date()

    def update_adherence_cases(self, start_date, end_date, confidence_level):
        try:
            adherence_cases = get_adherence_cases_between_dates(self.domain, self.person_id, start_date, end_date)
        except ENikshayCaseNotFound as e:
            raise AdherenceException(e.message)
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


def create_adherence_cases(domain, person_id, adherence_points):
    return AdherenceCaseFactory(domain, person_id).create_adherence_cases(adherence_points)


def update_adherence_confidence_level(domain, person_id, start_date, end_date, new_confidence):
    return AdherenceCaseFactory(domain, person_id).update_adherence_cases(start_date, end_date, new_confidence)


def update_default_confidence_level(domain, person_id, new_confidence):
    return AdherenceCaseFactory(domain, person_id).update_default_confidence_level(new_confidence)
