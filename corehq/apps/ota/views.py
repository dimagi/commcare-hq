from __future__ import absolute_import
from distutils.version import LooseVersion

from datetime import datetime
from django.http import JsonResponse, Http404, HttpResponse, HttpResponseBadRequest
from django.utils.translation import ugettext as _
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_GET

from casexml.apps.phone.exceptions import InvalidSyncLogException
from corehq.util.datadog.gauges import datadog_counter
from corehq.util.datadog.utils import bucket_value
from dimagi.utils.logging import notify_exception
from casexml.apps.case.cleanup import claim_case, get_first_claim
from casexml.apps.case.fixtures import CaseDBFixture
from casexml.apps.case.models import CommCareCase

from corehq import toggles
from corehq.const import OPENROSA_VERSION_MAP
from corehq.middleware import OPENROSA_VERSION_HEADER
from corehq.apps.app_manager.util import get_app, LatestAppInfo
from corehq.apps.case_search.models import QueryMergeException
from corehq.apps.case_search.utils import CaseSearchCriteria
from corehq.apps.domain.decorators import (
    login_or_digest_or_basic_or_apikey,
    check_domain_migration,
    login_or_digest_or_basic_or_apikey_or_token,
)
from corehq.apps.domain.models import Domain
from corehq.apps.es.case_search import flatten_result
from corehq.apps.users.models import CouchUser
from corehq.apps.locations.permissions import location_safe
from corehq.form_processor.exceptions import CaseNotFound
from casexml.apps.phone.restore import RestoreConfig, RestoreParams, RestoreCacheSettings

from .models import SerialIdBucket
from .utils import (
    demo_user_restore_response, get_restore_user, is_permitted_to_restore,
    handle_401_response, update_device_id)


@location_safe
@handle_401_response
@login_or_digest_or_basic_or_apikey_or_token()
@check_domain_migration
def restore(request, domain, app_id=None):
    """
    We override restore because we have to supply our own
    user model (and have the domain in the url)
    """
    response, timing_context = get_restore_response(
        domain, request.couch_user, app_id, **get_restore_params(request))
    return response


@location_safe
@login_or_digest_or_basic_or_apikey()
@check_domain_migration
def search(request, domain):
    """
    Accepts search criteria as GET params, e.g. "https://www.commcarehq.org/a/domain/phone/search/?a=b&c=d"
    Returns results as a fixture with the same structure as a casedb instance.
    """
    criteria = request.GET.dict()
    try:
        case_type = criteria.pop('case_type')
    except KeyError:
        return HttpResponse('Search request must specify case type', status=400)
    try:
        case_search_criteria = CaseSearchCriteria(domain, case_type, criteria)
        search_es = case_search_criteria.search_es
    except QueryMergeException as e:
        return _handle_query_merge_exception(request, e)
    try:
        hits = search_es.run().raw_hits
    except Exception as e:
        return _handle_es_exception(request, e, case_search_criteria.query_addition_debug_details)

    # Even if it's a SQL domain, we just need to render the hits as cases, so CommCareCase.wrap will be fine
    cases = [CommCareCase.wrap(flatten_result(result)) for result in hits]
    fixtures = CaseDBFixture(cases).fixture
    return HttpResponse(fixtures, content_type="text/xml; charset=utf-8")


def _handle_query_merge_exception(request, exception):
    notify_exception(request, exception.message, details=dict(
        exception_type=type(exception),
        original_query=getattr(exception, "original_query", None),
        query_addition=getattr(exception, "query_addition", None)
    ))
    return HttpResponse(status=500)


def _handle_es_exception(request, exception, query_addition_debug_details):
    notify_exception(request, exception, details=dict(
        exception_type=type(exception),
        **query_addition_debug_details
    ))
    return HttpResponse(status=500)


@location_safe
@csrf_exempt
@require_POST
@login_or_digest_or_basic_or_apikey()
@check_domain_migration
def claim(request, domain):
    """
    Allows a user to claim a case that they don't own.
    """
    as_user = request.POST.get('commcare_login_as', None)
    as_user_obj = CouchUser.get_by_username(as_user) if as_user else None
    restore_user = get_restore_user(domain, request.couch_user, as_user_obj)

    case_id = request.POST.get('case_id', None)
    if case_id is None:
        return HttpResponse('A case_id is required', status=400)

    try:
        if get_first_claim(domain, restore_user.user_id, case_id):
            return HttpResponse('You have already claimed that {}'.format(request.POST.get('case_type', 'case')),
                                status=409)

        claim_case(domain, restore_user.user_id, case_id,
                   host_type=request.POST.get('case_type'),
                   host_name=request.POST.get('case_name'),
                   device_id=__name__ + ".claim")
    except CaseNotFound:
        return HttpResponse('The case "{}" you are trying to claim was not found'.format(case_id),
                            status=410)
    return HttpResponse(status=200)


def get_restore_params(request):
    """
    Given a request, get the relevant restore parameters out with sensible defaults
    """
    # not a view just a view util
    try:
        openrosa_headers = getattr(request, 'openrosa_headers', {})
        openrosa_version = openrosa_headers[OPENROSA_VERSION_HEADER]
    except KeyError:
        openrosa_version = request.GET.get('openrosa_version', None)

    return {
        'since': request.GET.get('since'),
        'version': request.GET.get('version', "2.0"),
        'state': request.GET.get('state'),
        'items': request.GET.get('items') == 'true',
        'as_user': request.GET.get('as'),
        'overwrite_cache': request.GET.get('overwrite_cache') == 'true',
        'openrosa_version': openrosa_version,
        'device_id': request.GET.get('device_id'),
        'user_id': request.GET.get('user_id'),
        'case_sync': request.GET.get('case_sync'),
    }


def get_restore_response(domain, couch_user, app_id=None, since=None, version='1.0',
                         state=None, items=False, force_cache=False,
                         cache_timeout=None, overwrite_cache=False,
                         as_user=None, device_id=None, user_id=None,
                         openrosa_version=None,
                         case_sync=None):

    if user_id and user_id != couch_user.user_id:
        # sync with a user that has been deleted but a new
        # user was created with the same username and password
        from couchforms.openrosa_response import get_simple_response_xml
        from couchforms.openrosa_response import ResponseNature
        response = get_simple_response_xml(
            'Attempt to sync with invalid user.',
            ResponseNature.OTA_RESTORE_ERROR
        )
        return HttpResponse(response, content_type="text/xml; charset=utf-8", status=412), None

    is_demo_restore = couch_user.is_commcare_user() and couch_user.is_demo_user
    if is_demo_restore:
        # if user is in demo-mode, return demo restore
        return demo_user_restore_response(couch_user), None

    uses_login_as = bool(as_user)
    as_user_obj = CouchUser.get_by_username(as_user) if uses_login_as else None
    if uses_login_as and not as_user_obj:
        msg = _(u'Invalid restore as user {}').format(as_user)
        return HttpResponse(msg, status=401), None
    is_permitted, message = is_permitted_to_restore(
        domain,
        couch_user,
        as_user_obj,
    )
    if not is_permitted:
        return HttpResponse(message, status=401), None

    couch_restore_user = as_user_obj if uses_login_as else couch_user
    update_device_id(couch_restore_user, device_id)

    restore_user = get_restore_user(domain, couch_user, as_user_obj)
    if not restore_user:
        return HttpResponse('Could not find user', status=404), None

    project = Domain.get_by_name(domain)
    app = get_app(domain, app_id) if app_id else None
    async_restore_enabled = (
        toggles.ASYNC_RESTORE.enabled(domain)
        and openrosa_version
        and LooseVersion(openrosa_version) >= LooseVersion(OPENROSA_VERSION_MAP['ASYNC_RESTORE'])
    )
    restore_config = RestoreConfig(
        project=project,
        restore_user=restore_user,
        params=RestoreParams(
            sync_log_id=since,
            version=version,
            state_hash=state,
            include_item_count=items,
            app=app,
            device_id=device_id,
            openrosa_version=openrosa_version,
        ),
        cache_settings=RestoreCacheSettings(
            force_cache=force_cache or async_restore_enabled,
            cache_timeout=cache_timeout,
            overwrite_cache=overwrite_cache
        ),
        async=async_restore_enabled,
        case_sync=case_sync,
    )
    _log_time_since_last_sync(restore_config)
    return restore_config.get_response(), restore_config.timing_context


def _log_time_since_last_sync(restore_config):
    try:
        last_sync = restore_config.restore_state.last_sync_log
    except InvalidSyncLogException:
        return

    if not last_sync or not last_sync.date:
        bucket = 'initial'
    else:
        time_since = datetime.utcnow() - last_sync.date
        days_since = time_since.total_seconds() / 86400.0
        bucket = bucket_value(days_since, buckets=(2, 7, 14, 28), unit='d')

    datadog_counter('commcare.restore.sync_interval', tags=[
        'days_since_last:%s' % bucket
    ])


@login_or_digest_or_basic_or_apikey()
@require_GET
def heartbeat(request, domain, app_build_id):
    """
    An endpoint for CommCare mobile to get latest CommCare APK and app version
        info. (Should serve from cache as it's going to be busy view)

    'app_build_id' (that comes from URL) can be id of any version of the app
    'app_id' (urlparam) is usually id of an app that is not a copy
        mobile simply needs it to be resent back in the JSON, and doesn't
        need any validation on it. This is pulled from @uniqueid from profile.xml
    """
    app_id = request.GET.get('app_id', '')

    app_version = request.GET.get('app_version', '')
    device_id = request.GET.get('device_id', '')
    last_sync_time = request.GET.get('last_sync_time', '')
    num_unsent_forms = request.GET.get('num_unsent_forms', '')
    num_quarantined_forms = request.GET.get('num_quarantined_forms', '')
    commcare_version = request.GET.get('cc_version', '')

    info = {"app_id": app_id}
    try:
        # mobile will send brief_app_id
        info.update(LatestAppInfo(app_id, domain).get_info())
    except (Http404, AssertionError):
        # If it's not a valid 'brief' app id, find it by talking to couch
        notify_exception(request, 'Received an invalid heartbeat request')
        app = get_app(domain, app_build_id)
        brief_app_id = app.master_id
        info.update(LatestAppInfo(brief_app_id, domain).get_info())

    return JsonResponse(info)


@location_safe
@login_or_digest_or_basic_or_apikey()
@require_GET
def get_next_id(request, domain):
    bucket_id = request.GET.get('pool_id')
    session_id = request.GET.get('session_id')
    if bucket_id is None:
        return HttpResponseBadRequest("You must provide a pool_id parameter")
    return HttpResponse(SerialIdBucket.get_next(domain, bucket_id, session_id))
