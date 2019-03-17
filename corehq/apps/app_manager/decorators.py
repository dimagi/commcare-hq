from __future__ import absolute_import
from __future__ import unicode_literals
import logging
import json
from functools import wraps
from django.contrib import messages
from django.http import HttpResponseRedirect, HttpResponse
from couchdbkit.exceptions import ResourceConflict
from django.views.decorators.http import require_POST
from django.urls import reverse
from corehq import toggles
from corehq.apps.app_manager.exceptions import CaseError
from corehq.apps.app_manager.dbaccessors import get_app
from corehq.apps.app_manager.models import AppEditingError
from corehq.apps.app_manager.util import get_latest_enabled_build_for_profile, get_latest_enabled_app_release
from corehq.apps.users.decorators import require_permission
from corehq.apps.users.models import Permissions, CommCareUser
from corehq.apps.domain.decorators import login_and_domain_required
from corehq.apps.users.util import normalize_username

from dimagi.utils.couch.undo import DELETED_SUFFIX


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
            if not request.app.doc_type.endswith(DELETED_SUFFIX):
                return f(request, *args, **kwargs)
            else:
                message = 'User attempted to install deleted application: {}'.format(app_id)
        except (AppEditingError, CaseError, ValueError) as e:
            message = e
        logging.exception(message)
        messages.error(request, "Problem downloading file: %s" % message)
        return HttpResponseRedirect(reverse("view_app", args=[domain, app_id]))


    return _safe_download


def safe_cached_download(f):
    """
    Same as safe_download, but makes it possible for the browser to cache.

    If latest is passed to this endpoint it cannot be cached. This should not
    be used on any view that uses information from the user.
    """
    @wraps(f)
    def _safe_cached_download(request, *args, **kwargs):
        domain = args[0] if len(args) > 0 else kwargs["domain"]
        app_id = args[1] if len(args) > 1 else kwargs["app_id"]
        latest = True if request.GET.get('latest') == 'true' else False
        target = request.GET.get('target') or None

        # make endpoints that call the user fail hard
        from django.contrib.auth.models import AnonymousUser
        request.user = AnonymousUser()
        username = request.GET.get('username')
        if request.GET.get('username'):
            request.GET = request.GET.copy()
            request.GET.pop('username')

        latest_enabled_build = None
        if latest and toggles.MANAGE_RELEASES_PER_LOCATION.enabled(domain):
            if not username:
                content_response = dict(error="app.update.not.allowed.user.logged_out",
                                        default_response="Please log in the app to check for update.")
                return HttpResponse(status=406, content=json.dumps(content_response))
            user = CommCareUser.get_by_username(normalize_username(username, domain))
            user_location_id = user.location_id
            if user_location_id:
                parent_app_id = get_app(domain, app_id).copy_of
                latest_enabled_build = get_latest_enabled_app_release(domain, user_location_id, parent_app_id)
        try:
            if latest_enabled_build:
                request.app = latest_enabled_build
            else:
                request.app = get_app(domain, app_id, latest=latest, target=target)
            if not request.app.doc_type.endswith(DELETED_SUFFIX):
                response = f(request, *args, **kwargs)
                if request.app.copy_of is not None and request.app.is_released:
                    if latest:
                        response._cache_max_age = 60
                    response._always_allow_browser_caching = True
                    response._remember_domain = False
                return response
            else:
                message = 'User attempted to install deleted application: {}'.format(app_id)
        except (AppEditingError, CaseError, ValueError) as e:
            message = e
        logging.exception(message)
        messages.error(request, "Problem downloading file: %s" % message)
        return HttpResponseRedirect(reverse("view_app", args=[domain, app_id]))
    return _safe_cached_download


def no_conflict_require_POST(fn):
    """
    Catches resource conflicts on save and returns a 409 error.
    Also includes require_POST decorator
    """
    return require_POST(no_conflict(fn))


def no_conflict(fn):
    @wraps(fn)
    def _no_conflict(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except ResourceConflict:
            return HttpResponse(status=409)

    return _no_conflict


require_can_edit_apps = require_permission(Permissions.edit_apps)
require_deploy_apps = login_and_domain_required  # todo: can fix this when it is better supported
