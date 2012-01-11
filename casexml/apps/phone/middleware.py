
LAST_SYNCTOKEN_HEADER = "HTTP_X_COMMCAREHQ_LASTSYNCTOKEN"

class SyncTokenMiddleware(object):
    """
    Middleware to support submitting the sync token with phone
    submissions
    """
    
    def __init__(self):        
        pass

    def process_request(self, request):
        request.last_sync_token = request.META[LAST_SYNCTOKEN_HEADER] \
            if LAST_SYNCTOKEN_HEADER in request.META \
            else None
