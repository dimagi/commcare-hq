from django.core.urlresolvers import reverse
from django.shortcuts import redirect
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext_noop
from casexml.apps.case.xml import V2
from corehq import toggles
from corehq.apps.app_manager.models import Application
from corehq.apps.domain.decorators import domain_admin_required, login_or_digest_or_basic_or_apikey
from corehq.apps.domain.models import Domain
from corehq.apps.domain.views import DomainViewMixin, EditMyProjectSettingsView
from corehq.apps.hqwebapp.models import ProjectSettingsTab
from corehq.apps.ota.forms import PrimeRestoreCacheForm
from corehq.apps.ota.tasks import prime_restore
from corehq.apps.style.views import BaseB3SectionPageView
from corehq.apps.users.models import CouchUser, CommCareUser
from corehq.util.view_utils import json_error
from dimagi.utils.decorators.memoized import memoized
from casexml.apps.phone.restore import RestoreConfig, RestoreParams, RestoreCacheSettings
from django.http import HttpResponse
from soil import DownloadBase


@json_error
@login_or_digest_or_basic_or_apikey()
def restore(request, domain, app_id=None):
    """
    We override restore because we have to supply our own 
    user model (and have the domain in the url)
    """
    user = request.user
    couch_user = CouchUser.from_django_user(user)
    return get_restore_response(domain, couch_user, app_id, **get_restore_params(request))


def get_restore_params(request):
    """
    Given a request, get the relevant restore parameters out with sensible defaults
    """
    # not a view just a view util
    return {
        'since': request.GET.get('since'),
        'version': request.GET.get('version', "1.0"),
        'state': request.GET.get('state'),
        'items': request.GET.get('items') == 'true',
        'force_restore_mode': request.GET.get('mode')
    }


def get_restore_response(domain, couch_user, app_id=None, since=None, version='1.0',
                         state=None, items=False, force_cache=False,
                         cache_timeout=None, overwrite_cache=False,
                         force_restore_mode=None):
    # not a view just a view util
    if not couch_user.is_commcare_user():
        return HttpResponse("No linked chw found for %s" % couch_user.username,
                            status=401)  # Authentication Failure
    elif domain != couch_user.domain:
        return HttpResponse("%s was not in the domain %s" % (couch_user.username, domain),
                            status=401)

    project = Domain.get_by_name(domain)
    app = Application.get_db().get(app_id) if app_id else None
    restore_config = RestoreConfig(
        project=project,
        user=couch_user.to_casexml_user(),
        app=app,
        params=RestoreParams(
            sync_log_id=since,
            version=version,
            state_hash=state,
            include_item_count=items,
            force_restore_mode=force_restore_mode,
        ),
        cache_settings=RestoreCacheSettings(
            force_cache=force_cache,
            cache_timeout=cache_timeout,
            overwrite_cache=overwrite_cache
        ),
    )
    return restore_config.get_response()


class PrimeRestoreCacheView(BaseB3SectionPageView, DomainViewMixin):
    page_title = ugettext_noop("Prime Restore Cache")
    section_name = ugettext_noop("Project Settings")
    urlname = 'prime_restore_cache'
    template_name = "ota/prime_restore_cache.html"

    @method_decorator(domain_admin_required)
    @toggles.PRIME_RESTORE.required_decorator()
    def dispatch(self, *args, **kwargs):
        return super(PrimeRestoreCacheView, self).dispatch(*args, **kwargs)

    @property
    def main_context(self):
        main_context = super(PrimeRestoreCacheView, self).main_context
        main_context.update({
            'domain': self.domain,
        })
        main_context.update({
            'active_tab': ProjectSettingsTab(
                self.request,
                self.urlname,
                domain=self.domain,
                couch_user=self.request.couch_user,
                project=self.request.project
            ),
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
        if self.form.cleaned_data['all_users']:
            user_ids = CommCareUser.ids_by_domain(self.domain)
        else:
            user_ids = self.form.user_ids

        download = DownloadBase()
        res = prime_restore.delay(
            self.domain,
            user_ids,
            version=V2,
            cache_timeout_hours=24,
            overwrite_cache=self.form.cleaned_data['overwrite_cache'],
            check_cache_only=self.form.cleaned_data['check_cache_only']
        )
        download.set_task(res)

        return redirect('hq_soil_download', self.domain, download.download_id)
