from .api import set_request


class GlobalRequestMiddleware(object):

    def process_request(self, request):
        set_request(request)

    def process_response(self, request, response):
        return response
