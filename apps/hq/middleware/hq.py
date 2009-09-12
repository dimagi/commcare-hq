from __future__ import absolute_import

from hq.models import ExtUser

class HqMiddleware(object):
    '''Middleware for CommCare HQ.  Right now the only thing this does is
       convert the request.user property into an ExtUser, if they exist.'''
    
    
    def process_request(self, request):
        if request.user:
            try:
                extuser = ExtUser.objects.get(id=request.user.id)
                request.user = extuser
            except:
                pass
        return None
        
       
    
    