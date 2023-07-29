from rest_framework.exceptions import APIException


class ABDMErrorResponseFormatter:
    error_code_prefix = ''
    error_messages = {}

    def format_response(self, response, error_details=True):
        """
        ABDM has a different response body format which includes custom codes for standard errors.
        This updates the response body format obtained by drf_standardized_errors to the required format.
        Use this method for standard HTTP errors such as 400, 404, 500 etc.
        'keep_details' flag is used to decide on sending 'error'>'details' field
        Sample:
        Input Response Body:
        {
          "type": "validation_error",
          "errors": [
            {
              "code": "required",
              "detail": "This field is required.",
              "attr": "purpose.code"
            }
          ]
        }
        Output Response Body:
        {
            "error": {
                "code": 4400,
                "message": "Required attributes not provided or Request information is not as expected",
                "details": [
                    {
                        "code": "required",
                        "detail": "This field is required.",
                        "attr": "purpose.code"
                    }
                ]
            }
        }

        """
        if response is not None:
            if response.status_code == 500:
                del response.data['errors']
            data = {"error": {'code': int(f'{self.error_code_prefix}{response.status_code}')}}
            data['error']['message'] = self.error_messages.get(data['error']['code'])
            if error_details:
                data['error']['details'] = response.data.get('errors', [])
            response.data = data
        return response


class ABDMServiceUnavailable(APIException):
    status_code = 503
    default_detail = 'ABDM Service temporarily unavailable, try again later.'
    default_code = 'service_unavailable'


class ABDMGatewayError(APIException):
    status_code = 554
    default_detail = 'Error from Gateway'
    default_code = 'gateway_error'


class ABDMConfigurationException(Exception):
    pass
