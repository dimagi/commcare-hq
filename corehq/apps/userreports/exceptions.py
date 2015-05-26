

class UserReportsError(Exception):
    pass


class BadSpecError(UserReportsError):
    pass


class UserQueryError(UserReportsError):
    pass


class TableRebuildError(UserReportsError):
    pass
