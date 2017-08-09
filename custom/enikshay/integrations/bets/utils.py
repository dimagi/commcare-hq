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
        ancestor.location_type.name: ancestor.location_id
        for ancestor in location.get_ancestors()
    }
    response['metadata'] = {
        field: location.metadata.get(field) for field in
        ['is_test', 'tests_available', 'private_sector_org_id', 'nikshay_code', 'enikshay_enabled']
    }
    return response
