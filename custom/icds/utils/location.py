from corehq.apps.locations.models import SQLLocation


def find_test_state_locations():
    test_locations = set()
    for location in SQLLocation.active_objects.filter(location_type__code='state', domain='icds-cas'):
        if location.metadata.get('is_test_location') == 'test':
            test_locations.add(location)
    return test_locations


def find_test_awc_location_ids(domain):
    test_locations = set()
    for location in SQLLocation.active_objects.filter(location_type__code='state', domain=domain):
        if location.metadata.get('is_test_location') == 'test':
            test_locations.update(
                location.get_descendants(include_self=True).
                filter(location_type__code='awc').values_list('location_id', flat=True)
            )
    return test_locations
