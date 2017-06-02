def get_bets_location_json(location):
    response = location.to_json()
    response['ancestors_by_type'] = {
        ancestor.location_type.name: ancestor.location_id
        for ancestor in location.get_ancestors()
    }
    return response
