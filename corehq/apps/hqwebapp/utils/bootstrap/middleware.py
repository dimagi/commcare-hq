from corehq.apps.hqwebapp.utils.bootstrap import clear_bootstrap_version


class ThreadLocalCleanupMiddleware:
    '''
    Middleware to ensure that any bootstrap variables added to the thread via functions
    within corehq.apps.hqwebapp.utils.bootstrap are cleared before the thread is re-used
    '''
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            response = self.get_response(request)
            return response
        finally:
            clear_bootstrap_version()
