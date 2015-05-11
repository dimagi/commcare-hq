from casexml.apps.phone import xml
from casexml.apps.phone.fixtures import generator


class RestoreDataProvider(object):
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
    Get restore providers which contribute directly to the XML.
    """
    # note that ordering matters in this list as this is the order that the items
    # will appear in the XML, and have access to the RestoreState object
    return [
        SyncElementProvider(),
        RegistrationElementProvider(),
        FixtureElementProvider(),
    ]


class LongRunningRestoreDataProvider(object):
    """
    Base class for things that gives data optionally asynchronously to a restore.
    """

    def get_response(self, restore_state):
        raise NotImplementedError('Need to implement this method')


class CasePayloadProvider(LongRunningRestoreDataProvider):
    """
    Long running restore provider responsible for generating the case and stock payloads.
    """
    def get_response(self, restore_state):
        # todo: need to split these out more
        from casexml.apps.phone.restore import get_case_payload_batched, StockSettings

        if restore_state.domain and restore_state.domain.commtrack_settings:
            stock_settings = restore_state.domain.commtrack_settings.get_ota_restore_settings()
        else:
            stock_settings = StockSettings()

        case_response, num_batches = get_case_payload_batched(
            domain=restore_state.domain,
            stock_settings=stock_settings,
            version=restore_state.params.version,
            user=restore_state.user,
            last_synclog=restore_state.last_sync_log,
            new_synclog=restore_state.current_sync_log,
        )
        restore_state.provider_log['num_case_batches'] = num_batches
        return case_response


def get_long_running_providers():
    """
    Get restore providers that are expected to run for a long time.

    These have different API semantics to be able to support asynchronous calls in hte future.
    """
    return [CasePayloadProvider()]
