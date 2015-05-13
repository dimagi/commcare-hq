from .standard import *
from .case import *


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


def get_long_running_providers():
    """
    Get restore providers that are expected to run for a long time.

    These have different API semantics to be able to support asynchronous calls in hte future.
    """
    return [CasePayloadProvider()]
