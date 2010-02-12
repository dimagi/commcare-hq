from __future__ import absolute_import
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from hq.authentication import get_username_password
from hq.utils import get_dates


try:
    from threading import local
except ImportError:
    from django.utils._threading_local import local
 
# this keeps a thread-local cache of stuff.  we're gonna stick some HQ
# stuff inside so that we have access to the user and domain from things
# that don't have a handle to the request object
_thread_locals = local()

def get_current_user():
    """Get the current (thread-specific) user"""
    return getattr(_thread_locals, 'user', None)

def get_current_domain():
    """Get the current (thread-specific) user"""
    return getattr(_thread_locals, 'domain', None)

class HqMiddleware(object):
    '''Middleware for CommCare HQ.  Right now the only thing this does is
       set some stuff in the thread locals (user and domain) if they exist
       as well as do some custom authentication for unsalted passwords and
       set convenience accessors for passed in dates in urlparams.'''
    
    def process_request(self, request):
        _thread_locals.user = getattr(request, 'user', None)
        if request.user and not request.user.is_anonymous():
            self._set_local_vars(request, request.user)
        else:
            # attempt our custom authentication only if regular auth fails
            # (and request.user == anonymousUser
            username, password = get_username_password(request)
            if username and password:
                user = authenticate(username=username, password=password)
                if user is not None:
                    request.user = user
                    self._set_local_vars(request, user)
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
    
    def _set_local_vars(self, request, user):
        """Sets the User and Domain objects in the threadlocals, if
           they exist"""
        try: 
            # set the domain in the thread locals 
            # so it can be accessed in places other
            # than views. 
            _thread_locals.domain = request.user.selected_domain
        except Exception:
            # likely means that there's no selected user or
            # domain, just let it go.
            pass
    