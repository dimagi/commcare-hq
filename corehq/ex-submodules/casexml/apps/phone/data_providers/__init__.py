from __future__ import unicode_literals
from .standard import *
from .case import *


def get_element_providers(timing_context):
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
        FixtureElementProvider(timing_context),
    ]


def get_async_providers(timing_context, async_task=None):
    """
    Get restore providers that return their own fully formed responses

    They can optionally take an async task to update progress
    """
    return [
        CasePayloadProvider(timing_context, async_task),
    ]
