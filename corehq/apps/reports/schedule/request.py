
class RequestProcessor(object):
    def preprocess(self, request, **vals):
        """
        Kind of like a middleware. If you need to preprocess the request 
        do it here"""
        for key, val in vals.items():
            setattr(request, key, val)

