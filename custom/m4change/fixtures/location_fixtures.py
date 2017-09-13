from casexml.apps.phone.fixtures import FixtureProvider
from corehq.apps.locations.models import get_location
from custom.m4change.constants import M4CHANGE_DOMAINS
from lxml import etree as ElementTree


class LocationFixtureProvider(FixtureProvider):
    id = 'user-locations'

    def __call__(self, restore_state):
        restore_user = restore_state.restore_user

        if restore_user.domain in M4CHANGE_DOMAINS:
            location_id = restore_user.get_commtrack_location_id()
            if location_id is not None:
                fixture = self.get_fixture(restore_user, location_id)
                if fixture is None:
                    return []
                return [fixture]
            else:
                return []
        else:
            return []

    def get_fixture(self, restore_user, location_id):
        """
        Generate a fixture representation of all locations available to the user
        <fixture id="fixture:user-locations" user_id="4ce8b1611c38e953d3b3b84dd3a7ac18">
            <locations>
                <location name="Location 1" id="1039d1611c38e953d3b3b84ddc01d93"
                <!-- ... -->
            </locations>
        </fixture>
        """
        root = ElementTree.Element('fixture', {
            'id': self.id,
            'user_id': restore_user.user_id
        })

        locations_element = ElementTree.Element('locations')
        location = get_location(location_id)
        location_element = ElementTree.Element('location', {
            'name': location.name,
            'id': location.location_id
        })
        locations_element.append(location_element)

        root.append(locations_element)
        return root

generator = LocationFixtureProvider()
