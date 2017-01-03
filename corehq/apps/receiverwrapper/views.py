import logging
from couchdbkit import ResourceNotFound
from couchdbkit.ext.django.loading import get_db
from django.http import (
    HttpResponseBadRequest,
    HttpResponseForbidden,
)
from casexml.apps.case.xform import get_case_updates, is_device_report
from corehq.apps.domain.decorators import (
    check_domain_migration, login_or_digest_ex, login_or_basic_ex
)
from corehq.apps.receiverwrapper.auth import (
    AuthContext,
    WaivedAuthContext,
    domain_requires_auth,
)
from corehq.apps.receiverwrapper.util import (
    get_app_and_build_ids,
    determine_authtype,
    from_demo_user,
    should_ignore_submission,
    DEMO_SUBMIT_MODE,
)
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.form_processor.submission_post import SubmissionPost
from corehq.form_processor.utils import convert_xform_to_json, should_use_sql_backend
from corehq.util import datadog
from corehq.util.datadog.metrics import MULTIMEDIA_SUBMISSION_ERROR_COUNT
from corehq.util.datadog.utils import count_by_response_code, log_counter
from corehq.util.timer import TimingContext
import couchforms
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt

from couchforms.const import MAGIC_PROPERTY
from couchforms.getters import MultimediaBug
from dimagi.utils.logging import notify_exception
from corehq.apps.ota.utils import handle_401_response
from corehq import toggles


@count_by_response_code('commcare.xform_submissions')
def _process_form(request, domain, app_id, user_id, authenticated,
                  auth_cls=AuthContext):
    if should_ignore_submission(request):
        # silently ignore submission if it meets ignore-criteria
        return SubmissionPost.submission_ignored_response()

    if toggles.FORM_SUBMISSION_BLACKLIST.enabled(domain):
        return SubmissionPost.get_blacklisted_response()

    try:
        instance, attachments = couchforms.get_instance_and_attachment(request)
    except MultimediaBug as e:
        try:
            instance = request.FILES[MAGIC_PROPERTY].read()
            xform = convert_xform_to_json(instance)
            meta = xform.get("meta", {})
        except:
            meta = {}

        details = {
            "domain": domain,
            "app_id": app_id,
            "user_id": user_id,
            "authenticated": authenticated,
            "form_meta": meta,
        }
        log_counter(MULTIMEDIA_SUBMISSION_ERROR_COUNT, details)
        notify_exception(None, "Received a submission with POST.keys()", details)
        return HttpResponseBadRequest(e.message)

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
    )
    with TimingContext() as timer:
        response, instance, cases = submission_post.run()
    if response.status_code == 400:
        logging.error(
            'Status code 400 for a form submission. '
            'Response is: \n{0}\n'
        )
    elif response.status_code == 201:
        backend_tag = ('backend:sql' if should_use_sql_backend(domain) else
                       'backend:couch')

        datadog.statsd.gauge(
            'commcare.xform_submissions.timings', timer.duration, tags=[backend_tag])
        # normalize over number of items (form or case) saved
        datadog.statsd.gauge(
            'commcare.xform_submissions.normalized_timings',
            timer.duration/(1 + len(cases)), tags=[backend_tag])

    return response


@csrf_exempt
@require_POST
@check_domain_migration
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
    This is explictly called for a submission that has secure submissions enabled, but is manually
    overriding the submit URL to not specify auth context. It appears to be used by demo mode.

    It mainly just checks that we are touching test data only in the right domain and submitting
    as demo_user.
    """
    instance, _ = couchforms.get_instance_and_attachment(request)
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
        cases = CaseAccessors(domain).get_cases(list(case_ids))
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
def _secure_post_basic(request, domain, app_id=None):
    """only ever called from secure post"""
    return _process_form(
        request=request,
        domain=domain,
        app_id=app_id,
        user_id=request.couch_user.get_id,
        authenticated=True,
    )


@csrf_exempt
@require_POST
@check_domain_migration
def secure_post(request, domain, app_id=None):
    authtype_map = {
        'digest': _secure_post_digest,
        'basic': _secure_post_basic,
        'noauth': _noauth_post,
    }

    try:
        decorated_view = authtype_map[determine_authtype(request)]
    except KeyError:
        return HttpResponseBadRequest(
            'authtype must be one of: {0}'.format(','.join(authtype_map.keys()))
        )

    return decorated_view(request, domain, app_id=app_id)
