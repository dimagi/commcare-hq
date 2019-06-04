from __future__ import absolute_import
from __future__ import unicode_literals

import re
import uuid
from datetime import datetime

import pytz
from dateutil import parser as dateutil_parser
from dateutil.tz import tzutc
from lxml import etree
from requests import RequestException
from urllib3.exceptions import HTTPError

from casexml.apps.case.mock import CaseBlock
from corehq.apps.case_importer import util as importer_util
from corehq.apps.case_importer.const import LookupErrors
from corehq.apps.case_importer.util import EXTERNAL_ID
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.apps.locations.dbaccessors import get_one_commcare_user_at_location
from corehq.motech.const import DIRECTION_IMPORT
from corehq.motech.openmrs.const import (
    ATOM_FEED_NAME_PATIENT,
    ATOM_FEED_NAMES,
    OPENMRS_ATOM_FEED_DEVICE_ID,
    XMLNS_OPENMRS,
)
from corehq.motech.openmrs.exceptions import OpenmrsFeedDoesNotExist
from corehq.motech.openmrs.openmrs_config import get_property_map
from corehq.motech.openmrs.repeater_helpers import get_patient_by_uuid
from corehq.motech.openmrs.repeaters import AtomFeedStatus
from corehq.util.soft_assert import soft_assert


_assert = soft_assert(['@'.join(('nhooper', 'dimagi.com'))])


def get_feed_xml(requests, feed_name, page):
    if not page:
        # If this is the first time the patient feed is polled, just get
        # the most recent changes. This shows updating patients
        # successfully, but does not replay all OpenMRS changes.
        page = 'recent'
    assert feed_name in ATOM_FEED_NAMES
    feed_url = '/'.join(('/ws/atomfeed', feed_name, page))
    resp = requests.get(feed_url)
    if resp.status_code == 500 and 'AtomFeedRuntimeException: feed does not exist' in resp.content:
        # This can happen if a Repeater IP address is changed to point
        # to a different server, or if a server has been rebuilt.
        _assert(False, 'Domain "{}": Page does not exist in Atom feed "{}". '
                       'Resetting Atom feed status.'.format(requests.domain_name, resp.url))
        raise OpenmrsFeedDoesNotExist()
    root = etree.fromstring(resp.content)
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
        raise ValueError('XPath "{}" not found'.format(xpath))
    if len(timestamp_elems) != 1:
        raise ValueError('XPath "{}" matched multiple nodes'.format(xpath))
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
    >>> get_patient_uuid(element) == 'e8aa08f6-86cd-42f9-8924-1b3ea021aeb4'
    True

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
    Extracts the UUID of a patient from an entry's "content" node.

    >>> element = etree.XML('''<entry>
    ...     <content type="application/vnd.atomfeed+xml">
    ...         <![CDATA[/openmrs/ws/rest/v1/bahmnicore/bahmniencounter/0f54fe40-89af-4412-8dd4-5eaebe8684dc?includeAll=true]]>
    ...     </content>
    ... </entry>''')
    >>> get_encounter_uuid(element) == '0f54fe40-89af-4412-8dd4-5eaebe8684dc'
    True

    """
    content = element.xpath("./*[local-name()='content']")
    pattern = re.compile(r'/bahmniencounter/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\b')
    if content and len(content) == 1:
        cdata = content[0].text
        matches = pattern.search(cdata)
        if matches:
            return matches.group(1)
    raise ValueError('Encounter UUID not found')


def get_feed_updates(repeater, feed_name):
    """
    Iterates over a paginated atom feed, yields patients updated since
    repeater.patients_last_polled_at, and updates the repeater.
    """
    def has_new_entries_since(last_polled_at, element, xpath='./atom:updated'):
        return not last_polled_at or get_timestamp(element, xpath) > last_polled_at

    assert feed_name in ATOM_FEED_NAMES
    atom_feed_status = repeater.atom_feed_status.get(feed_name, AtomFeedStatus())
    last_polled_at = atom_feed_status['last_polled_at']
    page = atom_feed_status['last_page']
    get_uuid = get_patient_uuid if feed_name == ATOM_FEED_NAME_PATIENT else get_encounter_uuid
    # The OpenMRS Atom feeds' timestamps are timezone-aware. So when we
    # compare timestamps in has_new_entries_since(), this timestamp
    # must also be timezone-aware. repeater.patients_last_polled_at is
    # set to a UTC timestamp (datetime.utcnow()), but the timezone gets
    # dropped because it is stored as a jsonobject DateTimeProperty.
    # This sets it as a UTC timestamp again:
    last_polled_at = pytz.utc.localize(last_polled_at) if last_polled_at else None
    try:
        while True:
            feed_xml = get_feed_xml(repeater.requests, feed_name, page)
            if has_new_entries_since(last_polled_at, feed_xml):
                for entry in feed_xml.xpath('./atom:entry', namespaces={'atom': 'http://www.w3.org/2005/Atom'}):
                    if has_new_entries_since(last_polled_at, entry, './atom:published'):
                        yield get_uuid(entry)
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
    except (RequestException, HTTPError):
        # Don't update repeater if OpenMRS is offline
        return
    except OpenmrsFeedDoesNotExist:
        repeater.atom_feed_status[feed_name] = AtomFeedStatus()
        repeater.save()
    else:
        repeater.atom_feed_status[feed_name] = AtomFeedStatus(
            last_polled_at=datetime.utcnow(),
            last_page=page,
        )
        repeater.save()


def get_addpatient_caseblock(case_type, owner, patient, repeater):
    property_map = get_property_map(repeater.openmrs_config.case_config)

    fields_to_update = {}
    for prop, (jsonpath, value_source) in property_map.items():
        if not value_source.check_direction(DIRECTION_IMPORT):
            continue
        matches = jsonpath.find(patient)
        if matches:
            patient_value = matches[0].value
            new_value = value_source.deserialize(patient_value)
            fields_to_update[prop] = new_value

    if fields_to_update:
        case_id = uuid.uuid4().hex
        case_name = patient['person']['display']
        return CaseBlock(
            create=True,
            case_id=case_id,
            owner_id=owner.user_id,
            user_id=owner.user_id,
            case_type=case_type,
            case_name=case_name,
            external_id=patient['uuid'],
            update=fields_to_update,
        )


def get_updatepatient_caseblock(case, patient, repeater):
    property_map = get_property_map(repeater.openmrs_config.case_config)

    fields_to_update = {}
    for prop, (jsonpath, value_source) in property_map.items():
        if not value_source.check_direction(DIRECTION_IMPORT):
            continue
        matches = jsonpath.find(patient)
        if matches:
            patient_value = matches[0].value
            case_value = case.get_case_property(prop)
            new_value = value_source.deserialize(patient_value)
            if case_value != new_value:
                fields_to_update[prop] = new_value

    if fields_to_update:
        case_name = patient['person']['display']
        return CaseBlock(
            create=False,
            case_id=case.get_id,
            case_name=case_name,
            update=fields_to_update,
        )


def update_patient(repeater, patient_uuid):
    """
    Fetch patient from OpenMRS, submit case update for all mapped case
    properties.

    .. NOTE:: OpenMRS UUID must be saved to "external_id" case property

    """
    _assert(
        len(repeater.white_listed_case_types) == 1,
        'Unable to update patients from OpenMRS unless a single case type is '
        'specified. domain: "{}". repeater: "{}".'.format(
            repeater.domain, repeater.get_id
        )
    )
    case_type = repeater.white_listed_case_types[0]
    patient = get_patient_by_uuid(repeater.requests, patient_uuid)
    case, error = importer_util.lookup_case(
        EXTERNAL_ID,
        patient_uuid,
        repeater.domain,
        case_type=case_type,
    )
    if error == LookupErrors.NotFound:
        owner = get_one_commcare_user_at_location(repeater.domain, repeater.location_id)
        _assert(
            owner,
            'No users found at location "{}" to own patients added from '
            'OpenMRS atom feed. domain: "{}". repeater: "{}".'.format(
                repeater.location_id, repeater.domain, repeater.get_id
            )
        )
        case_block = get_addpatient_caseblock(case_type, owner, patient, repeater)

    else:
        _assert(
            error != LookupErrors.MultipleResults,
            # Multiple cases matched to the same patient.
            # Could be caused by:
            # * The cases were given the same identifier value. It could
            #   be user error, or case config assumed identifier was
            #   unique but it wasn't.
            # * PatientFinder matched badly.
            # * Race condition where a patient was previously added to
            #   both CommCare and OpenMRS.
            'More than one case found matching unique OpenMRS UUID. '
            'domain: "{}". case external_id: "{}". repeater: "{}".'.format(
                repeater.domain, patient_uuid, repeater.get_id
            )
        )
        case_block = get_updatepatient_caseblock(case, patient, repeater)

    if case_block:
        submit_case_blocks(
            [case_block.as_string()],
            repeater.domain,
            xmlns=XMLNS_OPENMRS,
            device_id=OPENMRS_ATOM_FEED_DEVICE_ID + repeater.get_id,
        )


def import_encounter(repeater, encounter_uuid):
    # It's possible that an OpenMRS concept appears more than once in
    # form_configs. Use a defaultdict(list) so that earlier definitions
    # don't get overwritten by later ones:

    def fields_from_observations(observations, mappings):
        """
        Traverse a tree of observations, and return the ones mapped to
        case properties.
        """
        fields = {}
        for obs in observations:
            if obs['concept']['uuid'] in mappings:
                for mapping in mappings[obs['concept']['uuid']]:
                    fields[mapping.case_property] = mapping.value.deserialize(obs['value'])
            if obs['groupMembers']:
                fields.update(fields_from_observations(obs['groupMembers'], mappings))
        return fields

    response = repeater.requests.get(
        '/ws/rest/v1/bahmnicore/bahmniencounter/' + encounter_uuid,
        {'includeAll': 'true'},
        raise_for_status=True
    )
    encounter = response.json()

    case_property_updates = fields_from_observations(encounter['observations'], repeater.observation_mappings)

    if case_property_updates:
        case_blocks = []
        patient_uuid = encounter['patientUuid']
        case_type = repeater.white_listed_case_types[0]
        case, error = importer_util.lookup_case(
            EXTERNAL_ID,
            patient_uuid,
            repeater.domain,
            case_type=case_type,
        )
        if case:
            case_id = case.get_id

        elif error == LookupErrors.NotFound:
            # The encounter is for a patient that has not yet been imported
            patient = get_patient_by_uuid(repeater.requests, patient_uuid)
            owner = get_one_commcare_user_at_location(repeater.domain, repeater.location_id)
            case_block = get_addpatient_caseblock(case_type, owner, patient, repeater)
            case_blocks.append(case_block)
            case_id = case_block.case_id

        else:
            _assert(
                error != LookupErrors.MultipleResults,
                'More than one case found matching unique OpenMRS UUID. '
                'domain: "{}". case external_id: "{}". repeater: "{}".'.format(
                    repeater.domain, patient_uuid, repeater.get_id
                )
            )
            return

        case_blocks.append(CaseBlock(
            case_id=case_id,
            create=False,
            update=case_property_updates,
        ))
        submit_case_blocks(
            [cb.as_string() for cb in case_blocks],
            repeater.domain,
            xmlns=XMLNS_OPENMRS,
            device_id=OPENMRS_ATOM_FEED_DEVICE_ID + repeater.get_id,
        )
