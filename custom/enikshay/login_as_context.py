from corehq.apps.locations.models import SQLLocation


def get_enikshay_login_as_context(user):
    location = get_linked_location(user)
    return {
        'linked_location': location,
        'district': get_district(location),
        'usertype_display': get_usertype_display(user.user_data.get('usertype')),
    }


def get_usertype_display(usertype):
    return {
        'pac': 'AYUSH / Other Provider',
        'pcp': 'MBBS Provider',
        'pcc-chemist': 'Chemist',
        'plc': 'Lab',
        'ps-fieldstaff': 'Field Staff',
    }.get(usertype, usertype)


def get_linked_location(user):
    location = None
    linked_location_id = user.user_data.get('linked_location_id')
    if linked_location_id:
        try:
            location = SQLLocation.objects.get(domain=user.domain, location_id=linked_location_id)
        except SQLLocation.DoestNotExist:
            pass
    if not location:
        location = user.sql_location

    return location


def get_district(location):
    if location:
        return get_closest_dto_above_location(location)


def get_closest_dto_above_location(location):
    try:
        return location.get_ancestors(include_self=True).get(location_type__code='dto')
    except SQLLocation.DoesNotExist:
        return None
