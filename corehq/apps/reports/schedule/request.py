
class RequestProcessor(object):
    def preprocess(self, request):
        """
        Kind of like a middleware. If you need to preprocess the request 
        do it here"""
        pass

class DictRequestProcessor(object):
    
    def __init__(self, **vals):
        self._dict = vals
    
    def preprocess(self, request):
        for key, val in self._dict.items():
            setattr(request, key, val)
    
class BasicRequestProcessor(DictRequestProcessor):
    
    def __init__(self, user, **vals):
        super(BasicRequestProcessor, self).__init__(**vals)
        self._dict["user"] = user
        #self._dict["domain"] = domain

