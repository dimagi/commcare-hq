from corehq import Domain
from corehq.apps.commtrack.util import get_commtrack_location_id
from corehq.apps.locations.models import Location
from custom.m4change.constants import M4CHANGE_DOMAINS
from lxml import etree as ElementTree


def generator(user, version, case_sync_op=None, last_sync=None):
    if user.domain in M4CHANGE_DOMAINS:
        domain = Domain.get_by_name(user.domain)
        location_id = get_commtrack_location_id(user, domain)
        if location_id is not None:
            fixture = LocationFixtureProvider('user-locations', user, domain, location_id).to_fixture()
            if fixture is None:
                return []
            return [fixture]
        else:
            return []
    else:
        return []


class LocationFixtureProvider(object):
    def __init__(self, id, user, domain, location_id):
        self.id = id
        self.user = user
        self.domain = domain
        self.location_id = location_id

    def to_fixture(self):
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
            'user_id': self.user._id
        })

        locations_element = ElementTree.Element('locations')
        locations = []
        locations.append(Location.get(self.location_id))
        for location in locations:
            location_element = ElementTree.Element('location', attrib={
                'name': location.name,
                'id': location.get_id
            })
            locations_element.append(location_element)

        root.append(locations_element)
        return root

    def to_string(self):
        return ElementTree.tostring(self.to_fixture(), encoding="utf-8")
