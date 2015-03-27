import logging
from functools import wraps
from django.contrib import messages
from django.http import HttpResponseRedirect, HttpResponse
from couchdbkit.exceptions import ResourceConflict
from django.views.decorators.http import require_POST
from django.core.urlresolvers import reverse
from corehq.apps.app_manager.exceptions import CaseError
from corehq.apps.app_manager.models import AppEditingError, get_app
from corehq.apps.users.decorators import require_permission
from corehq.apps.users.models import Permissions
from corehq.apps.domain.decorators import login_and_domain_required


def safe_download(f):
    """
    Makes a download safe, by trapping any app errors and redirecting
    to a default landing page.
    Assumes that the first 2 arguments to the function after request are
    domain and app_id, or there are keyword arguments with those names
    """
    @wraps(f)
    def _safe_download(request, *args, **kwargs):
        domain = args[0] if len(args) > 0 else kwargs["domain"]
        app_id = args[1] if len(args) > 1 else kwargs["app_id"]
        latest = True if request.GET.get('latest') == 'true' else False
        target = request.GET.get('target') or None

        try:
            request.app = get_app(domain, app_id, latest=latest, target=target)
            return f(request, *args, **kwargs)
        except (AppEditingError, CaseError), e:
            logging.exception(e)
            messages.error(request, "Problem downloading file: %s" % e)
            return HttpResponseRedirect(reverse("corehq.apps.app_manager.views.view_app", args=[domain,app_id]))
    return _safe_download


def no_conflict_require_POST(f):
    """
    Catches resource conflicts on save and returns a 409 error.
    Also includes require_POST decorator
    """
    @require_POST
    @wraps(f)
    def _no_conflict(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except ResourceConflict:
            return HttpResponse(status=409)
    return _no_conflict

require_can_edit_apps = require_permission(Permissions.edit_apps)
require_deploy_apps = login_and_domain_required  # todo: can fix this when it is better supported
