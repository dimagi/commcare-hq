class Dhis2Exception(Exception):
    """
    It's not us, it's them
    """
    pass


class BadTrackedEntityInstanceID(Dhis2Exception):
    """
    A Tracked Entity instance ID was not found on the server that (is
    believed to have) issued it.
    """
    pass


class MultipleInstancesFound(Dhis2Exception):
    """
    Unable to select a corresponding Tracked Entity instance from
    multiple available candidates.
    """
    pass
