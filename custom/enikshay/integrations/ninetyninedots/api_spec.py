from __future__ import absolute_import

import os

import jsonobject
import phonenumbers
import yaml

from corehq.apps.locations.models import SQLLocation
from custom.enikshay.case_utils import (
    CASE_TYPE_EPISODE,
    CASE_TYPE_OCCURRENCE,
    CASE_TYPE_PERSON,
    get_person_locations,
)
from custom.enikshay.const import (
    ENROLLED_IN_PRIVATE,
    PRIVATE_SECTOR,
    PUBLIC_SECTOR,
    SECTORS,
)
from custom.enikshay.integrations.ninetyninedots.const import (
    MERM_DAILY_REMINDER_STATUS,
    MERM_DAILY_REMINDER_TIME,
    MERM_ID,
    MERM_REFILL_REMINDER_DATE,
    MERM_REFILL_REMINDER_STATUS,
    MERM_REFILL_REMINDER_TIME,
    MERM_RT_HOURS,
)
from custom.enikshay.integrations.ninetyninedots.exceptions import \
    NinetyNineDotsException
from dimagi.ext.jsonobject import StrictJsonObject
from dimagi.utils.decorators.memoized import memoized
from dimagi.utils.modules import to_function

DIRECTION_OUTBOUND = 1
DIRECTION_INBOUND = 2
DIRECTION_BOTH = DIRECTION_INBOUND + DIRECTION_OUTBOUND


class DotsApiSectorParam(StrictJsonObject):
    public = jsonobject.StringProperty()
    private = jsonobject.StringProperty()
    both = jsonobject.StringProperty()

    def __init__(self, *args, **kwargs):
        try:
            _obj = args[0]
        except IndexError:
            _obj = {}
        _obj.update(kwargs)

        if _obj:
            if "both" in _obj and ("public" in _obj or "private" in _obj):
                raise ValueError("Can't define 'public' or 'private' options with 'both'")

        return super(DotsApiSectorParam, self).__init__(*args, **kwargs)


class DotsApiParamChoices(DotsApiSectorParam):
    public = jsonobject.ListProperty()
    private = jsonobject.ListProperty()
    both = jsonobject.ListProperty()


class DotsApiParam(StrictJsonObject):
    """99DOTS <-> eNikshay API Parameter Definition

    This class defines api parameters for the patient details API between
    99DOTS and eNikshay.

    For incoming api requests from 99DOTS, it defines where and how to save
    parameters.

    For outgoing api requests to 99DOTS, it defines which properties to watch
    for changes to and how they are compiled.

    """

    # the parameter name for the json sent and received
    api_param_name = jsonobject.StringProperty(required=True)

    # whether this parameter is required when receiving and API request
    required_ = jsonobject.BooleanProperty(default=False, name='required')
    exclude_if_none = jsonobject.BooleanProperty(default=True)
    choices = jsonobject.ObjectProperty(DotsApiParamChoices)

    # the case type to save or get this property from
    case_type = jsonobject.ObjectProperty(DotsApiSectorParam)
    # the case property to save to or get
    case_property = jsonobject.ObjectProperty(DotsApiSectorParam)

    # path to a function to get the value of this property
    getter = jsonobject.StringProperty()

    # path to a jsonObject that will wrap the value from the getter
    payload_object = jsonobject.StringProperty()

    # if using a custom getter, the case properties to watch for changes to send outwards
    case_properties = jsonobject.ObjectProperty(DotsApiParamChoices)

    # path to a function to set the case property for incoming requests. Should
    # return a dict of case properties to update
    setter = jsonobject.StringProperty()

    # whether we should send, receive, or both.
    direction = jsonobject.IntegerProperty(default=DIRECTION_BOTH,
                                           choices=[DIRECTION_INBOUND, DIRECTION_OUTBOUND, DIRECTION_BOTH])

    # path to a function that takes a sector parameter and returns a validator function
    # see checkbox_validator in this file for an example
    validator = jsonobject.StringProperty()
    # values passed into the validator function
    validator_values = jsonobject.ObjectProperty(DotsApiParamChoices)

    def get_by_sector(self, prop, sector):
        prop = getattr(self, prop)
        if isinstance(prop, DotsApiSectorParam):
            return getattr(prop, sector) or prop.both
        else:
            return prop


class DotsApiParams(StrictJsonObject):
    api_params = jsonobject.ListProperty(DotsApiParam)

    def get_param(self, param, sector):
        try:
            return next(
                p for p in self.api_params
                if p.api_param_name == param
                and (getattr(p.case_properties, sector) or getattr(p.case_properties, 'both')
                     or getattr(p.case_property, sector) or getattr(p.case_property, 'both'))
            )
        except StopIteration:
            raise KeyError("{} not in spec".format(param))

    @property
    def required_params(self):
        return [param.api_param_name for param in self.api_params if param.required_]

    def params_with_choices(self, sector):
        return [param.api_param_name for param in self.api_params if param.get_by_sector('choices', sector)]

    def params_by_case_type(self, sector, case_type):
        return [param for param in self.api_params
                if param.get_by_sector('case_type', sector) == case_type]

    def case_properties_by_case_type(self, sector, case_type, direction=DIRECTION_BOTH):
        params = self.params_by_case_type(sector, case_type)
        case_properties = []
        for param in params:
            if param.direction & direction:
                if param.get_by_sector("case_property", sector):
                    case_properties.append(param.get_by_sector("case_property", sector))
                if param.get_by_sector("case_properties", sector):
                    case_properties += param.get_by_sector("case_properties", sector)
        return case_properties


@memoized
def load_api_spec(filepath=None):
    """Loads API spec from api_properties.yaml and validates that the spec is correct
    """
    if filepath is None:
        filepath = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'api_properties.yaml')
    with open(filepath, 'r') as f:
        spec = DotsApiParams(yaml.load(f))
    return spec


class BasePatientPayload(StrictJsonObject):
    """The payload to send to 99DOTS

    The final payload class is generated programatically from the api_properties.yaml file.

    Location properties are included in the base classes as these cannot
    efficiently be expressed in the yaml definition.

    """
    sector = jsonobject.StringProperty(required=True)
    state_code = jsonobject.StringProperty(required=False)
    district_code = jsonobject.StringProperty(required=False)
    tu_code = jsonobject.StringProperty(required=False)

    @classmethod
    def create(cls, person_case, occurrence_case, episode_case):
        payload_kwargs = {
            "sector": cls._sector,
        }
        api_spec = load_api_spec()
        cases = {
            CASE_TYPE_EPISODE: episode_case,
            CASE_TYPE_OCCURRENCE: occurrence_case,
            CASE_TYPE_PERSON: person_case
        }
        for case_type in cases:
            case = cases[case_type]
            for spec_property in api_spec.params_by_case_type(cls._sector, case_type):
                if spec_property.getter:
                    prop = to_function(spec_property.getter)(
                        case.dynamic_case_properties(),
                        spec_property.get_by_sector('case_properties', cls._sector)
                    )
                else:
                    prop = case.get_case_property(spec_property.get_by_sector('case_property', cls._sector))
                payload_kwargs[spec_property.api_param_name] = prop or None

        payload_kwargs.update(cls.get_locations(person_case, episode_case))
        return cls(payload_kwargs)


def concat_properties(episode_case_properties, case_properties):
    return " ".join(episode_case_properties.get(prop, '') for prop in case_properties)


def split_name(param, val, sector):
    case_properties = param.get_by_sector("case_properties", sector)
    vals = val.split(" ", len(case_properties) - 1)
    output = {}
    for i, val in enumerate(vals):
        output[case_properties[i]] = val
    return output


def concat_phone_numbers(case_properties, case_properties_to_check):
    numbers = []
    for potential_number in case_properties_to_check:
        number = _parse_number(case_properties.get(potential_number))
        if number:
            numbers.append(_format_number(number))
    return ", ".join(numbers) if numbers else None


def unwrap_phone_number(param, val, sector):
    number = _format_number(_parse_number(val))
    case_properties = param.get_by_sector('case_properties', sector)
    return {p: number.replace("+", "") for p in case_properties}


def _parse_number(number):
    if number:
        phone_number = phonenumbers.parse(number, "IN")
        phone_number.italian_leading_zero = False
        return phone_number


def _format_number(phonenumber):
    if phonenumber:
        return phonenumbers.format_number(
            phonenumber,
            phonenumbers.PhoneNumberFormat.INTERNATIONAL
        ).replace(" ", "")


def noop(*args, **kwargs):
    return None


def location_name_getter(case_properties, props_to_check):
    if len(props_to_check) > 1:
        raise AttributeError("This getter only accepts a single case property")
    try:
        location = SQLLocation.active_objects.get(location_id=case_properties.get(props_to_check[0]))
        return location.name
    except SQLLocation.DoesNotExist:
        return None


def checkbox_validator(sector, validator_values):
    """Ensure that multiple answers to checkbox questions are all valid
    """

    def sector_validator(value):
        valid_values = getattr(validator_values, sector) + validator_values.both
        for individual_value in value.split(" "):
            if individual_value not in valid_values:
                raise ValueError('Error while parsing "{}". "{}" not in {}'.format(
                    value, individual_value, ", ".join(valid_values))
                )
        return True

    return sector_validator


class MermParams(StrictJsonObject):
    IMEI = jsonobject.StringProperty(required=False, exclude_if_none=True)
    daily_reminder_status = jsonobject.StringProperty(required=False, exclude_if_none=True)
    daily_reminder_time = jsonobject.StringProperty(required=False, exclude_if_none=True)  # HH:mm
    refill_reminder_status = jsonobject.StringProperty(required=False, exclude_if_none=True)
    refill_reminder_datetime = jsonobject.StringProperty(
        required=False,
        exclude_if_none=True
    )  # yy/MM/dd HH:mm:ss
    RT_hours = jsonobject.StringProperty(
        required=False,
        exclude_if_none=True
    )  # 1 = 12 hours; i.e. for 3 days - RT_hours = 6


def get_merm_params(episode_case_properties, properties_to_check):
    if not episode_case_properties.get(MERM_ID):
        return {}

    refill_reminder_date = episode_case_properties.get(MERM_REFILL_REMINDER_DATE, None)
    refill_reminder_time = episode_case_properties.get(MERM_REFILL_REMINDER_TIME, None)
    if refill_reminder_time and refill_reminder_date:
        refill_reminder_datetime = "{}T{}".format(refill_reminder_date, refill_reminder_time)
    else:
        refill_reminder_datetime = None

    params = MermParams({
        "IMEI": episode_case_properties.get(MERM_ID, None),
        "daily_reminder_status": episode_case_properties.get(MERM_DAILY_REMINDER_STATUS, None),
        "daily_reminder_time": episode_case_properties.get(MERM_DAILY_REMINDER_TIME, None),
        "refill_reminder_status": episode_case_properties.get(MERM_REFILL_REMINDER_STATUS, None),
        "refill_reminder_datetime": refill_reminder_datetime,
        "RT_hours": episode_case_properties.get(MERM_RT_HOURS, None),
    })
    return params.to_json()


def set_merm_params(param, val, sector):
    try:
        params = MermParams(val)
    except AttributeError as e:
        raise NinetyNineDotsException("Invalid MERM params sent. Full error was: {}".format(e))
    return {
        MERM_ID: params.IMEI,
        MERM_DAILY_REMINDER_STATUS: params.daily_reminder_status,
        MERM_DAILY_REMINDER_TIME: params.daily_reminder_time,
        MERM_REFILL_REMINDER_STATUS: params.refill_reminder_datetime,
        MERM_RT_HOURS: params.RT_hours,
    }


class BasePublicPatientPayload(BasePatientPayload):
    _sector = PUBLIC_SECTOR
    phi_code = jsonobject.StringProperty(required=False, exclude_if_none=True)

    @staticmethod
    def get_locations(person_case, episode_case):
        person_locations = get_person_locations(person_case, episode_case)
        return {
            "state_code": person_locations.sto,
            "district_code": person_locations.dto,
            "tu_code": person_locations.tu,
            "phi_code": person_locations.phi,
        }


class BasePrivatePatientPayload(BasePatientPayload):
    _sector = PRIVATE_SECTOR
    he_code = jsonobject.StringProperty(required=False, exclude_if_none=True)

    @staticmethod
    def get_locations(person_case, episode_case):
        person_locations = get_person_locations(person_case, episode_case)
        return {
            "state_code": person_locations.sto,
            "district_code": person_locations.dto,
            "tu_code": person_locations.tu,
            "he_code": person_locations.pcp,
        }


def get_payload_properties(sector):
    if sector not in SECTORS:
        raise ValueError('sector argument should be one of {}'.format(",".join(SECTORS)))

    properties = {}
    spec = load_api_spec()
    for param in spec.api_params:
        if param.payload_object:
            properties[param.api_param_name] = jsonobject.ObjectProperty(
                to_function(param.payload_object),
                required=param.required_,
                exclude_if_none=param.exclude_if_none,
            )
        else:
            properties[param.api_param_name] = jsonobject.StringProperty(
                choices=param.get_by_sector('choices', sector),
                required=param.required_,
                exclude_if_none=param.exclude_if_none,
                validators=([to_function(param.validator)(sector, param.validator_values)]
                            if param.validator else []),
            )
    return properties


PublicPatientPayload = type('PublicPatientPayload', (BasePublicPatientPayload,),
                            get_payload_properties('public'))

PrivatePatientPayload = type('PublicPatientPayload', (BasePrivatePatientPayload,),
                             get_payload_properties('private'))


def get_patient_payload(person_case, occurrence_case, episode_case):
    if person_case.get_case_property(ENROLLED_IN_PRIVATE) == 'true':
        return PrivatePatientPayload.create(person_case, occurrence_case, episode_case)
    else:
        return PublicPatientPayload.create(person_case, occurrence_case, episode_case)
