from casexml.apps.phone import xml
from casexml.apps.phone.fixtures import generator


class RestoreDataProvider(object):
    """
    Base class for anything that gives data to a restore.
    """

    def get_elements(self, restore_state):
        raise NotImplementedError('Need to implement this method')

class SyncElementProvider(RestoreDataProvider):
    """
    Gets the initial sync element.
    """
    def get_elements(self, restore_state):
        yield xml.get_sync_element(restore_state.current_sync_log._id)


class RegistrationElementProvider(RestoreDataProvider):
    """
    Gets the registration XML
    """
    def get_elements(self, restore_state):
        yield xml.get_registration_element(restore_state.user)


class FixtureElementProvider(RestoreDataProvider):
    """
    Gets any associated fixtures.
    """
    def get_elements(self, restore_state):
        # fixture block
        for fixture in generator.get_fixtures(
            restore_state.user,
            restore_state.params.version,
            restore_state.last_sync_log
        ):
            yield fixture


def get_restore_providers():
    """
    Get all restore providers. This can be smarter in the future.
    """
    # note that ordering matters in this list as this is the order that the items
    # will appear in the XML, and have access to the RestoreState object
    return [
        SyncElementProvider(),
        RegistrationElementProvider(),
        FixtureElementProvider(),
    ]
