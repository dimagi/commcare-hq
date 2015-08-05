from casexml.apps.case.exceptions import CommCareCaseError


class RestoreException(ValueError, CommCareCaseError):
    """
    For stuff that goes wrong during restore
    """
    message = "unknown problem during OTA restore"


class BadStateException(RestoreException):
    """
    Case state hash inconsistencies
    """
    message = "Phone case list is inconsistant with server's records."

    def __init__(self, expected, actual, case_ids, **kwargs):
        super(BadStateException, self).__init__(**kwargs)
        self.expected = expected
        self.actual = actual
        self.case_ids = case_ids

    def __str__(self):
        return "Phone state hash mismatch. Expected %s but was %s. Cases: [%s]" % \
            (self.expected, self.actual, ", ".join(self.case_ids))


class BadVersionException(RestoreException):
    """
    Bad ota version
    """
    message = "Bad version number submitted during sync."


class InvalidSyncLogException(Exception):
    pass


class MissingSyncLog(InvalidSyncLogException):
    pass


class SyncLogUserMismatch(InvalidSyncLogException):
    pass


class IncompatibleSyncLogType(InvalidSyncLogException):
    pass
