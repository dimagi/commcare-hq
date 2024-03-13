import os
import logging

from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.core.cache import cache

import couchforms
from casexml.apps.case.xform import get_case_updates, is_device_report
from corehq.apps.hqwebapp.decorators import waf_allow
from corehq.apps.users.decorators import require_permission
from corehq.apps.users.models import HqPermissions
from couchforms import openrosa_response
from couchforms.const import MAGIC_PROPERTY
from couchforms.exceptions import BadSubmissionRequest, UnprocessableFormSubmission
from couchforms.getters import MultimediaBug
from dimagi.utils.decorators.profile import profile_dump
from dimagi.utils.logging import notify_exception

from corehq import toggles
from corehq.apps.domain.auth import (
    BASIC,
    DIGEST,
    NOAUTH,
    API_KEY,
    OAUTH2,
    determine_authtype_from_request,
)
from corehq.apps.domain.decorators import (
    api_auth,
    check_domain_migration,
    login_or_basic_ex,
    login_or_digest_ex,
    login_or_api_key_ex,
    login_or_oauth2_ex,
    two_factor_exempt,
)
from corehq.apps.locations.permissions import location_safe
from corehq.apps.ota.utils import handle_401_response
from corehq.apps.receiverwrapper.auth import (
    AuthContext,
    WaivedAuthContext,
    domain_requires_auth,
)
from corehq.apps.receiverwrapper.rate_limiter import rate_limit_submission
from corehq.apps.receiverwrapper.util import (
    DEMO_SUBMIT_MODE,
    from_demo_user,
    get_app_and_build_ids,
    should_ignore_submission,
)
from corehq.form_processor.exceptions import XFormLockError
from corehq.form_processor.models import CommCareCase
from corehq.form_processor.submission_post import SubmissionPost
from corehq.form_processor.utils import convert_xform_to_json
from corehq.util.metrics import metrics_counter, metrics_histogram
from corehq.util.timer import TimingContext, set_request_duration_reporting_threshold
from couchdbkit import ResourceNotFound
from tastypie.http import HttpTooManyRequests

PROFILE_PROBABILITY = float(os.getenv('COMMCARE_PROFILE_SUBMISSION_PROBABILITY', 0))
PROFILE_LIMIT = os.getenv('COMMCARE_PROFILE_SUBMISSION_LIMIT')
PROFILE_LIMIT = int(PROFILE_LIMIT) if PROFILE_LIMIT is not None else 1
CACHE_EXPIRY_7_DAYS_IN_SECS = 7 * 24 * 60 * 60


def _verify_access(domain, user_id, request):
    """Unless going through the API, users should have the access_mobile_endpoints permission"""
    cache_key = f"form_submission_permissions_audit:{user_id}"
    if cache.get(cache_key):
        # User is already logged once in last 7 days for incorrect access, so no need to log again
        return

    if not request.couch_user.has_permission(domain, 'access_mobile_endpoints'):
        cache.set(cache_key, True, CACHE_EXPIRY_7_DAYS_IN_SECS)
        message = f"NoMobileEndpointsAccess: invalid request by {user_id} on {domain}"
        notify_exception(request, message=message)


@profile_dump('commcare_receiverwapper_process_form.prof', probability=PROFILE_PROBABILITY, limit=PROFILE_LIMIT)
def _process_form(request, domain, app_id, user_id, authenticated,
                  auth_cls=AuthContext, is_api=False):
    if authenticated and not is_api:
        _verify_access(domain, user_id, request)

    if rate_limit_submission(domain):
        return HttpTooManyRequests()

    metric_tags = {
        'backend': 'sql',
        'domain': domain
    }

    try:
        instance, attachments = couchforms.get_instance_and_attachment(request)
    except MultimediaBug:
        try:
            instance = request.FILES[MAGIC_PROPERTY].read()
            xform = convert_xform_to_json(instance)
            meta = xform.get("meta", {})
        except Exception:
            meta = {}

        metrics_counter('commcare.corrupt_multimedia_submissions', tags={
            'domain': domain, 'authenticated': authenticated
        })
        return _submission_error(
            request, "Received a submission with POST.keys()", metric_tags,
            domain, app_id, user_id, authenticated, meta,
        )
    # the order of these exceptions is relevant
    except UnprocessableFormSubmission as e:
        return openrosa_response.OpenRosaResponse(
            message=e.message, nature=openrosa_response.ResponseNature.PROCESSING_FAILURE, status=e.status_code,
        ).response()
    except BadSubmissionRequest as e:
        response = HttpResponse(e.message, status=e.status_code)
        _record_metrics(metric_tags, 'known_failures', response)
        return response

    if should_ignore_submission(request):
        # silently ignore submission if it meets ignore-criteria
        response = openrosa_response.SUBMISSION_IGNORED_RESPONSE
        _record_metrics(metric_tags, 'ignored', response)
        return response

    if toggles.FORM_SUBMISSION_BLACKLIST.enabled(domain):
        response = openrosa_response.BLACKLISTED_RESPONSE
        _record_metrics(metric_tags, 'blacklisted', response)
        return response

    with TimingContext() as timer:
        app_id, build_id = get_app_and_build_ids(domain, app_id)
        submission_post = SubmissionPost(
            instance=instance,
            attachments=attachments,
            domain=domain,
            app_id=app_id,
            build_id=build_id,
            auth_context=auth_cls(
                domain=domain,
                user_id=user_id,
                authenticated=authenticated,
            ),
            location=couchforms.get_location(request),
            received_on=couchforms.get_received_on(request),
            date_header=couchforms.get_date_header(request),
            path=couchforms.get_path(request),
            submit_ip=couchforms.get_submit_ip(request),
            last_sync_token=couchforms.get_last_sync_token(request),
            openrosa_headers=couchforms.get_openrosa_headers(request),
            force_logs=request.GET.get('force_logs', 'false') == 'true',
            timing_context=timer
        )

        try:
            result = submission_post.run()
        except XFormLockError as err:
            logging.warning('Unable to get lock for form %s', err)
            metrics_counter('commcare.xformlocked.count', tags={
                'domain': domain, 'authenticated': authenticated
            })
            return _submission_error(
                request, "XFormLockError: %s" % err,
                metric_tags, domain, app_id, user_id, authenticated, status=423,
                notify=False,
            )

    response = result.response
    response.request_timer = timer  # logged as Sentry breadcrumbs in LogLongRequestMiddleware

    _record_metrics(metric_tags, result.submission_type, result.response, timer, result.xform)

    return response


def _submission_error(request, message, metric_tags,
        domain, app_id, user_id, authenticated, meta=None, status=400,
        notify=True):
    """Notify exception, datadog count, record metrics, construct response

    :param status: HTTP status code (default: 400).
    :returns: HTTP response object
    """
    details = [
        "domain:{}".format(domain),
        "authenticated:{}".format(authenticated),
    ]
    if notify:
        details.extend([
            "user_id:{}".format(user_id),
            "form_meta:{}".format(meta or {}),
            "app_id:{}".format(app_id),
        ])
        notify_exception(request, message, details)
    response = HttpResponseBadRequest(
        message, status=status, content_type="text/plain")
    _record_metrics(metric_tags, 'error', response)
    return response


def _record_metrics(tags, submission_type, response, timer=None, xform=None):
    tags.update({
        'submission_type': submission_type,
        'status_code': response.status_code
    })

    if xform and xform.metadata and xform.metadata.timeEnd and xform.received_on:
        lag = xform.received_on - xform.metadata.timeEnd
        lag_days = lag.total_seconds() / 86400
        metrics_histogram(
            'commcare.xform_submissions.lag.days', lag_days,
            bucket_tag='lag', buckets=(1, 2, 4, 7, 14, 31, 90), bucket_unit='d',
            tags=tags
        )

    if timer:
        metrics_histogram(
            'commcare.xform_submissions.duration.seconds', timer.duration,
            bucket_tag='duration', buckets=(1, 5, 20, 60, 120, 300, 600), bucket_unit='s',
            tags=tags
        )

    metrics_counter('commcare.xform_submissions.count', tags=tags)


@waf_allow('XSS_BODY')
@csrf_exempt
@api_auth()
@require_permission(HqPermissions.edit_data)
@require_permission(HqPermissions.access_api)
@require_POST
@check_domain_migration
@set_request_duration_reporting_threshold(60)
def post_api(request, domain):
    return _process_form(
        request=request,
        domain=domain,
        app_id=None,
        user_id=request.couch_user.get_id,
        authenticated=True,
        is_api=True,
    )


@waf_allow('XSS_BODY')
@location_safe
@csrf_exempt
@require_POST
@check_domain_migration
@set_request_duration_reporting_threshold(60)
def post(request, domain, app_id=None):
    try:
        if domain_requires_auth(domain):
            # "redirect" to the secure version
            # an actual redirect doesn't work because it becomes a GET
            return secure_post(request, domain, app_id)
    except ResourceNotFound:
        return HttpResponseBadRequest(
            'No domain with name %s' % domain
        )
    return _process_form(
        request=request,
        domain=domain,
        app_id=app_id,
        user_id=None,
        authenticated=False,
    )


def _noauth_post(request, domain, app_id=None):
    """
    This is explicitly called for a submission that has secure submissions enabled, but is manually
    overriding the submit URL to not specify auth context. It appears to be used by demo mode.

    It mainly just checks that we are touching test data only in the right domain and submitting
    as demo_user.
    """
    try:
        instance, _ = couchforms.get_instance_and_attachment(request)
    except BadSubmissionRequest as e:
        return HttpResponseBadRequest(e.message)

    form_json = convert_xform_to_json(instance)
    case_updates = get_case_updates(form_json)

    def form_ok(form_json):
        return (from_demo_user(form_json) or is_device_report(form_json))

    def case_block_ok(case_updates):
        """
        Check for all cases that we are submitting as demo_user and that the domain we
        are submitting against for any previously existing cases matches the submission
        domain.
        """
        allowed_ids = ('demo_user', 'demo_user_group_id', None)
        case_ids = set()
        for case_update in case_updates:
            case_ids.add(case_update.id)
            create_action = case_update.get_create_action()
            update_action = case_update.get_update_action()
            index_action = case_update.get_index_action()
            if create_action:
                if create_action.user_id not in allowed_ids:
                    return False
                if create_action.owner_id not in allowed_ids:
                    return False
            if update_action:
                if update_action.owner_id not in allowed_ids:
                    return False
            if index_action:
                for index in index_action.indices:
                    case_ids.add(index.referenced_id)

        # todo: consider whether we want to remove this call, and/or pass the result
        # through to the next function so we don't have to get the cases again later
        cases = CommCareCase.objects.get_cases(list(case_ids), domain)
        for case in cases:
            if case.domain != domain:
                return False
            if case.owner_id or case.user_id not in allowed_ids:
                return False
        return True

    if not (form_ok(form_json) and case_block_ok(case_updates)):
        if request.GET.get('submit_mode') != DEMO_SUBMIT_MODE:
            # invalid submissions under demo mode submission can be processed
            return HttpResponseForbidden()

    return _process_form(
        request=request,
        domain=domain,
        app_id=app_id,
        user_id=None,
        authenticated=False,
        auth_cls=WaivedAuthContext,
    )


@login_or_digest_ex(allow_cc_users=True)
@two_factor_exempt
@set_request_duration_reporting_threshold(60)
def _secure_post_digest(request, domain, app_id=None):
    """only ever called from secure post"""
    return _process_form(
        request=request,
        domain=domain,
        app_id=app_id,
        user_id=request.couch_user.get_id,
        authenticated=True,
    )


@handle_401_response
@login_or_basic_ex(allow_cc_users=True)
@two_factor_exempt
@set_request_duration_reporting_threshold(60)
def _secure_post_basic(request, domain, app_id=None):
    """only ever called from secure post"""
    return _process_form(
        request=request,
        domain=domain,
        app_id=app_id,
        user_id=request.couch_user.get_id,
        authenticated=True,
    )


@handle_401_response
@login_or_oauth2_ex(allow_cc_users=True, oauth_scopes=['sync'])
@two_factor_exempt
@set_request_duration_reporting_threshold(60)
def _secure_post_oauth2(request, domain, app_id=None):
    """only ever called from secure post"""
    return _process_form(
        request=request,
        domain=domain,
        app_id=app_id,
        user_id=request.couch_user.get_id,
        authenticated=True,
    )


@login_or_api_key_ex()
@require_permission(HqPermissions.edit_data)
@require_permission(HqPermissions.access_api)
@set_request_duration_reporting_threshold(60)
def _secure_post_api_key(request, domain, app_id=None):
    """only ever called from secure post"""
    return _process_form(
        request=request,
        domain=domain,
        app_id=app_id,
        user_id=request.couch_user.get_id,
        authenticated=True,
    )


@waf_allow('XSS_BODY')
@location_safe
@csrf_exempt
@require_POST
@check_domain_migration
@set_request_duration_reporting_threshold(60)
def secure_post(request, domain, app_id=None):
    authtype_map = {
        DIGEST: _secure_post_digest,
        BASIC: _secure_post_basic,
        NOAUTH: _noauth_post,
        API_KEY: _secure_post_api_key,
        OAUTH2: _secure_post_oauth2,
    }

    if request.GET.get('authtype'):
        authtype = request.GET['authtype']
    else:
        authtype = determine_authtype_from_request(request, default=BASIC)

    try:
        decorated_view = authtype_map[authtype]
    except KeyError:
        return HttpResponseBadRequest(
            'authtype must be one of: {0}'.format(','.join(authtype_map))
        )

    return decorated_view(request, domain, app_id=app_id)
