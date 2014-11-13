class FixtureException(Exception):
    pass


class FixtureDownloadError(FixtureException):
    pass


class FixtureUploadError(FixtureException):
    pass


class DuplicateFixtureTagException(FixtureUploadError):
    pass


class ExcelMalformatException(FixtureUploadError):
    pass


class FixtureAPIException(Exception):
    pass


class FixtureTypeCheckError(Exception):
    pass


class FixtureVersionError(Exception):
    pass




