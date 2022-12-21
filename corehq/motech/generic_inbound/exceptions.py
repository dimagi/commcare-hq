class GenericInboundApiError(Exception):
    pass


class GenericInboundUserError(Exception):
    pass


class GenericInboundRequestFiltered(GenericInboundApiError):
    pass


class GenericInboundValidationError(GenericInboundApiError):
    def __init__(self, errors):
        self.errors = errors

    def __str__(self):
        return '\n'.join(f"{e['name']}: {e['message']}" for e in self.errors)
