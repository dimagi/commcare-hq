class ConfigurationError(Exception):
    pass


class JsonpathError(Exception):
    # jsonpath_rw raises bare exceptions. This class is to re-raise
    # them, so we can be smarter about catching them.
    pass
