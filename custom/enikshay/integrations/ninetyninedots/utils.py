from __future__ import absolute_import
import six
import uuid
from dateutil import parser
from pytz import timezone

from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from casexml.apps.case.const import CASE_INDEX_EXTENSION, UNOWNED_EXTENSION_OWNER_ID
from corehq.form_processor.exceptions import CaseNotFound
from dimagi.utils.decorators.memoized import memoized
from dimagi.utils.modules import to_function

from casexml.apps.case.mock import CaseFactory, CaseStructure, CaseIndex
from custom.enikshay.const import ENIKSHAY_TIMEZONE
from custom.enikshay.integrations.ninetyninedots.const import VALID_ADHERENCE_VALUES
from custom.enikshay.integrations.ninetyninedots.api_spec import load_api_spec, DIRECTION_INBOUND
from custom.enikshay.integrations.ninetyninedots.exceptions import NinetyNineDotsException
from custom.enikshay.case_utils import (
    CASE_TYPE_EPISODE,
    CASE_TYPE_OCCURRENCE,
    CASE_TYPE_PERSON,
    get_sector,
    get_all_episode_cases_from_person,
    get_occurrence_case_from_episode,
    get_adherence_cases_between_dates,
)
from custom.enikshay.exceptions import ENikshayCaseNotFound
from custom.enikshay.tasks import update_single_episode
from corehq.apps.hqcase.utils import bulk_update_cases


class BaseNinetyNineDotsUpdater(object):

    def __init__(self, domain):
        self.domain = domain
        self.case_accessor = CaseAccessors(domain)
        self.case_factory = CaseFactory(domain)

    @property
    def case_types_to_cases(self):
        return {
            CASE_TYPE_PERSON: self._person_case,
            CASE_TYPE_OCCURRENCE: self._occurrence_case,
            CASE_TYPE_EPISODE: self._episode_case,
        }

    @property
    @memoized
    def _person_case(self):
        try:
            return self.case_accessor.get_case(self.person_id)
        except CaseNotFound:
            raise NinetyNineDotsException("No patient exists with this beneficiary ID")

    @property
    @memoized
    def _occurrence_case(self):
        try:
            return get_occurrence_case_from_episode(self.domain, self._episode_case)

        except ENikshayCaseNotFound as e:
            raise NinetyNineDotsException(e)

    @property
    @memoized
    def _episode_case(self):
        try:
            episode_cases = get_all_episode_cases_from_person(self.domain, self._person_case.case_id)
        except ENikshayCaseNotFound as e:
            raise NinetyNineDotsException(e)

        if not episode_cases:
            raise NinetyNineDotsException("No episode cases found for {}".format(self._person_case.case_id))

        open_cases = [c for c in episode_cases if not c.closed]
        if open_cases:
            return sorted(open_cases, key=lambda c: c.opened_on)[0]

        return episode_cases[0]


class PatientDetailsUpdater(BaseNinetyNineDotsUpdater):
    def __init__(self, domain, request_json):
        super(PatientDetailsUpdater, self).__init__(domain)
        self.api_spec = load_api_spec()
        self.request_json = request_json
        self._validate_request()

    def _validate_request(self):
        self._validate_required_props()
        self._validate_beneficiary()
        self._validate_choices()

    def _validate_required_props(self):
        missing_required_properties = set(self.api_spec.required_params) - set(self.request_json.keys())
        if missing_required_properties:
            raise NinetyNineDotsException(
                "Missing {} which are required parameters.".format(", ".join(missing_required_properties))
            )

    def _validate_beneficiary(self):
        try:
            self.person_id = self.request_json.pop('beneficiary_id')
        except KeyError:
            raise NinetyNineDotsException("Missing beneficiary_id which is a required parameter.")
        self._person_case       # ensure person case before doing more work

    def _validate_choices(self):
        sector = get_sector(self._person_case)
        for param_name, value in six.iteritems(self.request_json):
            try:
                choices = self.api_spec.get_param(param_name, sector).get_by_sector('choices', sector)
            except KeyError:
                raise NinetyNineDotsException("{} is not a valid parameter to update".format(param_name))
            if choices and value not in choices:
                raise NinetyNineDotsException(
                    "{} is not a valid value for {}.".format(value, param_name)
                )

    def update_cases(self):
        sector = get_sector(self._person_case)
        case_updates = []
        for prop, value in six.iteritems(self.request_json):
            try:
                param = self.api_spec.get_param(prop, sector)
            except KeyError:
                raise NinetyNineDotsException("{} is not a valid parameter to update".format(prop))

            if not param.direction & DIRECTION_INBOUND:
                raise NinetyNineDotsException("{} is not a valid parameter to update".format(prop))

            case_type = param.get_by_sector('case_type', sector)
            case_id = self.case_types_to_cases[case_type].case_id

            if param.setter:
                update = to_function(param.setter)(param, value, sector)
            else:
                update = {param.get_by_sector('case_property', sector): value}
            case_updates.append((case_id, update, False))

        return bulk_update_cases(
            self.domain,
            case_updates,
            "{}.{}".format(self.__module__, self.__class__.__name__),
        )


class AdherenceCaseFactory(BaseNinetyNineDotsUpdater):
    """
    Creates and updates adherence cases for a given person

    Only for use by the 99DOTS integration with eNikshay
    """
    DEFAULT_ADHERENCE_CONFIDENCE = "medium"
    ADHERENCE_CASE_TYPE = "adherence"
    DEFAULT_ADHERENCE_VALUE = "unobserved_dose"

    def __init__(self, domain, person_id):
        super(AdherenceCaseFactory, self).__init__(domain)
        self.person_id = person_id

    @property
    @memoized
    def _default_adherence_confidence(self):
        return self._episode_case.dynamic_case_properties().get(
            'default_adherence_confidence', self.DEFAULT_ADHERENCE_CONFIDENCE
        )

    def create_adherence_cases(self, adherence_points):
        case_structures = []
        for adherence_point in adherence_points:
            if adherence_point.get('MERM_TypeOfEvent') == "HEARTBEAT":
                continue
            case_structures.append(
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
            )
        return self.case_factory.create_or_update_cases(case_structures)

    def _get_adherence_case_properties(self, adherence_point):
        return {
            "name": adherence_point.get("timestamp", None),
            "adherence_value": self._parse_adherence_value(adherence_point),
            "adherence_source": adherence_point.get('adherenceSource', '99DOTS'),
            "adherence_date": self._parse_adherence_date(adherence_point["timestamp"]),
            "person_name": self._person_case.name,
            "adherence_confidence": self._default_adherence_confidence,
            "shared_number_99_dots": adherence_point.get("sharedNumber"),
            "merm_imei": adherence_point.get("MERM_IMEI"),
            "merm_extra_info": adherence_point.get("MERM_ExtraInformation"),
        }

    def _parse_adherence_date(self, iso_datestring):
        tz = timezone(ENIKSHAY_TIMEZONE)
        try:
            datetime_from_adherence = parser.parse(iso_datestring)
            datetime_in_india = datetime_from_adherence.astimezone(tz)
        except ValueError:
            raise NinetyNineDotsException(
                "Adherence date should be an ISO8601 formated string with timezone information."
            )
        return datetime_in_india.date()

    def _parse_adherence_value(self, adherence_point):
        value = adherence_point.get('adherenceValue', self.DEFAULT_ADHERENCE_VALUE)
        if value not in VALID_ADHERENCE_VALUES:
            raise NinetyNineDotsException(
                "adherenceValue must be one of {}".format(", ".join(VALID_ADHERENCE_VALUES))
            )
        return value

    def update_adherence_cases(self, start_date, end_date, confidence_level):
        try:
            adherence_cases = get_adherence_cases_between_dates(self.domain, self.person_id, start_date, end_date)
        except ENikshayCaseNotFound as e:
            raise NinetyNineDotsException(six.text_type(e))
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

    def update_episode_adherence_properties(self):
        # update episode 10 minutes later to give the adherence datasource time to catch up
        update_single_episode.apply_async(args=[self.domain, self._episode_case], countdown=600)


def create_adherence_cases(domain, person_id, adherence_points):
    return AdherenceCaseFactory(domain, person_id).create_adherence_cases(adherence_points)


def update_adherence_confidence_level(domain, person_id, start_date, end_date, new_confidence):
    return AdherenceCaseFactory(domain, person_id).update_adherence_cases(start_date, end_date, new_confidence)


def update_default_confidence_level(domain, person_id, new_confidence):
    return AdherenceCaseFactory(domain, person_id).update_default_confidence_level(new_confidence)
