from casexml.apps.phone import xml
from casexml.apps.phone.fixtures import generator


def get_element_providers(timing_context, skip_fixtures=False):
    """
    Get restore providers which contribute directly to the XML.

    Each provider has a `get_elements(restore_state)` method which
    returns an iterable. Each item yielded by the returned iterable is
    either an `cElementTree.Element` object or a UTF-8 encoded string
    containing one or more XML elements. The string form must be wrapped
    in an enclosing XML element to construct valid XML.
    """
    # note that ordering matters in this list as this is the order that the items
    # will appear in the XML, and have access to the RestoreState object
    return [
        SyncElementProvider(timing_context),
        RegistrationElementProvider(timing_context),
        FixtureElementProvider(timing_context, skip_fixtures),
    ]


class TimedProvider(object):
    def __init__(self, timing_context):
        self.timing_context = timing_context


class RestoreDataProvider(TimedProvider):
    """
    Base class for things that gives data directly to a restore.
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
        yield xml.get_registration_element(restore_state.restore_user)


class FixtureElementProvider(RestoreDataProvider):
    """
    Gets any associated fixtures.
    """

    def __init__(self, timing_context, skip_fixtures):
        self._skip_fixtures = skip_fixtures
        super().__init__(timing_context)

    def get_elements(self, restore_state):
        # fixture block
        providers = generator.get_providers(
            restore_state.restore_user,
            version=restore_state.version,
        )
        for provider in providers:
            if self._skip_fixtures and not getattr(provider, 'ignore_skip_fixtures_flag', False):
                continue
            with self.timing_context('fixture:{}'.format(provider.id)):
                elements = provider(restore_state)
                for element in elements:
                    yield element
