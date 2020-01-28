from corehq.apps.locations.models import SQLLocation


def find_test_state_locations():
    test_locations = set()
    for location in SQLLocation.active_objects.filter(location_type__code='state', domain='icds-cas'):
        if location.metadata.get('is_test_location') == 'test':
            test_locations.add(location)
    return test_locations
