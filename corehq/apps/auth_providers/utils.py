class SessionAuthManager(object):
    def __init__(self, request):
        self.request = request
        self._auth_providers = self._initialize_session_properties()

    def authenticate(self, auth_provider_id):
        self._auth_providers.add(auth_provider_id)
        self.request.session.modified = True

    def revoke_auth(self, auth_provider_id):
        self._auth_providers.remove(auth_provider_id)
        self.request.session.modified = True

    def has_auth(self, acceptable_auth_provider_ids):
        return set(acceptable_auth_provider_ids) & self._auth_providers

    def _initialize_session_properties(self):
        if AUTH_PROVIDERS not in self.request.session:
            self.request.session[AUTH_PROVIDERS] = set()
            self.request.session.modified = True
        return self.request.session[AUTH_PROVIDERS]


AUTH_PROVIDERS = 'auth_providers'
