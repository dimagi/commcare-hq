from django.conf import settings
from django.utils.deprecation import MiddlewareMixin

FORMPLAYER_SESSION_COOKIE_NAME = 'formplayer_session'


class CloudcareMiddleware(MiddlewareMixin):

    def process_response(self, request, response):
        self._set_formplayer_session_cookie(request, response)
        return response

    @staticmethod
    def _set_formplayer_session_cookie(request, response):
        """
        Set the formplayer_session cookie for sticky routing

        This is what makes all requests from a given user go to the same formplayer machine,
        along with https://git.io/JeDjr in commcare-cloud.

        For years previously, we routed based on the django sessionid, but that was brittle
        and the log out / log in cycle broke sticky routing because it changes the sessionid.
        Sticky routing with a high degree of consistency is essential to providing consistent
        phone-like state, and cracks in sticky routing lead to cases not being present in the
        formplayer local db when they should be and unintuitve behavior.
        """
        couch_user = getattr(request, 'couch_user', None)
        if couch_user:
            if request.COOKIES.get(FORMPLAYER_SESSION_COOKIE_NAME) != couch_user.user_id:
                response.set_cookie(FORMPLAYER_SESSION_COOKIE_NAME, couch_user.user_id,
                                    httponly=settings.SESSION_COOKIE_HTTPONLY)
