import logging
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.core.urlresolvers import reverse
from corehq.apps.app_manager.models import AppError, get_app


def safe_download(f):
    """
    Makes a download safe, by trapping any app errors and redirecting
    to a default landing page.
    Assumes that the first 2 arguments to the function after request are
    domain and app_id, or there are keyword arguments with those names
    """
    def _safe_download(req, *args, **kwargs):
        domain = args[0] if len(args) > 0 else kwargs["domain"]
        app_id = args[1] if len(args) > 1 else kwargs["app_id"]
        latest = True if req.GET.get('latest') == 'true' else False
        
        try:
            req.app = get_app(domain, app_id, latest=latest)
            return f(req, *args, **kwargs)
        except AppError, e:
            logging.exception(e)
            messages.error(req, "Problem downloading file: %s" % e)
            return HttpResponseRedirect(reverse("corehq.apps.app_manager.views.view_app", args=[domain,app_id]))
    return _safe_download
    