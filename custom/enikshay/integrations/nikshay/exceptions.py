class NikshayAPIError(Exception):
    pass


class NikshayResponseException(NikshayAPIError):
    pass


class NikshayLocationNotFound(NikshayAPIError):
    pass


class NikshayCodeNotFound(NikshayAPIError):
    pass
