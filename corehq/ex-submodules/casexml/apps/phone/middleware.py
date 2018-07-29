from __future__ import absolute_import
from __future__ import unicode_literals
from django.utils.deprecation import MiddlewareMixin

LAST_SYNCTOKEN_HEADER = "HTTP_X_COMMCAREHQ_LASTSYNCTOKEN"


class SyncTokenMiddleware(MiddlewareMixin):
    """
    Middleware to support submitting the sync token with phone
    submissions
    """

    def process_request(self, request):
        request.last_sync_token = request.META[LAST_SYNCTOKEN_HEADER] \
            if LAST_SYNCTOKEN_HEADER in request.META \
            else None
