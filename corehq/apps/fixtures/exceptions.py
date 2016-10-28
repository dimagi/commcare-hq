class FixtureException(Exception):
    pass


class FixtureDownloadError(FixtureException):
    pass


class FixtureUploadError(FixtureException):
    pass


class DuplicateFixtureTagException(FixtureUploadError):
    pass


class ExcelMalformatException(FixtureUploadError):
    def __init__(self, errors):
        self.errors = errors


class FixtureTypeCheckError(Exception):
    pass


class FixtureVersionError(Exception):
    pass




