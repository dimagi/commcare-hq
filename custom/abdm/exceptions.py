from rest_framework.exceptions import APIException
from rest_framework.response import Response

ERROR_CODE_REQUIRED = 'required'
ERROR_CODE_REQUIRED_MESSAGE = 'This field is required.'
ERROR_CODE_INVALID = 'invalid'
ERROR_FUTURE_DATE_MESSAGE = 'This field must be in future'
ERROR_PAST_DATE_MESSAGE = 'This field must be in past'


class ABDMErrorResponseFormatter:
    error_code_prefix = ''
    error_messages = {}

    def format_drf_response(self, response, error_details=True):
        """
        ABDM (M2/M3) has a different response body format which includes custom codes for standard errors.
        This modifies the response body format obtained by drf_standardized_errors to the required format.
        Used for standard frameworks errors like serializers, authentication, unhandled exceptions etc.
        Takes input as response returned by drf_standardized_errors.
        'keep_details' flag is used to decide on sending 'error'>'details' field.
        The field 'error'>'code' is created by appending 'error_code_prefix' to the response status code.
        Sample:
        Input Response Body with Status Code as 400:
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
        Output Response Body with `error_code_prefix` as `4`:
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
            data = {"error": {'code': int(f'{self.error_code_prefix}{response.status_code}')}}
            data['error']['message'] = self.error_messages.get(data['error']['code'])
            if error_details and response.status_code != 500:
                data['error']['details'] = response.data.get('errors', [])
            response.data = data
        return response

    def generate_custom_error_response(self, error_code, status_code=400, details_message=None, details_field=None):
        """
        Used for creating response for custom errors
        """
        data = {
            'error': {
                'code': error_code,
                'message': self.error_messages.get(error_code)
            }
        }
        if details_message or details_field:
            data['error']['details'] = [{
                'code': 'invalid',
                'detail': details_message or self.error_messages.get(error_code),
                'attr': details_field
            }]
        return Response(data=data, status=status_code)


class ABDMServiceUnavailable(APIException):
    status_code = 503
    default_detail = 'ABDM Service temporarily unavailable, try again later.'
    default_code = 'service_unavailable'


class ABDMGatewayError(APIException):
    status_code = 554
    default_detail = 'Error from Gateway'
    default_code = 'gateway_error'


class ABDMConfigurationError(Exception):
    pass
