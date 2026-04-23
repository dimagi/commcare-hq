

class DocumentNotFoundError(Exception):
    pass


class DocumentDeletedError(DocumentNotFoundError):
    pass


class DocumentMissingError(DocumentNotFoundError):
    pass


class DocumentMismatchError(Exception):
    pass
