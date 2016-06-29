from .standard import *
from .case import *


def get_element_providers(timing_context):
    """
    Get restore providers which contribute directly to the XML.
    """
    # note that ordering matters in this list as this is the order that the items
    # will appear in the XML, and have access to the RestoreState object
    return [
        SyncElementProvider(timing_context),
        RegistrationElementProvider(timing_context),
        FixtureElementProvider(timing_context),
    ]


def get_full_response_providers(timing_context, async_task=None):
    """
    Get restore providers that return their own fully formed responses

    They can optionally take an async task to update progress
    """
    return [
        CasePayloadProvider(timing_context, async_task),
    ]
