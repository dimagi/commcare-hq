""" 
MORE INFO AT: http://code.google.com/p/django-rest-interface/wiki/RestifyDjango
"""

from django.http import HttpResponse
from django.utils.translation import ugettext as _
import md5, time, random
from hq.authentication import get_username_password, get_auth_dict

def djangouser_auth(username, password):
    """
    Check username and password against
    django.contrib.auth.models.User
    """
    from django.contrib.auth.models import User
    try:
        user = User.objects.get(username=username)
        if user.check_password(password):
            return True
        else:
            return False
    except User.DoesNotExist:
        return False

class Authentication(object):
    """
    Authentication interface
    """
    def is_authenticated(self, request):
        raise NotImplementedError

    def challenge_headers(self):
        raise NotImplementedError

class NoAuthentication(Authentication):
    """
    No authentication: Permit every request.
    """
    def is_authenticated(self, request):
        return True

    def challenge_headers(self):
        return {}

class HttpBasicAuthentication(Authentication):
    """
    HTTP/1.0 basic authentication.
    """    
    def __init__(self, authfunc=djangouser_auth, realm=_('Restricted Access')):
        """
        authfunc:
            A user-defined function which takes a username and
            password as its first and second arguments respectively
            and returns True if the user is authenticated
        realm:
            An identifier for the authority that is requesting
            authorization
        """
        self.realm = realm
        self.authfunc = authfunc
    
    def challenge_headers(self):
        """
        Returns the http headers that ask for appropriate
        authorization.
        """
        return {'WWW-Authenticate' : 'Basic realm="%s"' % self.realm}
    
    def is_authenticated(self, request):
        """
        Checks whether a request comes from an authorized user.
        """
        if not request.META.has_key('HTTP_AUTHORIZATION'):
            return False
        (authmeth, auth) = request.META['HTTP_AUTHORIZATION'].split(' ', 1)
        if authmeth.lower() != 'basic':
            return False
        auth = auth.strip().decode('base64')
        username, password = auth.split(':', 1)
        return self.authfunc(username=username, password=password)

def digest_password(realm, username, password):
    """
    Construct the appropriate hashcode needed for HTTP digest
    """
    return md5.md5("%s:%s:%s" % (username, realm, password)).hexdigest()

class HttpDigestAuthentication(Authentication):
    """
    HTTP/1.1 digest authentication (RFC 2617).
    Uses code from the Python Paste Project (MIT Licence).
    """    
    def __init__(self, authfunc, realm=_('Restricted Access')):
        """
        authfunc:
            A user-defined function which takes a username and
            a realm as its first and second arguments respectively
            and returns the combined md5 hash of username,
            authentication realm and password.
        realm:
            An identifier for the authority that is requesting
            authorization
        """
        self.realm = realm
        self.authfunc = authfunc
        self.nonce    = {} # prevention of replay attacks

    def get_auth_response(self, http_method, fullpath, username, nonce, realm, qop, cnonce, nc):
        """
        Returns the server-computed digest response key.
        
        http_method:
            The request method, e.g. GET
        username:
            The user to be authenticated
        fullpath:
            The absolute URI to be accessed by the user
        nonce:
            A server-specified data string which should be 
            uniquely generated each time a 401 response is made
        realm:
            A string to be displayed to users so they know which 
            username and password to use
        qop:
            Indicates the "quality of protection" values supported 
            by the server.  The value "auth" indicates authentication.
        cnonce:
            An opaque quoted string value provided by the client 
            and used by both client and server to avoid chosen 
            plaintext attacks, to provide mutual authentication, 
            and to provide some message integrity protection.
        nc:
            Hexadecimal request counter
        """
        ha1 = self.authfunc(realm, username)
        ha2 = md5.md5('%s:%s' % (http_method, fullpath)).hexdigest()
        if qop:
            chk = "%s:%s:%s:%s:%s:%s" % (ha1, nonce, nc, cnonce, qop, ha2)
        else:
            chk = "%s:%s:%s" % (ha1, nonce, ha2)
        computed_response = md5.md5(chk).hexdigest()
        return computed_response
    
    def challenge_headers(self, stale=''):
        """
        Returns the http headers that ask for appropriate
        authorization.
        """
        nonce  = md5.md5(
            "%s:%s" % (time.time(), random.random())).hexdigest()
        opaque = md5.md5(
            "%s:%s" % (time.time(), random.random())).hexdigest()
        self.nonce[nonce] = None
        parts = {'realm': self.realm, 'qop': 'auth',
                 'nonce': nonce, 'opaque': opaque }
        if stale:
            parts['stale'] = 'true'
        head = ", ".join(['%s="%s"' % (k, v) for (k, v) in parts.items()])
        return {'WWW-Authenticate':'Digest %s' % head}
    
    def is_authenticated(self, request):
        """
        Checks whether a request comes from an authorized user.
        """
        
        # Make sure the request is a valid HttpDigest request
        if not request.META.has_key('HTTP_AUTHORIZATION'):
            return False
        fullpath = request.META['SCRIPT_NAME'] + request.META['PATH_INFO']
        (authmeth, auth) = request.META['HTTP_AUTHORIZATION'].split(" ", 1)
        if authmeth.lower() != 'digest':
            return False
        
        # Extract auth parameters from request
        amap = get_auth_dict(auth)
        try:
            username = amap['username']
            authpath = amap['uri']
            nonce    = amap['nonce']
            realm    = amap['realm']
            response = amap['response']
            assert authpath.split("?", 1)[0] in fullpath
            assert realm == self.realm
            qop      = amap.get('qop', '')
            cnonce   = amap.get('cnonce', '')
            nc       = amap.get('nc', '00000000')
            if qop:
                assert 'auth' == qop
                assert nonce and nc
        except:
            return False

        # Compute response key    
        computed_response = self.get_auth_response(request.method, fullpath, username, nonce, realm, qop, cnonce, nc)
        
        # Compare server-side key with key from client
        # Prevent replay attacks
        if not computed_response or computed_response != response:
            if nonce in self.nonce:
                del self.nonce[nonce]
            return False
        pnc = self.nonce.get(nonce,'00000000')
        if nc <= pnc:
            if nonce in self.nonce:
                del self.nonce[nonce]
            return False # stale = True
        self.nonce[nonce] = nc
        return True


class HQAuthentication(Authentication):
    """
    Custom CommCare Authentication
    
    Takes HTTP headers like:
    Authorization: CommCare username="brian",
                            password=md5(username:password)
    """
    def __init__(self, authfunc=djangouser_auth, realm=_('Restricted Access')):
        """
        authfunc:
            A user-defined function which takes a username and
            password as its first and second arguments respectively
            and returns True if the user is authenticated
        realm:
            An identifier for the authority that is requesting
            authorization
        """
        self.realm = realm
        self.authfunc = authfunc
    
    def challenge_headers(self):
        """
        Returns the http headers that ask for appropriate
        authorization.
        """
        return {'WWW-Authenticate' : 'Basic realm="%s"' % self.realm}
    
    def is_authenticated(self, request):
        username, password = get_username_password(request)
        if username and password:
            return self.authfunc(username=username, password=password)
        return False

