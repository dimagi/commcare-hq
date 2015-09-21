from corehq.apps.domain.models import Domain
from corehq.apps.commtrack.util import get_commtrack_location_id
from corehq.apps.locations.models import Location
from custom.m4change.constants import M4CHANGE_DOMAINS
from lxml import etree as ElementTree


class LocationFixtureProvider(object):
    id = 'user-locations'

    def __call__(self, user, version, last_sync=None):
        if user.domain in M4CHANGE_DOMAINS:
            domain = Domain.get_by_name(user.domain)
            location_id = get_commtrack_location_id(user, domain)
            if location_id is not None:
                fixture = self.get_fixture(user, location_id)
                if fixture is None:
                    return []
                return [fixture]
            else:
                return []
        else:
            return []

    def get_fixture(self, user, location_id):
        """
        Generate a fixture representation of all locations available to the user
        <fixture id="fixture:user-locations" user_id="4ce8b1611c38e953d3b3b84dd3a7ac18">
            <locations>
                <location name="Location 1" id="1039d1611c38e953d3b3b84ddc01d93"
                <!-- ... -->
            </locations>
        </fixture>
        """
        root = ElementTree.Element('fixture', attrib={
            'id': self.id,
            'user_id': user._id
        })

        locations_element = ElementTree.Element('locations')
        location = Location.get(location_id)
        location_element = ElementTree.Element('location', attrib={
            'name': location.name,
            'id': location.get_id
        })
        locations_element.append(location_element)

        root.append(locations_element)
        return root

generator = LocationFixtureProvider()
