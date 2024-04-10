import os
from datetime import datetime
from urllib.parse import unquote

from django.conf import settings
from django.http import (
    Http404,
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseNotFound,
    JsonResponse,
)
from django.utils.translation import gettext as _
from django.utils.translation import ngettext
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from couchdbkit import ResourceConflict
from iso8601 import iso8601
from looseversion import LooseVersion
from memoized import memoized
from tastypie.http import HttpTooManyRequests

from casexml.apps.case.cleanup import claim_case, get_first_claims
from casexml.apps.case.fixtures import CaseDBFixture
from casexml.apps.phone.data_providers.case.livequery import get_case_hierarchy
from casexml.apps.phone.exceptions import MissingSyncLog
from casexml.apps.phone.models import get_properly_wrapped_sync_log
from casexml.apps.phone.restore import (
    RestoreCacheSettings,
    RestoreConfig,
    RestoreParams,
)
from dimagi.utils.decorators.profile import profile_dump
from dimagi.utils.logging import notify_exception
from dimagi.utils.parsing import string_to_utc_datetime

from corehq import toggles
from corehq.apps.app_manager.dbaccessors import (
    get_app_cached,
    get_latest_released_app_version,
)
from corehq.apps.app_manager.models import GlobalAppConfig
from corehq.apps.builds.utils import get_default_build_spec
from corehq.apps.case_search.const import COMMCARE_PROJECT
from corehq.apps.case_search.exceptions import CaseSearchUserError
from corehq.apps.case_search.models import CASE_SEARCH_REGISTRY_ID_KEY, CASE_SEARCH_TAGS_MAPPING
from corehq.apps.case_search.utils import get_case_search_results_from_request
from corehq.apps.domain.auth import formplayer_auth
from corehq.apps.domain.decorators import check_domain_migration
from corehq.apps.domain.models import Domain
from corehq.apps.locations.permissions import (
    location_safe,
    location_safe_bypass,
)
from corehq.apps.ota.decorators import mobile_auth, mobile_auth_or_formplayer
from corehq.apps.registry.exceptions import (
    RegistryAccessException,
    RegistryNotFound,
)
from corehq.apps.registry.helper import DataRegistryHelper
from corehq.apps.users.models import CouchUser, UserReportingMetadataStaging
from corehq.const import ONE_DAY, OPENROSA_VERSION_MAP
from corehq.form_processor.exceptions import CaseNotFound
from corehq.form_processor.models import CommCareCase
from corehq.form_processor.utils.xform import adjust_text_to_datetime
from corehq.middleware import OPENROSA_VERSION_HEADER
from corehq.util.metrics import limit_domains, metrics_histogram, limit_tags
from corehq.util.quickcache import quickcache

from .case_restore import get_case_restore_response
from .models import DeviceLogRequest, MobileRecoveryMeasure, SerialIdBucket
from .rate_limiter import rate_limit_restore
from .utils import (
    demo_user_restore_response,
    get_restore_user,
    handle_401_response,
    is_permitted_to_restore,
)

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
    if rate_limit_restore(domain):
        return HttpTooManyRequests()

    response, timing_context = get_restore_response(
        domain, request.couch_user, app_id, **get_restore_params(request, domain))
    return response


@location_safe_bypass
@csrf_exempt
@mobile_auth
@check_domain_migration
@toggles.SYNC_SEARCH_CASE_CLAIM.required_decorator()
def search(request, domain):
    return app_aware_search(request, domain, None)


@location_safe_bypass
@csrf_exempt
@mobile_auth
@check_domain_migration
@toggles.SYNC_SEARCH_CASE_CLAIM.required_decorator()
def app_aware_search(request, domain, app_id):
    """
    Accepts search criteria as GET params, e.g. "https://www.commcarehq.org/a/domain/phone/search/?a=b&c=d"
        Daterange can be specified in the format __range__YYYY-MM-DD__YYYY-MM-DD
        Multiple values can be specified for a param, which will be searched with OR operator

    Returns results as a fixture with the same structure as a casedb instance.
    """
    start_time = datetime.now()
    request_dict = dict((request.GET if request.method == 'GET' else request.POST).lists())

    try:
        fixtures, profiler = get_case_search_results_from_request(domain, app_id, request.couch_user, request_dict)
    except CaseSearchUserError as e:
        return HttpResponse(str(e), status=400)
    _log_search_timing(start_time, request_dict, domain, app_id)
    response = HttpResponse(fixtures, content_type="text/xml; charset=utf-8")
    response.request_timer = profiler.timing_context  # logged as Sentry breadcrumbs
    return response


def _log_search_timing(start_time, request_dict, domain, app_id):
    for key, value in request_dict.items():
        if isinstance(value, str):
            request_dict[key] = value.replace('\t', '')
        elif isinstance(value, list):
            request_dict[key] = [item.replace('\t', '') for item in value if isinstance(item, str)]

    tags = {
        tag_name: value[0]
        for param_name, tag_name in CASE_SEARCH_TAGS_MAPPING.items()
        if (value := request_dict.pop(param_name, []))
    }
    tags.update({'domain': limit_domains(domain)})

    elapsed = (datetime.now() - start_time).total_seconds()
    metrics_histogram("commcare.app_aware_search.processing_time",
                      int(elapsed * 1000),
                      bucket_tag='duration_bucket',
                      buckets=(500, 1000, 5000),
                      bucket_unit='ms',
                      tags=limit_tags(tags, domain))
    if elapsed >= 10 and limit_domains(domain) != "__other__":
        notify_exception(None, "LongCaseSearchRequest", details={
            'request_dict': request_dict,
            'app_id': app_id,
        })


@location_safe_bypass
@csrf_exempt
@require_POST
@mobile_auth
@check_domain_migration
@toggles.SYNC_SEARCH_CASE_CLAIM.required_decorator()
def claim(request, domain):
    """
    Allows a user to claim a case that they don't own.
    """
    as_user = unquote(request.POST.get('commcare_login_as', ''))
    as_user_obj = CouchUser.get_by_username(as_user) if as_user else None
    restore_user = get_restore_user(domain, request.couch_user, as_user_obj)

    case_ids = request.POST.getlist('case_id')

    if not case_ids:
        return HttpResponse('A case_id is required', status=400)

    try:
        case_ids_already_claimed = get_first_claims(domain, restore_user.user_id, case_ids)
        case_ids_to_claim = {case for case in case_ids if case not in case_ids_already_claimed}
    except CaseNotFound as err:
        return HttpResponse(f'No cases claimed. Case IDs "{err}" not found',
                            status=410)

    for case_id in case_ids_to_claim:
        claim_case(domain, restore_user, case_id,
                   host_type=unquote(request.POST.get('case_type', '')),
                   host_name=unquote(request.POST.get('case_name', '')),
                   device_id=__name__ + ".claim")

    @memoized
    def get_synclog(sync_token):
        try:
            return get_properly_wrapped_sync_log(sync_token)
        except MissingSyncLog:
            return False

    def phone_holds_all_cases(request):
        if get_synclog(request.last_sync_token):
            synclog = get_synclog(request.last_sync_token)
            missing_case_ids_on_phone = set(case_ids) - synclog.case_ids_on_phone
            return not missing_case_ids_on_phone

    def cases_have_been_modified_since_last_synclog_date():
        if get_synclog(request.last_sync_token):
            synclog = get_synclog(request.last_sync_token)
            return bool(CommCareCase.objects.get_modified_case_ids(domain, case_ids, synclog))

    if case_ids_to_claim:
        return HttpResponse(status=201)

    if not phone_holds_all_cases(request):
        return HttpResponse(status=201)

    if cases_have_been_modified_since_last_synclog_date():
        return HttpResponse(status=201)

    return HttpResponse(status=204)


def get_restore_params(request, domain):
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

    skip_fixtures = (
        toggles.SKIP_FIXTURES_ON_RESTORE.enabled(
            domain, namespace=toggles.NAMESPACE_DOMAIN
        ) or request.GET.get('skip_fixtures') == 'true'
    )

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
        'skip_fixtures': skip_fixtures,
        'auth_type': getattr(request, 'auth_type', None),
        'fail_hard': request.GET.get('fail_hard') == 'true',
    }


@profile_dump('commcare_ota_get_restore_response.prof', probability=PROFILE_PROBABILITY, limit=PROFILE_LIMIT)
def get_restore_response(domain, couch_user, app_id=None, since=None, version='1.0',
                         state=None, items=False, force_cache=False,
                         cache_timeout=None, overwrite_cache=False,
                         as_user=None, device_id=None, user_id=None,
                         openrosa_version=None,
                         skip_fixtures=False, auth_type=None,
                         fail_hard=False):
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
    :param skip_fixtures: Do not include fixtures in sync payload
    :param auth_type: The type of auth that was used to authenticate the request.
        Used to determine if the request is coming from an actual user or as part of some automation.
    :param fail_hard: In case of exceptions, fail hardly by raising exception instead of logging
        silently.
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

    # Ensure fixtures are included if sync is full rather than incremental
    if not since:
        skip_fixtures = False

    # If loadtest user, do a full restore
    if restore_user.loadtest_factor > 1:
        since = None

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
            fail_hard=fail_hard,
        ),
        cache_settings=RestoreCacheSettings(
            force_cache=force_cache or async_restore_enabled,
            cache_timeout=cache_timeout,
            overwrite_cache=overwrite_cache
        ),
        is_async=async_restore_enabled,
        skip_fixtures=skip_fixtures,
        auth_type=auth_type
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
    build_profile_id = request.GET.get('build_profile_id', '')
    master_app_id = app_id
    try:
        info = GlobalAppConfig.get_latest_version_info(domain, app_id, build_profile_id)
    except (Http404, AssertionError):
        # If it's not a valid master app id, find it by talking to couch
        app = get_app_cached(domain, app_build_id)
        notify_exception(request, 'Received an invalid heartbeat request')
        master_app_id = app.origin_id if app else None
        info = GlobalAppConfig.get_latest_version_info(domain, app.origin_id, build_profile_id)

    info["app_id"] = app_id
    if master_app_id:
        if not toggles.SKIP_UPDATING_USER_REPORTING_METADATA.enabled(domain):
            update_user_reporting_data(app_build_id, app_id, build_profile_id, request.couch_user, request)

    if _should_force_log_submission(request):
        info['force_logs'] = True
    return JsonResponse(info)


def update_user_reporting_data(app_build_id, app_id, build_profile_id, couch_user, request):
    def _safe_int(val):
        try:
            return int(val)
        except Exception:
            pass

    app_version = _safe_int(request.GET.get('app_version', ''))
    device_id = request.GET.get('device_id', '')
    last_sync_time = request.GET.get('last_sync_time', '')
    num_unsent_forms = _safe_int(request.GET.get('num_unsent_forms', ''))
    num_quarantined_forms = _safe_int(request.GET.get('num_quarantined_forms', ''))
    commcare_version = request.GET.get('cc_version', '')
    fcm_token = ''
    if toggles.FCM_NOTIFICATION.enabled(request.domain):
        fcm_token = request.GET.get('fcm_token', '')
    # if mobile cannot determine app version it sends -1
    if app_version == -1:
        app_version = None
    try:
        last_sync = adjust_text_to_datetime(last_sync_time)
    except iso8601.ParseError:
        try:
            last_sync = string_to_utc_datetime(last_sync_time)
        except (ValueError, OverflowError):
            last_sync = None

    if settings.USER_REPORTING_METADATA_BATCH_ENABLED:
        UserReportingMetadataStaging.add_heartbeat(
            request.domain, couch_user._id, app_id, app_build_id, last_sync, device_id,
            app_version, num_unsent_forms, num_quarantined_forms, commcare_version, build_profile_id, fcm_token
        )
    else:
        record = UserReportingMetadataStaging(domain=request.domain, user_id=couch_user._id, app_id=app_id,
            build_id=app_build_id, sync_date=last_sync, device_id=device_id, app_version=app_version,
            num_unsent_forms=num_unsent_forms, num_quarantined_forms=num_quarantined_forms,
            commcare_version=commcare_version, build_profile_id=build_profile_id,
            last_heartbeat=datetime.utcnow(), modified_on=datetime.utcnow(), fcm_token=fcm_token)
        try:
            record.process_record(couch_user)
        except ResourceConflict:
            # https://sentry.io/dimagi/commcarehq/issues/521967014/
            couch_user = CouchUser.get(couch_user.user_id)
            record.process_record(couch_user)


def _should_force_log_submission(request):
    return DeviceLogRequest.is_pending(
        request.domain,
        request.couch_user.username
    )


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
    app_id = get_app_cached(domain, build_id).origin_id
    response = {
        "latest_apk_version": get_default_build_spec().version,
        "latest_ccz_version": get_latest_released_app_version(domain, app_id),
        "app_id": request.GET.get('app_id'),  # passed through unchanged
    }
    measures = get_recovery_measures_cached(domain, app_id)
    if measures:
        response["recovery_measures"] = measures
    return JsonResponse(response)


@location_safe_bypass
@csrf_exempt
@mobile_auth
@toggles.SYNC_SEARCH_CASE_CLAIM.required_decorator()
def case_fixture(request, domain, app_id):
    request_dict = request.GET if request.method == 'GET' else request.POST
    case_ids = request_dict.getlist("case_id")
    case_types = request_dict.getlist("case_type")
    registry = request_dict.get(CASE_SEARCH_REGISTRY_ID_KEY)

    missing = [
        name for name, value in zip(
            ["case_id", "case_type"],
            [case_ids, case_types]
        )
        if not value
    ]
    if missing:
        return HttpResponseBadRequest(ngettext(
            "'{params}' is a required parameter",
            "'{params}' are required parameters",
            len(missing)
        ).format(params="', '".join(missing)))

    if registry:
        try:
            cases = _data_registry_case_fixture(request, domain, app_id, case_types, case_ids, registry)
        except RegistryAccessException as e:
            return HttpResponseBadRequest(str(e))
        except Http404 as e:
            # convert to a simple response to avoid the HTML error page
            return HttpResponseNotFound(str(e))
    else:
        cases = _single_domain_case_fixture(request, domain, case_types, case_ids)

    for case in cases:
        case.case_json[COMMCARE_PROJECT] = case.domain
    return HttpResponse(CaseDBFixture(cases).fixture, content_type="text/xml; charset=utf-8")


def _single_domain_case_fixture(request, domain, case_types, case_ids):
    cases = CommCareCase.objects.get_cases(case_ids)
    for case in cases:
        if case.domain != domain or case.type not in case_types:
            raise Http404(f"Case '{case.case_id}' not found")
    case_ids_found = {case.case_id for case in cases}
    missing = set(case_ids) - case_ids_found
    if missing:
        raise Http404(f"Cases '{','.join(missing)}' not found")

    return get_case_hierarchy(domain, cases)


@toggles.DATA_REGISTRY.required_decorator()
def _data_registry_case_fixture(request, domain, app_id, case_types, case_ids, registry_slug):
    helper = DataRegistryHelper(domain, registry_slug=registry_slug)

    app = get_app_cached(domain, app_id)
    try:
        cases = [
            helper.get_case(case_id, request.couch_user, app)
            for case_id in case_ids
        ]
    except RegistryNotFound:
        raise Http404(f"Registry '{registry_slug}' not found")
    except CaseNotFound as e:
        raise Http404(f"Case '{str(e)}' not found")

    for case in cases:
        if case.type not in case_types:
            raise Http404(f"Case '{case.case_id}' not found")

    return helper.get_multi_domain_case_hierarchy(request.couch_user, cases)


@formplayer_auth
def case_restore(request, domain, case_id):
    """Restore endpoint used for SMS forms where the 'user' is a case.

    Accepts the provided case_id and returns a restore for the user containing:
    * Registration block
    * The passed in case and its full network of cases
    """
    return get_case_restore_response(domain, case_id)
