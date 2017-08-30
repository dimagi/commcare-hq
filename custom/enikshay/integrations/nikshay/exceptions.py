class NikshayAPIError(Exception):
    pass


class NikshayResponseException(NikshayAPIError):
    pass


class NikshayHealthEstablishmentInvalidUpdate(Exception):
    pass
