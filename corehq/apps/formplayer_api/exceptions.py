class FormplayerAPIException(Exception):
    pass


class FormplayerRequestException(FormplayerAPIException):
    def __init__(self, status_code):
        self.status_code = status_code


class FormplayerResponseException(FormplayerAPIException):
    def __init__(self, response_json):
        self.response_json = response_json
