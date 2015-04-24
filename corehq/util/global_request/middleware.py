from .api import set_request


class GlobalRequestMiddleware(object):

    def process_request(self, request):
        set_request(request)

    def process_response(self, request, response):
        if hasattr(request, 'domain'):
            self.remember_domain_visit(request, response)
        return response

    def remember_domain_visit(self, request, response):
        last_visited_domain = request.session.get('last_visited_domain')
        if last_visited_domain != request.domain:
            request.session['last_visited_domain'] = request.domain
