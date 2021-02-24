class ServiceProviderCertificateError(Exception):
    pass


class SsoAuthenticationError(Exception):

    def __init__(self, message):
        self.message = message
