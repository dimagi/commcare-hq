def get_bets_location_json(location):
    response = location.to_json()
    parent = location.parent
    if parent:
        response['parent_site_code'] = parent.site_code
    else:
        response['parent_site_code'] = ''
    response['ancestors_by_type'] = {
        ancestor.location_type.name: ancestor.location_id
        for ancestor in location.get_ancestors()
    }
    return response
