from casexml.apps.case.exceptions import CommCareCaseError
from corehq.util.datadog.gauges import datadog_counter
from corehq.util.datadog.metrics import DATE_OPENED_CASEBLOCK_ERROR_COUNT


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


class DateOpenedBugException(RestoreException):
    """We added a date_opened block to every case being synced on July 19, 2016.

    This caused mobile to crash when accessing the caselist because it was
    expecting a different date format.
    http://manage.dimagi.com/default.asp?232602

    This is solved by forcing a 412 for those users.
    """
    message = "Cases were sent down with a date_opened block that had bad time information"

    def __init__(self, user, synclog_id, **kwargs):
        super(DateOpenedBugException, self).__init__(user, **kwargs)
        details = [
            u"domain:{}".format(user.domain),
            u"username:{}".format(user.username),
            u"user_id:{}".format(user.user_id),
            u"last_synclog_id:{}".format(synclog_id)
        ]
        datadog_counter(DATE_OPENED_CASEBLOCK_ERROR_COUNT, tags=details)


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
