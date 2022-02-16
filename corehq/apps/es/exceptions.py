class ESError(Exception):
    pass


class ESRegistryError(ESError):
    pass


class ESShardFailure(ESError):
    pass
