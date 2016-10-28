class FixtureException(Exception):
    pass


class FixtureDownloadError(FixtureException):
    pass


class FixtureAPIRequestError(FixtureException):
    pass


class FixtureUploadError(FixtureException):
    def __init__(self, errors):
        self.errors = errors


class FixtureTypeCheckError(Exception):
    pass


class FixtureVersionError(Exception):
    pass
