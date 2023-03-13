import re
import uuid
from collections import defaultdict
from datetime import datetime
from itertools import chain
from typing import (
    Any,
    Callable,
    DefaultDict,
    Dict,
    List,
    NamedTuple,
    Optional,
    Tuple,
    Union,
)

from django.utils.translation import gettext as _

import pytz
from dateutil import parser as dateutil_parser
from dateutil.tz import tzutc
from lxml import etree
from requests import RequestException
from urllib3.exceptions import HTTPError

from casexml.apps.case.mock import CaseBlock, IndexAttrs

from corehq.apps.case_importer import util as importer_util
from corehq.apps.case_importer.const import LookupErrors
from corehq.apps.case_importer.util import EXTERNAL_ID
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.apps.users.models import CommCareUser
from corehq.form_processor.models import CommCareCase
from corehq.motech.exceptions import ConfigurationError, JsonpathError
from corehq.motech.openmrs.const import (
    ATOM_FEED_NAME_PATIENT,
    ATOM_FEED_NAMES,
    OPENMRS_ATOM_FEED_DEVICE_ID,
    XMLNS_OPENMRS,
)
from corehq.motech.openmrs.exceptions import (
    DuplicateCaseMatch,
    OpenmrsException,
    OpenmrsFeedRuntimeException,
    OpenmrsFeedSyntaxError,
)
from corehq.motech.openmrs.openmrs_config import (
    ALL_CONCEPTS,
    ObservationMapping,
    get_property_map,
)
from corehq.motech.openmrs.repeater_helpers import get_patient_by_uuid
from corehq.motech.openmrs.repeaters import AtomFeedStatus, OpenmrsRepeater
from corehq.motech.value_source import (
    ValueSource,
    as_value_source,
    deserialize,
    get_import_value,
)
from corehq.util.dates import iso_string_to_datetime
from dimagi.utils.parsing import json_format_datetime

CASE_BLOCK_ARGS = ("case_name", "owner_id")


class CaseAttrs(NamedTuple):
    case_id: str
    case_type: str
    owner_id: str


def get_feed_xml(requests, feed_name, page: str):
    assert feed_name in ATOM_FEED_NAMES
    feed_url = f'/ws/atomfeed/{feed_name}/{page}'
    resp = requests.get(feed_url)

    if resp.status_code == 500:
        if 'AtomFeedRuntimeException: feed does not exist' in resp.text:
            exception = OpenmrsFeedRuntimeException(
                f'Domain "{requests.domain_name}": Page does not exist in Atom '
                f'feed "{resp.url}". Resetting Atom feed status.'
            )
            requests.notify_exception(
                str(exception),
                _("This can happen if the IP address of a Repeater is changed "
                  "to point to a different server, or if a server has been "
                  "rebuilt. It can signal more severe consequences, like "
                  "attempts to synchronize CommCare cases with OpenMRS "
                  "patients that can no longer be found.")
            )
            raise exception
        if ('AtomFeedRuntimeException: feedId must not be null and must be '
                'greater than 0') in resp.text:
            exception = OpenmrsFeedRuntimeException(
                f'Domain "{requests.domain_name}": Page "{page}" is not valid '
                f'in Atom feed "{resp.url}". Resetting Atom feed status.'
            )
            requests.notify_exception(
                str(exception),
                _('It is unclear how Atom feed pagination can lead to page '
                  '"{}". Follow up with OpenMRS system '
                  'administrator.').format(page)
            )
            raise exception

        # Use OpenmrsException instead of OpenmrsFeedRuntimeException so
        # that we don't reset the Atom feed if we don't know what the
        # problem is.
        exception = OpenmrsException(
            f'Domain "{requests.domain_name}": Unrecognized error in Atom '
            f'feed "{resp.url}".'
        )
        requests.notify_exception(
            str(exception),
            _('Response text: \n{}').format(resp.text)
        )
        raise exception

    try:
        root = etree.fromstring(resp.content)
    except etree.XMLSyntaxError as err:
        requests.notify_exception(
            str(err),
            _('There is an XML syntax error in the OpenMRS Atom feed at '
              f'"{resp.url}".')
        )
        raise OpenmrsFeedSyntaxError() from err
    return root


def get_timestamp(element, xpath='./atom:updated'):
    """
    Returns a datetime instance of the text at the given xpath.

    >>> element = etree.XML('''<feed xmlns="http://www.w3.org/2005/Atom">
    ...     <updated>2018-05-15T14:02:08Z</updated>
    ... </feed>''')
    >>> get_timestamp(element)
    datetime.datetime(2018, 5, 15, 14, 2, 8, tzinfo=tzutc())

    """
    timestamp_elems = element.xpath(xpath, namespaces={'atom': 'http://www.w3.org/2005/Atom'})
    if not timestamp_elems:
        raise ValueError(f'XPath "{xpath}" not found')
    if len(timestamp_elems) != 1:
        raise ValueError(f'XPath "{xpath}" matched multiple nodes')
    tzinfos = {'UTC': tzutc()}
    return dateutil_parser.parse(timestamp_elems[0].text, tzinfos=tzinfos)


def get_patient_uuid(element):
    """
    Extracts the UUID of a patient from an entry's "content" node.

    >>> element = etree.XML('''<entry>
    ...     <content type="application/vnd.atomfeed+xml">
    ...         <![CDATA[/openmrs/ws/rest/v1/patient/e8aa08f6-86cd-42f9-8924-1b3ea021aeb4?v=full]]>
    ...     </content>
    ... </entry>''')
    >>> get_patient_uuid(element)
    'e8aa08f6-86cd-42f9-8924-1b3ea021aeb4'

    """
    # "./*[local-name()='content']" ignores namespaces and matches all
    # child nodes with tag name "content". This lets us traverse the
    # feed regardless of whether the Atom namespace is explicitly given.
    content = element.xpath("./*[local-name()='content']")
    pattern = re.compile(r'/patient/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\b')
    if content and len(content) == 1:
        cdata = content[0].text
        matches = pattern.search(cdata)
        if matches:
            return matches.group(1)
    raise ValueError('Patient UUID not found')


def get_encounter_uuid(element):
    """
    Extracts the UUID of an encounter from an entry's "content" node.

    >>> element = etree.XML('''<entry>
    ...   <title>Encounter</title>
    ...   <content type="application/vnd.atomfeed+xml">
    ...     <![CDATA[/openmrs/ws/rest/v1/bahmnicore/bahmniencounter/0f54fe40-89af-4412-8dd4-5eaebe8684dc?includeAll=true]]>
    ...   </content>
    ... </entry>''')
    >>> get_encounter_uuid(element)
    '0f54fe40-89af-4412-8dd4-5eaebe8684dc'

    """
    content = element.xpath("./*[local-name()='content']")
    pattern = re.compile(r'/bahmniencounter/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\b')
    if content and len(content) == 1:
        cdata = content[0].text
        matches = pattern.search(cdata)
        if matches:
            return matches.group(1)
        # Not everything in the Encounter atom feed is an Encounter. It
        # also includes bed assignments.
        if 'bedPatientAssignment' in cdata:
            return None
    raise ValueError('Unrecognised Encounter atom feed entry')


def get_feed_updates(repeater, feed_name):
    """
    Iterates over a paginated atom feed, yields patients updated since
    repeater.patients_last_polled_at, and updates the repeater.
    """
    def has_new_entries_since(last_polled_at, element, xpath='./atom:updated'):
        return not last_polled_at or get_timestamp(element, xpath) > last_polled_at

    assert feed_name in ATOM_FEED_NAMES
    atom_feed_status = repeater.atom_feed_status.get(feed_name, AtomFeedStatus().to_json())
    last_polled_at = atom_feed_status['last_polled_at']
    page = atom_feed_status['last_page']
    get_uuid = get_patient_uuid if feed_name == ATOM_FEED_NAME_PATIENT else get_encounter_uuid
    # The OpenMRS Atom feeds' timestamps are timezone-aware. So when we
    # compare timestamps in has_new_entries_since(), this timestamp
    # must also be timezone-aware. repeater.patients_last_polled_at is
    # set to a UTC timestamp (datetime.utcnow()), but the timezone gets
    # dropped because it is stored as a jsonobject DateTimeProperty.
    # This sets it as a UTC timestamp again:
    last_polled_at = iso_string_to_datetime(last_polled_at) if type(last_polled_at) is str else last_polled_at
    last_polled_at = pytz.utc.localize(last_polled_at) if last_polled_at else None
    try:
        while True:
            feed_xml = get_feed_xml(repeater.requests, feed_name, page)
            if has_new_entries_since(last_polled_at, feed_xml):
                for entry in feed_xml.xpath('./atom:entry', namespaces={'atom': 'http://www.w3.org/2005/Atom'}):
                    if has_new_entries_since(last_polled_at, entry, './atom:published'):
                        entry_uuid = get_uuid(entry)
                        if entry_uuid:
                            yield entry_uuid
            next_page = feed_xml.xpath(
                './atom:link[@rel="next-archive"]',
                namespaces={'atom': 'http://www.w3.org/2005/Atom'}
            )
            if next_page:
                href = next_page[0].get('href')
                page = href.split('/')[-1]
            else:
                if not page:
                    this_page = feed_xml.xpath(
                        './atom:link[@rel="via"]',
                        namespaces={'atom': 'http://www.w3.org/2005/Atom'}
                    )
                    href = this_page[0].get('href')
                    page = href.split('/')[-1]
                break
    except OpenmrsFeedRuntimeException:
        # Reset feed status so that polling will start at the beginning
        # of the feed.
        repeater.atom_feed_status[feed_name] = AtomFeedStatus().to_json()
        repeater.save()
    except (OpenmrsException, RequestException, HTTPError):
        # Don't update repeater if OpenMRS is offline, or XML cannot be
        # parsed.
        return
    else:
        repeater.atom_feed_status[feed_name] = {
            'last_polled_at': json_format_datetime(datetime.utcnow()),
            'last_page': page,
            'doc_type': 'AtomFeedStatus',  # Needed for syncing to Couch
        }
        repeater.save()


def get_addpatient_caseblock(
    case_type: str,
    default_owner: Optional[CommCareUser],
    patient: dict,
    repeater: OpenmrsRepeater,
) -> CaseBlock:

    case_block_kwargs = get_case_block_kwargs_from_patient(patient, repeater)
    if default_owner:
        case_block_kwargs.setdefault("owner_id", default_owner.user_id)
    if not case_block_kwargs.get("owner_id"):
        raise ConfigurationError(_(
            f'No users found at location "{repeater.location_id}" to own '
            'patients added from OpenMRS Atom feed.'
        ))
    case_id = uuid.uuid4().hex
    return CaseBlock(
        create=True,
        case_id=case_id,
        case_type=case_type,
        external_id=patient['uuid'],
        **case_block_kwargs
    )


def get_updatepatient_caseblock(case, patient, repeater):
    case_block_kwargs = get_case_block_kwargs_from_patient(patient, repeater, case)
    return CaseBlock(
        create=False,
        case_id=case.case_id,
        **case_block_kwargs
    )


def get_case_block_kwargs_from_patient(patient, repeater, case=None):
    property_map = get_property_map(repeater.openmrs_config['case_config'])
    case_block_kwargs = {
        "case_name": patient['person']['display'],
        "update": {}
    }
    for prop, (jsonpath, value_source_config) in property_map.items():
        value_source = as_value_source(value_source_config)
        if not value_source.can_import:
            continue
        matches = jsonpath.find(patient)
        if matches:
            patient_value = matches[0].value
            new_value = value_source.deserialize(patient_value)
            if case:
                if prop in CASE_BLOCK_ARGS:
                    case_value = case.name if prop == "case_name" else getattr(case, prop)
                    if case_value != new_value:
                        case_block_kwargs[prop] = new_value
                else:
                    case_value = case.get_case_property(prop)
                    if case_value != new_value:
                        case_block_kwargs["update"][prop] = new_value
            else:
                if prop in CASE_BLOCK_ARGS:
                    case_block_kwargs[prop] = new_value
                else:
                    case_block_kwargs["update"][prop] = new_value
    return case_block_kwargs


def update_patient(repeater, patient_uuid):
    """
    Fetch patient from OpenMRS, submit case update for all mapped case
    properties.

    .. NOTE:: OpenMRS UUID must be saved to "external_id" case property

    """
    if len(repeater.white_listed_case_types) != 1:
        raise ConfigurationError(_(
            f'{repeater.domain}: {repeater}: Error in settings: Unable to update '
            f'patients from OpenMRS unless only one case type is specified.'
        ))
    case_type = repeater.white_listed_case_types[0]
    try:
        patient = get_patient_by_uuid(repeater.requests, patient_uuid)
    except (RequestException, ValueError) as err:
        raise OpenmrsException(_(
            f'{repeater.domain}: {repeater}: Error fetching Patient '
            f'{patient_uuid!r}: {err}'
        )) from err

    case, error = importer_util.lookup_case(
        EXTERNAL_ID,
        patient_uuid,
        repeater.domain,
        case_type=case_type,
    )
    if error == LookupErrors.NotFound:
        if not repeater.openmrs_config['case_config']['import_creates_cases']:
            # We can't create cases via the Atom feed, just update them.
            # Nothing to do here.
            return
        default_owner: Optional[CommCareUser] = repeater.first_user
        case_block = get_addpatient_caseblock(case_type, default_owner, patient, repeater)
    elif error == LookupErrors.MultipleResults:
        # Multiple cases have been matched to the same patient.
        # Could be caused by:
        # * The cases were given the same identifier value. It could
        #   be user error, or case config assumed identifier was
        #   unique but it wasn't.
        # * PatientFinder matched badly.
        # * Race condition where a patient was previously added to
        #   both CommCare and OpenMRS.
        raise DuplicateCaseMatch(_(
            f'{repeater.domain}: {repeater}: More than one case found '
            f'matching unique OpenMRS UUID. case external_id: "{patient_uuid}"'
        ))
    else:
        case_block = get_updatepatient_caseblock(case, patient, repeater)

    if case_block:
        submit_case_blocks(
            [case_block.as_text()],
            repeater.domain,
            xmlns=XMLNS_OPENMRS,
            device_id=OPENMRS_ATOM_FEED_DEVICE_ID + repeater.repeater_id,
        )


def import_encounter(repeater, encounter_uuid):
    try:
        encounter = get_encounter(repeater, encounter_uuid)
    except (RequestException, ValueError) as err:
        raise OpenmrsException(_(
            f'{repeater.domain}: {repeater}: Error fetching Encounter '
            f'"{encounter_uuid}": {err}'
        )) from err

    case_blocks = []
    patient_case_id, default_owner_id, patient_case_block = get_case_id_owner_id_case_block(
        repeater, encounter['patientUuid'],
    )
    if not patient_case_id:
        # No patient to create or update. Ignore this encounter.
        return
    if patient_case_block:
        case_blocks.append(patient_case_block)

    case_block_kwargs, more_case_blocks = get_case_block_kwargs_from_encounter(
        repeater, encounter, patient_case_id, default_owner_id,
    )
    case_blocks.extend(more_case_blocks)
    if has_case_updates(case_block_kwargs) or case_blocks:
        update_case(repeater, patient_case_id, case_block_kwargs, case_blocks)


def get_case_block_kwargs_from_encounter(
    repeater: OpenmrsRepeater,
    encounter: dict,
    patient_case_id: str,
    default_owner_id: str,
) -> Tuple[dict, List[CaseBlock]]:
    case_block_kwargs = {"update": {}, "index": {}}
    case_blocks = []

    more_kwargs = get_case_block_kwargs_from_encounter_meta(
        encounter,
        get_encounter_datetime_value_sources(repeater)
    )
    deep_update(case_block_kwargs, more_kwargs)

    patient_case_type = repeater.white_listed_case_types[0]
    observation_mappings = get_observation_mappings(repeater)
    patient_case_attrs = CaseAttrs(
        patient_case_id,
        patient_case_type,
        default_owner_id,
    )
    more_kwargs, more_case_blocks = get_case_block_kwargs_from_observations(
        encounter['observations'],
        observation_mappings,
        patient_case_attrs,
    )
    deep_update(case_block_kwargs, more_kwargs)
    case_blocks.extend(more_case_blocks)

    if 'bahmniDiagnoses' in encounter:
        more_kwargs, more_case_blocks = get_case_block_kwargs_from_bahmni_diagnoses(
            encounter['bahmniDiagnoses'],
            get_diagnosis_mappings(repeater),
            patient_case_attrs,
        )
        deep_update(case_block_kwargs, more_kwargs)
        case_blocks.extend(more_case_blocks)
        # O/ ... ... ... start snip
        # TODO: Remove this after deploy, once existing configs have
        #       been moved to repeater.bahmni_diagnoses
        more_kwargs, more_case_blocks = get_case_block_kwargs_from_bahmni_diagnoses(
            encounter['bahmniDiagnoses'],
            observation_mappings,
            patient_case_attrs,
        )
        deep_update(case_block_kwargs, more_kwargs)
        case_blocks.extend(more_case_blocks)
        #  O\ ˙˙˙ ˙˙˙ ˙˙˙ end snip

    return case_block_kwargs, case_blocks


def get_encounter(repeater, encounter_uuid):
    """
    Fetches an Encounter by its UUID

    :raises RequestException: If response status is not in the 200s
    :raises ValueError: If the response body does not contain valid JSON.
    :return: Encounter dict
    """
    response = repeater.requests.get(
        '/ws/rest/v1/bahmnicore/bahmniencounter/' + encounter_uuid,
        {'includeAll': 'true'},
        raise_for_status=True
    )
    return response.json()


def get_case_id_owner_id_case_block(
    repeater: OpenmrsRepeater,
    patient_uuid: str,
) -> Tuple[Optional[str], Optional[str], Optional[CaseBlock]]:
    """
    If a case exists with external_id == patient_uuid, returns its
    case_id, owner_id, and None. Otherwise returns the case_id, owner_id
    and case block for a new case.
    """
    # NOTE: Atom Feed integration requires Patient UUID to be external_id
    case = get_case(repeater, patient_uuid)
    if case:
        return case.case_id, case.owner_id, None
    if not repeater.openmrs_config['case_config']['import_creates_cases']:
        # We cannot create new cases for patients in the Atom feed.
        return None, None, None
    case_block = create_case(repeater, patient_uuid)
    return case_block.case_id, case_block.owner_id, case_block


def get_case(
    repeater: OpenmrsRepeater,
    patient_uuid: str,
) -> Union[CommCareCase, None]:

    case_type = repeater.white_listed_case_types[0]
    case, error = importer_util.lookup_case(
        EXTERNAL_ID,
        patient_uuid,
        repeater.domain,
        case_type=case_type,
    )
    if error == LookupErrors.MultipleResults:
        raise DuplicateCaseMatch(_(
            f'{repeater.domain}: {repeater}: More than one case found '
            'matching unique OpenMRS UUID. case external_id: '
            f'"{patient_uuid}". '
        ))
    return case


def create_case(
    repeater: OpenmrsRepeater,
    patient_uuid: str,
) -> CaseBlock:

    case_type = repeater.white_listed_case_types[0]
    patient = get_patient_by_uuid(repeater.requests, patient_uuid)
    default_owner: Optional[CommCareUser] = repeater.first_user
    case_block = get_addpatient_caseblock(case_type, default_owner, patient, repeater)
    return case_block


def get_observation_mappings(
    repeater: OpenmrsRepeater
) -> DefaultDict[str, List[ObservationMapping]]:
    obs_mappings = defaultdict(list)
    for form_config in repeater.openmrs_config['form_configs']:
        for obs_mapping in form_config['openmrs_observations']:
            value_source = as_value_source(obs_mapping['value'])
            if (
                value_source.can_import
                and (obs_mapping.get('case_property') or obs_mapping.get('indexed_case_mapping'))
            ):
                # If obs_mapping.concept is "" or None, the mapping
                # should apply to any concept
                concept = obs_mapping['concept'] or None

                # It's possible that an OpenMRS concept appears more
                # than once in form_configs. We are using a
                # defaultdict(list) so that earlier definitions
                # don't get overwritten by later ones:
                obs_mappings[concept].append(obs_mapping)
    return obs_mappings


def get_diagnosis_mappings(
    repeater: OpenmrsRepeater
) -> DefaultDict[str, List[ObservationMapping]]:
    diag_mappings = defaultdict(list)
    for form_config in repeater.openmrs_config['form_configs']:
        for diag_mapping in form_config['bahmni_diagnoses']:
            value_source = as_value_source(diag_mapping['value'])
            if (
                value_source.can_import
                and (diag_mapping.get('case_property') or diag_mapping.get('indexed_case_mapping'))
            ):
                concept = diag_mapping.get('concept', None)
                diag_mappings[concept].append(diag_mapping)
    return diag_mappings


def get_encounter_datetime_value_sources(
    repeater: OpenmrsRepeater
) -> List[ValueSource]:
    value_sources = []
    for form_config in repeater.openmrs_config['form_configs']:
        encounter_datetime_config = form_config['openmrs_start_datetime']
        if encounter_datetime_config and "case_property" in encounter_datetime_config:
            value_source = as_value_source(encounter_datetime_config)
            if value_source.can_import:
                if not value_source.jsonpath:
                    value_source.jsonpath = "encounterDateTime"
                value_sources.append(value_source)
    return value_sources


def update_case(repeater, case_id, case_block_kwargs, case_blocks):
    case_blocks.append(CaseBlock(
        case_id=case_id,
        create=False,
        **case_block_kwargs,
    ))
    submit_case_blocks(
        [cb.as_text() for cb in case_blocks],
        repeater.domain,
        xmlns=XMLNS_OPENMRS,
        device_id=OPENMRS_ATOM_FEED_DEVICE_ID + repeater.repeater_id,
    )


def get_case_block_kwargs_from_observations(
    observations: List[dict],
    mappings: Dict[str, List[ObservationMapping]],
    case_attrs: CaseAttrs,
) -> Tuple[dict, List[CaseBlock]]:
    """
    Traverse a tree of observations, and return the ones mapped to case
    properties.
    """
    case_block_kwargs, case_blocks = get_case_block_kwargs_from_concepts(
        observations,
        mappings,
        case_attrs,
        uuid_func=lambda obs: obs.get('concept', {}).get('uuid'),
        fallback_value_func=lambda obs: obs.get('value'),
    )

    for obs in observations:
        if obs.get('groupMembers'):
            more_kwargs, more_case_blocks = get_case_block_kwargs_from_observations(
                obs['groupMembers'],
                mappings,
                case_attrs,
            )
            deep_update(case_block_kwargs, more_kwargs)
            case_blocks.extend(more_case_blocks)

    return case_block_kwargs, case_blocks


def get_case_block_kwargs_from_encounter_meta(
    encounter: dict,
    encounter_datetime_value_sources: List[ValueSource],
) -> dict:
    case_block_kwargs = {"update": {}}
    for value_source in encounter_datetime_value_sources:
        try:
            value = value_source.get_import_value(encounter)
        except (ConfigurationError, JsonpathError):
            # value_source isn't configured to parse encounter
            continue
        if value_source.case_property in CASE_BLOCK_ARGS:
            case_block_kwargs[value_source.case_property] = value
        else:
            case_block_kwargs["update"][value_source.case_property] = value
    return case_block_kwargs


def get_case_block_kwargs_from_bahmni_diagnoses(
    diagnoses: List[dict],
    mappings: Dict[str, List[ObservationMapping]],
    case_attrs: CaseAttrs,
) -> Tuple[dict, List[CaseBlock]]:
    """
    Iterate a list of Bahmni diagnoses, and return the ones mapped to
    case properties.
    """
    return get_case_block_kwargs_from_concepts(
        diagnoses,
        mappings,
        case_attrs,
        uuid_func=lambda diag: diag.get('codedAnswer', {}).get('uuid'),
        fallback_value_func=lambda diag: diag.get('codedAnswer', {}).get('name'),
    )


def get_case_block_kwargs_from_concepts(
    observationoids: List[dict],  # Observations or things that look like them
    mappings: Dict[str, List[ObservationMapping]],
    case_attrs: CaseAttrs,
    uuid_func: Callable,
    fallback_value_func: Callable,
) -> Tuple[dict, List[CaseBlock]]:
    case_block_kwargs = {"update": {}}
    case_blocks = []
    for obs in observationoids:
        uuid = uuid_func(obs)
        if uuid:
            obs_mappings = chain(
                mappings.get(uuid, []),
                mappings.get(ALL_CONCEPTS, []),
            )
            for mapping in obs_mappings:
                if mapping.get('case_property'):
                    more_kwargs = get_case_block_kwargs_for_case_property(
                        mapping, obs, fallback_value=fallback_value_func(obs)
                    )
                    deep_update(case_block_kwargs, more_kwargs)
                if mapping.get('indexed_case_mapping'):
                    case_block = get_case_block_for_indexed_case(
                        mapping, obs, case_attrs,
                    )
                    case_blocks.append(case_block)
    return case_block_kwargs, case_blocks


def get_case_block_kwargs_for_case_property(
    mapping: ObservationMapping,
    external_data: dict,
    fallback_value: Any,
) -> dict:
    case_block_kwargs = {"update": {}}
    try:
        value = get_import_value(mapping.get('value'), external_data)
    except (ConfigurationError, JsonpathError):
        # mapping.value isn't configured to parse external_data
        value = deserialize(mapping.get('value'), fallback_value)
    if mapping.get('case_property') in CASE_BLOCK_ARGS:
        case_block_kwargs[mapping['case_property']] = value
    else:
        case_block_kwargs["update"][mapping['case_property']] = value
    return case_block_kwargs


def get_case_block_for_indexed_case(
    mapping: ObservationMapping,
    external_data: dict,
    parent_case_attrs: CaseAttrs,
) -> CaseBlock:
    parent_case_id, parent_case_type, default_owner_id = parent_case_attrs

    relationship = mapping['indexed_case_mapping']['relationship']
    case_block_kwargs = {
        "index": {
            mapping['indexed_case_mapping']['identifier']: IndexAttrs(
                parent_case_type,
                parent_case_id,
                relationship,
            )
        },
        "update": {}
    }
    for value_source_config in mapping['indexed_case_mapping']['case_properties']:
        value_source = as_value_source(value_source_config)
        value = value_source.get_import_value(external_data)
        if value_source.case_property in CASE_BLOCK_ARGS:
            case_block_kwargs[value_source.case_property] = value
        else:
            case_block_kwargs["update"][value_source.case_property] = value

    case_id = uuid.uuid4().hex
    case_type = mapping['indexed_case_mapping']['case_type']
    case_block_kwargs.setdefault("owner_id", default_owner_id)
    if not case_block_kwargs["owner_id"]:
        raise ConfigurationError(_(
            f'Unable to determine mobile worker to own new "{case_type}" '
            f'{relationship} case or parent case "{parent_case_id}"'
        ))
    case_block = CaseBlock(
        create=True,
        case_id=case_id,
        case_type=case_type,
        **case_block_kwargs
    )
    return case_block


def has_case_updates(case_block_kwargs):
    """
    Returns True if case_block_kwargs contains case changes.

    >>> has_case_updates({"owner_id": "123456", "update": {}})
    True
    >>> has_case_updates({"update": {}})
    False

    """
    if case_block_kwargs.get("update"):
        return True
    if case_block_kwargs.get("index"):
        return True
    return any(k for k in case_block_kwargs if k not in ("update", "index"))


def deep_update(dict_by_ref: dict, other: dict):
    """
    Recursively update ``dict_by_ref`` with values from ``other``.

    >>> nested = {"inner": {"ham": "spam"}}
    >>> deep_update(nested, {"inner": {"eggs": "spam"}})
    >>> nested == {"inner": {"ham": "spam", "eggs": "spam"}}
    True

    >>> nested = {"inner": {"ham": "spam"}}
    >>> deep_update(nested, {"inner": "SPAM"})
    >>> nested
    {'inner': 'SPAM'}

    """
    for key, value in other.items():
        if (
            key in dict_by_ref
            and isinstance(dict_by_ref[key], dict)
            and isinstance(value, dict)
        ):
            deep_update(dict_by_ref[key], value)
        else:
            dict_by_ref[key] = value
