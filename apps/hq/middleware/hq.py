from __future__ import absolute_import

from hq.models import ExtUser

class HqMiddleware(object):
    '''Middleware for CommCare HQ.  Right now the only thing this does is
       convert the request.user property into an ExtUser, if they exist.'''
    
    
    def process_request(self, request):
        if request.user:
            try:
                extuser = ExtUser.objects.get(id=request.user.id)
                # override the request.user property so we can call it 
                # easily within templates and default to the standard
                # "user" object when this fails. 
                request.user = extuser
                # also duplicate it as request.extuser so we can check
                # this property in our views. 
                request.extuser = extuser
            except Exception:
                # make sure the property is set either way to avoid 
                # having extraneous hasattr() calls.  Most likely
                # this was an ExtUser.DoesNotExist, but it could
                # be anything something else and we don't want to
                # fail hard in the middleware layer. 
                request.extuser = None
        else:
            # ditto exception block
            request.extuser = None
        return None
        
       
    
    