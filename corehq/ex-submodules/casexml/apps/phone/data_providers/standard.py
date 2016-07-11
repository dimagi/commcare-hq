from casexml.apps.phone import xml
from casexml.apps.phone.fixtures import generator


class TimedProvider(object):
    def __init__(self, timing_context):
        self.timing_context = timing_context


class RestoreDataProvider(TimedProvider):
    """
    Base class for things that gives data directly to a restore.
    """
    def get_elements(self, restore_state):
        raise NotImplementedError('Need to implement this method')


class FullResponseDataProvider(TimedProvider):
    """
    Base class for things that deal with their own response.
    """
    def __init__(self, timing_context, async_task=None):
        super(FullResponseDataProvider, self).__init__(timing_context)
        self.async_task = async_task

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
        yield xml.get_registration_element(restore_state.restore_user)


class FixtureElementProvider(RestoreDataProvider):
    """
    Gets any associated fixtures.
    """

    def get_elements(self, restore_state):
        # fixture block
        providers = generator.get_providers(
            restore_state.restore_user,
            restore_state.version,
        )
        for provider in providers:
            with self.timing_context(provider.__class__.__name__):
                elements = provider(
                    restore_state.restore_user,
                    restore_state.version,
                    restore_state.last_sync_log,
                    app=restore_state.params.app
                )
                for element in elements:
                    yield element
