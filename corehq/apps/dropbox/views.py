from dropbox.client import DropboxOAuth2Flow

from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect, HttpResponse
from django.views.generic import View

from .utils import get_dropbox_auth_flow

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
            access_token, user_id, url_state = get_dropbox_auth_flow(request.session).finish(request.GET)
        except DropboxOAuth2Flow.BadRequestException, e:
            return HttpResponse(e, status=400)
        except DropboxOAuth2Flow.BadStateException:
            # Start the auth flow again.
            return HttpResponseRedirect(reverse(DropboxAuthInitiate.slug))
        except DropboxOAuth2Flow.CsrfException, e:
            return HttpResponse(e, status=403)
        except DropboxOAuth2Flow.NotApprovedException:
            return HttpResponseRedirect("/", status=400)
        except DropboxOAuth2Flow.ProviderException, e:
            return HttpResponse(e, status=403)
        request.session[DROPBOX_ACCESS_TOKEN] = access_token
        return HttpResponseRedirect(request.session.get('dropbox_next_url', '/'))
