from casexml.apps.phone import xml
from casexml.apps.phone.fixtures import generator


class RestoreDataProvider(object):
    """
    Base class for things that gives data directly to a restore.
    """

    def get_elements(self, restore_state):
        raise NotImplementedError('Need to implement this method')


class LongRunningRestoreDataProvider(object):
    """
    Base class for things that gives data optionally asynchronously to a restore.
    """

    def get_response(self, restore_state):
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


class FixtureElementMixin(object):
    """
    Gets any associated fixtures.
    """
    def __init__(self, fixture_group):
        self.fixture_group = fixture_group

    def get_elements(self, restore_state):
        # fixture block
        for fixture in generator.get_fixtures(
            restore_state.user,
            restore_state.version,
            restore_state.last_sync_log,
            group=self.fixture_group
        ):
            yield fixture


class FixtureElementProvider(FixtureElementMixin, RestoreDataProvider):
    pass


class FixtureResponseProvider(FixtureElementMixin, LongRunningRestoreDataProvider):
    def get_response(self, restore_state):
        response = restore_state.restore_class()
        response.extend(self.get_elements(restore_state))
        return response