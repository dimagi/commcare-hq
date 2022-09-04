from tastypie.models import ApiKey
from tastypie.http import HttpUnauthorized
from tastypie.authentication import Authentication
from django.core.exceptions import ObjectDoesNotExist


class CustomApiKeyAuthentication(Authentication):

    def _unauthorized(self):
        return HttpUnauthorized()

    def is_authenticated(self, request, **kwargs):
        if not (request.META.get('HTTP_AUTHORIZATION')):
            return self._unauthorized()

        api_key = request.META['HTTP_AUTHORIZATION']
        key_auth_check = self.get_key(api_key, request)
        return key_auth_check

    def get_key(self, api_key, request):
        """
        Finding Api Key from UserProperties Model
        """
        try:
            return ApiKey.objects.get(key=api_key)
        except ObjectDoesNotExist:
            return self._unauthorized()
        return True