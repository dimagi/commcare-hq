from __future__ import absolute_import
from __future__ import unicode_literals

import os
import six

from couchdbkit import ResourceConflict
from distutils.version import LooseVersion

from datetime import datetime

from django.conf import settings
from django.http import JsonResponse, Http404, HttpResponse, HttpResponseBadRequest
from django.utils.translation import ugettext as _
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_GET
from iso8601 import iso8601

from corehq.apps.app_manager.dbaccessors import get_app_cached, get_latest_released_app_version
from corehq.form_processor.utils.xform import adjust_text_to_datetime
from dimagi.utils.decorators.profile import profile_prod
from dimagi.utils.logging import notify_exception
from casexml.apps.case.cleanup import claim_case, get_first_claim
from casexml.apps.case.fixtures import CaseDBFixture
from casexml.apps.case.models import CommCareCase

from corehq import toggles
from corehq.const import OPENROSA_VERSION_MAP, ONE_DAY
from corehq.middleware import OPENROSA_VERSION_HEADER
from corehq.apps.app_manager.util import LatestAppInfo
from corehq.apps.builds.utils import get_default_build_spec
from corehq.apps.case_search.models import QueryMergeException
from corehq.apps.case_search.utils import CaseSearchCriteria
from corehq.apps.domain.decorators import (
    mobile_auth,
    check_domain_migration,
    mobile_auth_or_formplayer,
)
from corehq.apps.domain.models import Domain
from corehq.apps.es.case_search import flatten_result
from corehq.apps.users.models import CouchUser, DeviceAppMeta
from corehq.apps.locations.permissions import location_safe
from corehq.form_processor.exceptions import CaseNotFound
from corehq.util.quickcache import quickcache
from casexml.apps.phone.restore import RestoreConfig, RestoreParams, RestoreCacheSettings
from dimagi.utils.parsing import string_to_utc_datetime

from .models import SerialIdBucket, MobileRecoveryMeasure
from .utils import (
    demo_user_restore_response, get_restore_user, is_permitted_to_restore,
    handle_401_response)
from corehq.apps.users.util import update_device_meta, update_latest_builds, update_last_sync


PROFILE_PROBABILITY = float(os.getenv('COMMCARE_PROFILE_RESTORE_PROBABILITY', 0))
PROFILE_LIMIT = os.getenv('COMMCARE_PROFILE_RESTORE_LIMIT')
PROFILE_LIMIT = int(PROFILE_LIMIT) if PROFILE_LIMIT is not None else 1


@location_safe
@handle_401_response
@mobile_auth_or_formplayer
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
@mobile_auth
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
    cases = [CommCareCase.wrap(flatten_result(result, include_score=True)) for result in hits]
    fixtures = CaseDBFixture(cases).fixture
    return HttpResponse(fixtures, content_type="text/xml; charset=utf-8")


def _handle_query_merge_exception(request, exception):
    notify_exception(request, six.text_type(exception), details=dict(
        exception_type=type(exception),
        original_query=getattr(exception, "original_query", None),
        query_addition=getattr(exception, "query_addition", None)
    ))
    return HttpResponse(status=500)


def _handle_es_exception(request, exception, query_addition_debug_details):
    notify_exception(request, six.text_type(exception), details=dict(
        exception_type=type(exception),
        **query_addition_debug_details
    ))
    return HttpResponse(status=500)


@location_safe
@csrf_exempt
@require_POST
@mobile_auth
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
    if isinstance(openrosa_version, bytes):
        openrosa_version = openrosa_version.decode('utf-8')

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


@profile_prod('commcare_ota_get_restore_response.prof', probability=PROFILE_PROBABILITY, limit=PROFILE_LIMIT)
def get_restore_response(domain, couch_user, app_id=None, since=None, version='1.0',
                         state=None, items=False, force_cache=False,
                         cache_timeout=None, overwrite_cache=False,
                         as_user=None, device_id=None, user_id=None,
                         openrosa_version=None,
                         case_sync=None):
    """
    :param domain: Domain being restored from
    :param couch_user: User performing restore
    :param app_id: App ID of the app making the request
    :param since: ID of current sync log used to generate incremental sync
    :param version: Version of the sync response required
    :param state: Hash value of the current database of cases on the device for consistency checking
    :param items: Include item count if True
    :param force_cache: Force response to be cached
    :param cache_timeout: Override the default cache timeout of 1 hour.
    :param overwrite_cache: Ignore cached response if True
    :param as_user: Username of user to generate restore for (if different from current user)
    :param device_id: ID of device performing restore
    :param user_id: ID of user performing restore (used in case of deleted user with same username)
    :param openrosa_version:
    :param case_sync: Override default case sync algorithm
    :return: Tuple of (http response, timing context or None)
    """

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
        msg = _('Invalid restore as user {}').format(as_user)
        return HttpResponse(msg, status=401), None
    is_permitted, message = is_permitted_to_restore(
        domain,
        couch_user,
        as_user_obj,
    )
    if not is_permitted:
        return HttpResponse(message, status=401), None

    restore_user = get_restore_user(domain, couch_user, as_user_obj)
    if not restore_user:
        return HttpResponse('Could not find user', status=404), None

    project = Domain.get_by_name(domain)
    async_restore_enabled = (
        toggles.ASYNC_RESTORE.enabled(domain)
        and openrosa_version
        and LooseVersion(openrosa_version) >= LooseVersion(OPENROSA_VERSION_MAP['ASYNC_RESTORE'])
    )

    app = get_app_cached(domain, app_id) if app_id else None
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
        is_async=async_restore_enabled,
        case_sync=case_sync,
    )
    return restore_config.get_response(), restore_config.timing_context


@mobile_auth
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

    info = {"app_id": app_id}
    try:
        # mobile will send brief_app_id
        info.update(LatestAppInfo(app_id, domain).get_info())
    except (Http404, AssertionError):
        # If it's not a valid 'brief' app id, find it by talking to couch
        notify_exception(request, 'Received an invalid heartbeat request')
        app = get_app_cached(domain, app_build_id)
        brief_app_id = app.master_id
        info.update(LatestAppInfo(brief_app_id, domain).get_info())

    else:
        if settings.SERVER_ENVIRONMENT not in settings.ICDS_ENVS:
            # disable on icds for now since couch still not happy
            couch_user = request.couch_user
            try:
                update_user_reporting_data(app_build_id, app_id, couch_user, request)
            except ResourceConflict:
                # https://sentry.io/dimagi/commcarehq/issues/521967014/
                couch_user = CouchUser.get(couch_user.user_id)
                update_user_reporting_data(app_build_id, app_id, couch_user, request)

    return JsonResponse(info)


def update_user_reporting_data(app_build_id, app_id, couch_user, request):
    def _safe_int(val):
        try:
            return int(val)
        except:
            pass

    app_version = _safe_int(request.GET.get('app_version', ''))
    device_id = request.GET.get('device_id', '')
    last_sync_time = request.GET.get('last_sync_time', '')
    num_unsent_forms = _safe_int(request.GET.get('num_unsent_forms', ''))
    num_quarantined_forms = _safe_int(request.GET.get('num_quarantined_forms', ''))
    commcare_version = request.GET.get('cc_version', '')
    save_user = False
    # if mobile cannot determine app version it sends -1
    if app_version and app_version > 0:
        save_user = update_latest_builds(couch_user, app_id, datetime.utcnow(), app_version)
    try:
        last_sync = adjust_text_to_datetime(last_sync_time)
    except iso8601.ParseError:
        try:
            last_sync = string_to_utc_datetime(last_sync_time)
        except (ValueError, OverflowError):
            last_sync = None
    else:
        save_user |= update_last_sync(couch_user, app_id, last_sync, app_version)
    app_meta = DeviceAppMeta(
        app_id=app_id,
        build_id=app_build_id,
        build_version=app_version,
        last_heartbeat=datetime.utcnow(),
        last_sync=last_sync,
        num_unsent_forms=num_unsent_forms,
        num_quarantined_forms=num_quarantined_forms
    )
    save_user |= update_device_meta(
        couch_user,
        device_id,
        commcare_version=commcare_version,
        device_app_meta=app_meta,
        save=False
    )
    if save_user:
        couch_user.save(fire_signals=False)


@location_safe
@mobile_auth
@require_GET
def get_next_id(request, domain):
    bucket_id = request.GET.get('pool_id')
    session_id = request.GET.get('session_id')
    if bucket_id is None:
        return HttpResponseBadRequest("You must provide a pool_id parameter")
    return HttpResponse(SerialIdBucket.get_next(domain, bucket_id, session_id))


@quickcache(['domain', 'app_id'], timeout=ONE_DAY)
def get_recovery_measures_cached(domain, app_id):
    return [measure.to_mobile_json() for measure in
            MobileRecoveryMeasure.objects.filter(domain=domain, app_id=app_id)]


# Note: this endpoint does not require authentication
@location_safe
@require_GET
@toggles.MOBILE_RECOVERY_MEASURES.required_decorator()
def recovery_measures(request, domain, build_id):
    app_id = get_app_cached(domain, build_id).master_id
    response = {
        "latest_apk_version": get_default_build_spec().version,
        "latest_ccz_version": get_latest_released_app_version(domain, app_id),
        "app_id": request.GET.get('app_id'),  # passed through unchanged
    }
    measures = get_recovery_measures_cached(domain, app_id)
    if measures:
        response["recovery_measures"] = measures
    return JsonResponse(response)
