class ABDMBaseResponseFormatter:
    error_code_prefix = ''
    error_messages = {}

    def format_response(self, response):
        """
        ABDM has a different response body format and codes for errors.
        """
        if response is not None:
            if response.status_code == 500:
                del response.data['errors']
            data = {
                "error":{
                    'code': int(f'{self.error_code_prefix}{response.status_code}'),
                }
            }
            data['error']['message'] = self.error_messages.get(data['error']['code'])
            data['error']['details'] = response.data.pop('errors', [])
            response.data = data
        return response
