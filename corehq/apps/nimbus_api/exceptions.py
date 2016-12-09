class NimbusAPIException(Exception):
    pass


class NimbusRequestException(NimbusAPIException):
    def __init__(self, status_code):
        self.status_code = status_code
