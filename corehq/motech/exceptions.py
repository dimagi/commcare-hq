class ConfigurationError(Exception):
    pass


class RemoteAPIError(Exception):
    pass


class JsonpathError(Exception):
    # jsonpath-ng (still) raises bare exceptions. This class is to
    # re-raise them, so we can be smarter about catching them.
    pass
