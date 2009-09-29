from __future__ import absolute_import

from django.contrib.auth import authenticate
from hq.models import ExtUser
from hq.utils import get_dates
from hq.authentication import get_username_password

class HqMiddleware(object):
    '''Middleware for CommCare HQ.  Right now the only thing this does is
       convert the request.user property into an ExtUser, if they exist.'''
    
    
    def process_request(self, request):
        # the assumption here is that we will never have an ExtUser for AnonymousUser
        if request.user and not request.user.is_anonymous():
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
            request.extuser = None
            # attempt our custom authentication only if regular auth fails
            # (and request.user == anonymousUser
            username, password = get_username_password(request)
            if username and password:
                request.extuser = authenticate(username=username, password=password)
            if request.extuser is not None:
                request.user = request.extuser
        # do the same for start and end dates.  at some point our views
        # can just start accessing these properties on the request assuming
        # our middleware is running  
        try:
            startdate, enddate = utils.get_dates(request)
            request.startdate = startdate
            request.enddate = enddate
        except Exception:
            request.startdate = None
            request.enddate = None
        return None
        
       
    
    