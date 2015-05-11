

class InvalidSyncLogException(Exception):
    pass


class MissingSyncLog(InvalidSyncLogException):
    pass


class SyncLogUserMismatch(InvalidSyncLogException):
    pass
