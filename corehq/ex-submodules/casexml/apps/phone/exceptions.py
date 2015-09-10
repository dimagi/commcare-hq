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

    def __init__(self, server_hash, phone_hash, case_ids, **kwargs):
        super(BadStateException, self).__init__(**kwargs)
        self.server_hash = server_hash
        self.phone_hash = phone_hash
        self.case_ids = case_ids

    def __str__(self):
        return "Phone state hash mismatch. Server hash: %s, Phone hash: %s. # of cases: [%s]" % \
            (self.server_hash, self.phone_hash, len(self.case_ids))


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


class OwnershipCleanlinessError(Exception):
    pass


class InvalidDomainError(OwnershipCleanlinessError):
    pass


class InvalidOwnerIdError(OwnershipCleanlinessError):
    pass


class SyncLogCachingError(Exception):
    pass
