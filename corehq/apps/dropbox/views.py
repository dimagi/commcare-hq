from __future__ import absolute_import
from __future__ import unicode_literals
from dropbox.oauth import (
    DropboxOAuth2Flow,
    BadRequestException,
    BadStateException,
    CsrfException,
    NotApprovedException,
    ProviderException,
)

from django.urls import reverse
from django.http import HttpResponseRedirect, HttpResponse
from django.views.generic import View

from .utils import get_dropbox_auth_flow, DROPBOX_CSRF_TOKEN

DROPBOX_ACCESS_TOKEN = 'dropbox_access_token'


class DropboxAuthInitiate(View):
    slug = 'dropbox_auth_initiate'

    def get(self, request, *args, **kwargs):
        authorize_url = get_dropbox_auth_flow(request.session).start()
        return HttpResponseRedirect(authorize_url)


class DropboxAuthCallback(View):
    slug = 'dropbox_auth_finalize'

    def get(self, request, *args, **kwargs):
        try:
            if DROPBOX_CSRF_TOKEN not in request.session:
                # workaround for library raising a KeyError in this situation.
                # http://manage.dimagi.com/default.asp?222132
                return HttpResponseRedirect(reverse(DropboxAuthInitiate.slug))
            else:
                oauth_result = get_dropbox_auth_flow(request.session).finish(request.GET)
        except BadRequestException as e:
            return HttpResponse(e, status=400)
        except BadStateException:
            # Start the auth flow again.
            return HttpResponseRedirect(reverse(DropboxAuthInitiate.slug))
        except CsrfException as e:
            return HttpResponse(e, status=403)
        except NotApprovedException:
            return HttpResponseRedirect("/", status=400)
        except ProviderException as e:
            return HttpResponse(e, status=403)
        request.session[DROPBOX_ACCESS_TOKEN] = oauth_result.access_token
        return HttpResponseRedirect(request.session.get('dropbox_next_url', '/'))
