

class UnknownDocumentStore(ValueError):
    pass


class MissingMetaInformationError(Exception):
    pass


class UnavailableKafkaOffset(Exception):
    pass
