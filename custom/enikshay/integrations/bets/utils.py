from __future__ import absolute_import
from corehq.motech.repeaters.const import RECORD_FAILURE_STATE, RECORD_PENDING_STATE
from corehq.motech.repeaters.dbaccessors import get_repeat_records_by_payload_id
from six.moves import map


def get_bets_location_json(location):
    response = {
        'name': location.name,
        'site_code': location.site_code,
        '_id': location.location_id,
        'location_id': location.location_id,
        'doc_type': 'Location',
        'domain': location.domain,
        'external_id': location.external_id,
        'is_archived': location.is_archived,
        'last_modified': location.last_modified.isoformat(),
        'latitude': float(location.latitude) if location.latitude else None,
        'longitude': float(location.longitude) if location.longitude else None,
        'location_type': location.location_type.name,
        'location_type_code': location.location_type.code,
        'lineage': location.lineage,
        'parent_location_id': location.parent_location_id,
    }

    parent = location.parent
    if parent:
        response['parent_site_code'] = parent.site_code
    else:
        response['parent_site_code'] = ''
    response['ancestors_by_type'] = {
        ancestor.location_type.code: ancestor.location_id
        for ancestor in location.get_ancestors()
    }
    response['metadata'] = {
        field: location.metadata.get(field) for field in
        ['is_test', 'tests_available', 'private_sector_org_id', 'nikshay_code', 'enikshay_enabled']
    }
    return response


def get_bets_user_json(domain, user):
    from custom.enikshay.integrations.bets.repeater_generators import (
        _get_district_location,
        BETSUserPayloadGenerator,
        get_national_number,
    )
    location = user.get_sql_location(domain)
    district_location = _get_district_location(location)
    org_id = (
        location.metadata.get('private_sector_org_id')
        or district_location.metadata.get('private_sector_org_id')
    )
    user_json = {
        "username": user.raw_username,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "default_phone_number": get_national_number(user.user_data.get("contact_phone_number")),
        "id": user._id,
        "phone_numbers": list(map(get_national_number, user.phone_numbers)),
        "email": user.email,
        "dtoLocation": district_location.location_id,
        "privateSectorOrgId": org_id,
        "resource_uri": "",
    }
    user_json['user_data'] = {
        field: user.user_data.get(field, "")
        for field in BETSUserPayloadGenerator.user_data_fields
    }
    return user_json


def queued_payload(domain, payload_id):
    records = get_repeat_records_by_payload_id(domain, payload_id)
    for record in records:
        if record.state in [RECORD_FAILURE_STATE, RECORD_PENDING_STATE]:
            # these states are "queued", i.e. they will send the latest version
            # of the payload at some point in the future
            return True
