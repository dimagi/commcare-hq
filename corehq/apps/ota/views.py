from distutils.version import LooseVersion

from django.http import JsonResponse, Http404
from django.urls import reverse
from django.shortcuts import redirect
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext_noop
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_GET

from dimagi.utils.logging import notify_exception
from casexml.apps.case.cleanup import claim_case, get_first_claim
from casexml.apps.case.fixtures import CaseDBFixture
from casexml.apps.case.models import CommCareCase
from casexml.apps.case.xml import V2

from corehq import toggles
from corehq.const import OPENROSA_VERSION_MAP
from corehq.middleware import OPENROSA_VERSION_HEADER
from corehq.apps.app_manager.util import get_app, LatestAppInfo
from corehq.apps.case_search.models import QueryMergeException
from corehq.apps.case_search.utils import CaseSearchCriteria
from corehq.apps.domain.decorators import (
    domain_admin_required,
    login_or_digest_or_basic_or_apikey,
    check_domain_migration,
    login_or_digest_or_basic_or_apikey_or_token,
)
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
    restore_user = get_restore_user(domain, request.couch_user, as_user)

    case_id = request.POST.get('case_id', None)
    if case_id is None:
        return HttpResponse('A case_id is required', status=400)

    try:
        if get_first_claim(domain, restore_user.user_id, case_id):
            return HttpResponse('You have already claimed that {}'.format(request.POST.get('case_type', 'case')),
                                status=409)

        claim_case(domain, restore_user.user_id, case_id,
                   host_type=request.POST.get('case_type'), host_name=request.POST.get('case_name'))
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
                         force_restore_mode=None,
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

    # not a view just a view util
    is_permitted, message = is_permitted_to_restore(
        domain,
        couch_user,
        as_user,
    )
    if not is_permitted:
        return HttpResponse(message, status=401), None

    is_demo_restore = couch_user.is_commcare_user() and couch_user.is_demo_user
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
def heartbeat(request, domain, hq_app_id):
    """
    An endpoint for CommCare mobile to get latest CommCare APK and app version
        info. (Should serve from cache as it's going to be busy view)

    'hq_app_id' (that comes from URL) can be id of any version of the app
    'app_id' (urlparam) is usually id of an app that is not a copy
        mobile simply needs it to be resent back in the JSON, and doesn't
        need any validation on it. This is pulled from @uniqueid from profile.xml
    """
    url_param_app_id = request.GET.get('app_id', '')
    info = {"app_id": url_param_app_id}
    try:
        # mobile will send brief_app_id
        info.update(LatestAppInfo(url_param_app_id, domain).get_info())
    except (Http404, AssertionError):
        # If it's not a valid 'brief' app id, find it by talking to couch
        notify_exception(request, 'Received an invalid heartbeat request')
        app = get_app(domain, hq_app_id)
        brief_app_id = app.copy_of or app.id
        info.update(LatestAppInfo(brief_app_id, domain).get_info())

    return JsonResponse(info)
