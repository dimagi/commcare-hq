""" Authentication Backend for CommCaer HQ """
from django.conf import settings
from hq.models import ExtUser

class HQBackend:
    """
    Authenticate against extuser.unsalted_password 
    (given username and sha1 of username:password)
    """
    def authenticate(self, username=None, password=None):        
        try:
            user = ExtUser.objects.get(username=username)
            if user.unsalted_password == password:
                return user
            else:
                return None
        except ExtUser.DoesNotExist:
            return None        

    def get_user(self, user_id):
        try:
            return ExtUser.objects.get(pk=user_id)
        except ExtUser.DoesNotExist:
            return None
        
def get_username_password(request):
    """
    Checks whether a request comes from an authorized user.
    """
    try:
        if not request.META.has_key('HTTP_AUTHORIZATION'):
            return (None, None)
        (authmeth, auth) = request.META['HTTP_AUTHORIZATION'].split(" ", 1)
        if authmeth.lower() != 'hq':
            return (None, None)
        
        # Extract auth parameters from request
        amap = get_auth_dict(auth)  
    except Exception, e:
        # catch all errors (most likely poorly formatted POST's)
        # so we do not fail hard in the auth middleware
        return (None, None)
    try:
        username = amap['username']
        password = amap['password']
    except:
        return (None, None)
    return ( username, password )

def get_auth_dict(auth_string):
    """
    Splits WWW-Authenticate and HTTP_AUTHORIZATION strings
    into a dictionaries, e.g.
    {
        nonce  : "951abe58eddbb49c1ed77a3a5fb5fc2e"',
        opaque : "34de40e4f2e4f4eda2a3952fd2abab16"',
        realm  : "realm1"',
        qop    : "auth"'
    }
    """
    amap = {}
    for itm in auth_string.split(", "):
        (k, v) = [s.strip() for s in itm.split("=", 1)]
        amap[k] = v.replace('"', '')
    return amap