from __future__ import absolute_import, unicode_literals

from django.http import HttpResponse
from django.views import View

from corehq.apps.domain.auth import get_username_and_password_from_request
from custom.icds.models import CCZHosting
from django.utils.decorators import method_decorator
from basicauth.decorators import basic_auth_required


# @method_decorator(basic_auth_required, name='dispatch')
class CCZDownloadView(View):
    template_name = 'file_hosting.html'

    def get(self, request, domain, identifier):
        import ipdb; ipdb.sset_trace()
        """
        Create model ICDSCCZFiles, find the one corresponding to state_name        
        """
        uname, passwd = get_username_and_password_from_request(request)
        if uname and passwd:
            return None

        # Either they did not provide an authorization header or
        # something in the authorization attempt failed. Send a 401
        # back to them to ask them to authenticate.
        response = HttpResponse(status=401)
        response['WWW-Authenticate'] = 'Basic realm="%s"' % ''
        return response
        file_hosting = CCZHosting.objects.get(identifier=identifier)
