from distutils.version import LooseVersion

from django.http import JsonResponse
from django.urls import reverse
from django.shortcuts import redirect
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext_noop
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_GET

from dimagi.utils.logging import notify_exception
from dimagi.utils.couch.cache.cache_core import get_redis_default_cache
from django_prbac.utils import has_privilege
from casexml.apps.case.cleanup import claim_case, get_first_claim
from casexml.apps.case.fixtures import CaseDBFixture
from casexml.apps.case.models import CommCareCase
from casexml.apps.case.xml import V2
from corehq import toggles, privileges
from corehq.const import OPENROSA_VERSION_MAP, OPENROSA_DEFAULT_VERSION
from corehq.middleware import OPENROSA_VERSION_HEADER
from corehq.apps.app_manager.dbaccessors import get_app
from corehq.apps.case_search.models import QueryMergeException
from corehq.apps.case_search.utils import CaseSearchCriteria
from corehq.apps.domain.decorators import (
    domain_admin_required,
    login_or_digest_or_basic_or_apikey,
    check_domain_migration,
    login_or_digest_or_basic_or_apikey_or_token,
)
from corehq.util.datadog.gauges import datadog_counter, datadog_histogram
from corehq.apps.domain.models import Domain
from corehq.apps.domain.views import DomainViewMixin, EditMyProjectSettingsView
from corehq.apps.es.case_search import flatten_result
from corehq.apps.hqwebapp.views import BaseSectionPageView
from corehq.apps.ota.forms import PrimeRestoreCacheForm, AdvancedPrimeRestoreCacheForm
from corehq.apps.ota.tasks import queue_prime_restore
from corehq.apps.users.models import CommCareUser, CouchUser
from corehq.apps.locations.permissions import location_safe
from corehq.form_processor.exceptions import CaseNotFound
from dimagi.utils.decorators.memoized import memoized
from casexml.apps.phone.restore import RestoreConfig, RestoreParams, RestoreCacheSettings
from django.http import HttpResponse
from soil import MultipleTaskDownload

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
    tags = [
        u'status_code:{}'.format(response.status_code),
    ]
    datadog_counter('commcare.restores.count', tags=tags)
    if timing_context is not None:
        for timer in timing_context.to_list(exclude_root=True):
            # Only record leaf nodes so we can sum to get the total
            if timer.is_leaf_node:
                datadog_histogram(
                    'commcare.restores.timings',
                    timer.duration,
                    tags=tags + [u'segment:{}'.format(timer.name)],
                )

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
        results = search_es.values()
    except Exception as e:
        return _handle_es_exception(request, e, case_search_criteria.query_addition_debug_details)

    # Even if it's a SQL domain, we just need to render the results as cases, so CommCareCase.wrap will be fine
    cases = [CommCareCase.wrap(flatten_result(result)) for result in results]
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
    restore_user = get_restore_user(domain, request.couch_user, as_user)
    cache = get_redis_default_cache()

    case_id = request.POST.get('case_id', None)
    if case_id is None:
        return HttpResponse('A case_id is required', status=400)

    try:
        if (
            cache.get(_claim_key(restore_user.user_id)) == case_id or
            get_first_claim(domain, restore_user.user_id, case_id)
        ):
            return HttpResponse('You have already claimed that {}'.format(request.POST.get('case_type', 'case')),
                                status=409)

        claim_case(domain, restore_user.user_id, case_id,
                   host_type=request.POST.get('case_type'), host_name=request.POST.get('case_name'))
    except CaseNotFound:
        return HttpResponse('The case "{}" you are trying to claim was not found'.format(case_id),
                            status=410)
    cache.set(_claim_key(restore_user.user_id), case_id)
    return HttpResponse(status=200)


def _claim_key(user_id):
    return u'last_claimed_case_case_id-{}'.format(user_id)


def get_restore_params(request):
    """
    Given a request, get the relevant restore parameters out with sensible defaults
    """
    # not a view just a view util
    try:
        openrosa_headers = getattr(request, 'openrosa_headers', {})
        openrosa_version = openrosa_headers[OPENROSA_VERSION_HEADER]
    except KeyError:
        openrosa_version = request.GET.get('openrosa_version', OPENROSA_DEFAULT_VERSION)

    return {
        'since': request.GET.get('since'),
        'version': request.GET.get('version', "2.0"),
        'state': request.GET.get('state'),
        'items': request.GET.get('items') == 'true',
        'as_user': request.GET.get('as'),
        'has_data_cleanup_privelege': has_privilege(request, privileges.DATA_CLEANUP),
        'overwrite_cache': request.GET.get('overwrite_cache') == 'true',
        'openrosa_version': openrosa_version,
        'device_id': request.GET.get('device_id'),
        'user_id': request.GET.get('user_id'),
        'case_sync': request.GET.get('case_sync'),
    }


def get_restore_response(domain, couch_user, app_id=None, since=None, version='1.0',
                         state=None, items=False, force_cache=False,
                         cache_timeout=None, overwrite_cache=False,
                         force_restore_mode=None,
                         as_user=None, device_id=None, user_id=None,
                         has_data_cleanup_privelege=False,
                         openrosa_version=OPENROSA_DEFAULT_VERSION,
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

    # not a view just a view util
    is_permitted, message = is_permitted_to_restore(
        domain,
        couch_user,
        as_user,
        has_data_cleanup_privelege,
    )
    if not is_permitted:
        return HttpResponse(message, status=401), None

    is_demo_restore = couch_user.is_commcare_user() and couch_user.is_demo_user
    is_enikshay = toggles.ENIKSHAY.enabled(domain)
    if is_enikshay:
        couch_restore_user = couch_user
        if not is_demo_restore and as_user is not None:
            couch_restore_user = CouchUser.get_by_username(as_user)
        update_device_id(couch_restore_user, device_id)

    if is_demo_restore:
        # if user is in demo-mode, return demo restore
        return demo_user_restore_response(couch_user), None

    restore_user = get_restore_user(domain, couch_user, as_user)
    if not restore_user:
        return HttpResponse('Could not find user', status=404), None

    project = Domain.get_by_name(domain)
    app = get_app(domain, app_id) if app_id else None
    async_restore_enabled = (
        toggles.ASYNC_RESTORE.enabled(domain) and
        LooseVersion(openrosa_version) >= LooseVersion(OPENROSA_VERSION_MAP['ASYNC_RESTORE'])
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
        ),
        cache_settings=RestoreCacheSettings(
            force_cache=force_cache or async_restore_enabled,
            cache_timeout=cache_timeout,
            overwrite_cache=overwrite_cache
        ),
        async=async_restore_enabled,
        case_sync=case_sync,
    )
    return restore_config.get_response(), restore_config.timing_context


class PrimeRestoreCacheView(BaseSectionPageView, DomainViewMixin):
    page_title = ugettext_noop("Speed up 'Sync with Server'")
    section_name = ugettext_noop("Project Settings")
    urlname = 'prime_restore_cache'
    template_name = "ota/prime_restore_cache.html"

    @method_decorator(domain_admin_required)
    @method_decorator(toggles.PRIME_RESTORE.required_decorator())
    def dispatch(self, *args, **kwargs):
        return super(PrimeRestoreCacheView, self).dispatch(*args, **kwargs)

    @property
    def main_context(self):
        main_context = super(PrimeRestoreCacheView, self).main_context
        main_context.update({
            'domain': self.domain,
        })
        main_context.update({
            'is_project_settings': True,
        })
        return main_context

    @property
    @memoized
    def page_url(self):
        if self.urlname:
            return reverse(self.urlname, args=[self.domain])

    @property
    @memoized
    def section_url(self):
        return reverse(EditMyProjectSettingsView.urlname, args=[self.domain])

    @property
    @memoized
    def form(self):
        if self.request.method == 'POST':
            return PrimeRestoreCacheForm(self.request.POST)
        return PrimeRestoreCacheForm()

    @property
    def page_context(self):
        return {
            'form': self.form,
        }

    def post(self, request, *args, **kwargs):
        if self.form.is_valid():
            return self.form_valid()
        return self.get(request, *args, **kwargs)

    def form_valid(self):
        res = queue_prime_restore(
            self.domain,
            CommCareUser.ids_by_domain(self.domain),
            version=V2,
            cache_timeout_hours=24,
            overwrite_cache=True,
            check_cache_only=False
        )
        download = MultipleTaskDownload()
        download.set_task(res)
        download.save()

        return redirect('hq_soil_download', self.domain, download.download_id)


class AdvancedPrimeRestoreCacheView(PrimeRestoreCacheView):
    template_name = "ota/advanced_prime_restore_cache.html"
    urlname = 'advanced_prime_restore_cache'

    @property
    @memoized
    def form(self):
        if self.request.method == 'POST':
            return AdvancedPrimeRestoreCacheForm(self.request.POST)
        return AdvancedPrimeRestoreCacheForm()

    def form_valid(self):
        if self.form.cleaned_data['all_users']:
            user_ids = CommCareUser.ids_by_domain(self.domain)
        else:
            user_ids = self.form.user_ids

        res = queue_prime_restore(
            self.domain,
            user_ids,
            version=V2,
            cache_timeout_hours=24,
            overwrite_cache=self.form.cleaned_data['overwrite_cache'],
            check_cache_only=self.form.cleaned_data['check_cache_only']
        )
        download = MultipleTaskDownload()
        download.set_task(res)
        download.save()

        return redirect('hq_soil_download', self.domain, download.download_id)


@login_or_digest_or_basic_or_apikey()
@require_GET
def heartbeat(request, domain, id):
    # mobile needs this. This needs to be revisited to actually work dynamically (Sravan June 7, 17)
    return JsonResponse({
        "app_id": "value_copied_from_app_id_url_param",
        "latest_apk_version": {"value": ""},
        "latest_ccz_version": {"value": ""}
    })
