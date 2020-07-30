from celery.task import task
from collections import defaultdict

from django.conf import settings
from django.utils.translation import ugettext as _
from django.urls import reverse

from dimagi.utils.logging import notify_exception
from dimagi.utils.web import get_url_base

from corehq import toggles
from corehq.apps.app_manager.dbaccessors import get_apps_in_domain
from corehq.apps.app_manager.util import is_linked_app
from corehq.apps.app_manager.views.utils import update_linked_app
from corehq.apps.hqwebapp.tasks import send_html_email_async
from corehq.apps.linked_domain.const import MODEL_APP, MODEL_CASE_SEARCH, MODEL_REPORT
from corehq.apps.linked_domain.dbaccessors import get_linked_domains
from corehq.apps.linked_domain.ucr import update_linked_ucr
from corehq.apps.linked_domain.updates import update_model_type
from corehq.apps.linked_domain.util import pull_missing_multimedia_for_app_and_notify
from corehq.apps.userreports.dbaccessors import get_report_configs_for_domain
from corehq.apps.userreports.models import ReportConfiguration
from corehq.apps.users.models import CouchUser


@task(queue='background_queue')
def pull_missing_multimedia_for_app_and_notify_task(domain, app_id, email=None):
    pull_missing_multimedia_for_app_and_notify(domain, app_id, email)


@task(queue='background_queue')
def push_models(master_domain, models, linked_domains, build_apps, username):
    user = CouchUser.get_by_username(username)
    manager = ReleaseManager(master_domain, user)
    manager.release(models, linked_domains, build_apps)
    manager.send_email()


class ReleaseManager():
    def __init__(self, master_domain, user):
        self.master_domain = master_domain
        self.user = user
        self.linked_domains = []
        self.models = []
        self._reset()

    def _reset(self, models=None, linked_domains=None):
        self.errors_by_domain = {'html': defaultdict(list), 'text': defaultdict(list)}
        self.successes_by_domain = {'html': defaultdict(list), 'text': defaultdict(list)}
        self.models = models or []
        self.linked_domains = linked_domains or []

    def _add_error(self, domain, html, text=None):
        text = text or html
        self.errors_by_domain['html'][domain].append(html)
        self.errors_by_domain['text'][domain].append(text)

    def _add_success(self, domain, html, text=None):
        text = text or html
        self.successes_by_domain['html'][domain].append(html)
        self.successes_by_domain['text'][domain].append(text)

    def _get_error_domain_count(self):
        return len(self.errors_by_domain['html'])

    def _get_success_domain_count(self):
        return len(self.linked_domains) - self._get_error_domain_count()

    def _get_errors(self, domain, html=True):
        return self.errors_by_domain['html' if html else 'text'][domain]

    def _get_successes(self, domain, html=True):
        return self.successes_by_domain['html' if html else 'text'][domain]

    def release(self, models, linked_domains, build_apps=False):
        self._reset(models, linked_domains)
        domain_links_by_linked_domain = {
            link.linked_domain: link for link in get_linked_domains(self.master_domain)
        }
        for linked_domain in self.linked_domains:
            if linked_domain not in domain_links_by_linked_domain:
                self._add_error(linked_domain, _("Project space {} is no longer linked to {}. No content "
                                                 "was released to it.").format(self.master_domain, linked_domain))
                continue

            self.release_domain(domain_links_by_linked_domain[linked_domain], build_apps)

    def release_domain(self, domain_link, build_apps=False):
        for model in self.models:
            errors = None
            try:
                if model['type'] == MODEL_APP:
                    errors = self._release_app(domain_link, model, self.user, build_apps)
                elif model['type'] == MODEL_REPORT:
                    errors = self._release_report(domain_link, model)
                elif model['type'] == MODEL_CASE_SEARCH:
                    errors = self._release_case_search(domain_link, model, self.user)
                else:
                    errors = self._release_model(domain_link, model, self.user)
            except Exception as e:   # intentionally broad
                errors = [str(e), str(e)]
                notify_exception(None, "Exception pushing linked domains: {}".format(e))

            if errors:
                self._add_error(
                    domain_link.linked_domain,
                    _("Could not update {}: {}").format(model['name'], errors[0]),
                    text=_("Could not update {}: {}").format(model['name'], errors[1]))
            else:
                self._add_success(domain_link.linked_domain, _("Updated {} successfully").format(model['name']))

    def send_email(self):
        subject = _("Linked project release complete.")
        if self.errors_by_domain:
            subject += _(" Errors occurred.")
        email = self.user.email or self.user.username
        send_html_email_async.delay(
            subject,
            email,
            self.get_email_message(html=True),
            text_content=self.get_email_message(html=False),
            email_from=settings.DEFAULT_FROM_EMAIL
        )

    def get_email_message(self, html=True):
        error_domain_count = self._get_error_domain_count()
        message = _("""
Release complete. {} project(s) succeeded. {}

The following content was released:
{}

The following linked project spaces received content:
        """).format(
            self._get_success_domain_count(),
            _("{} project(s) encountered errors.").format(error_domain_count) if error_domain_count else "",
            "\n".join(["- " + m['name'] for m in self.models])
        )
        for linked_domain in self.linked_domains:
            if not self._get_errors(linked_domain, html):
                message += _("\n- {} updated successfully").format(linked_domain)
            else:
                message += _("\n- {} encountered errors:").format(linked_domain)
                for msg in self._get_errors(linked_domain, html) + self._get_successes(linked_domain, html):
                    message += "\n   - " + msg
        return message

    def _release_app(self, domain_link, model, user, build_and_release=False):
        if toggles.MULTI_MASTER_LINKED_DOMAINS.enabled(domain_link.linked_domain):
            return self._error_tuple(_("Multi master flag is in use"))

        app_id = model['detail']['app_id']
        found = False
        error_prefix = ""
        try:
            for linked_app in get_apps_in_domain(domain_link.linked_domain, include_remote=False):
                if is_linked_app(linked_app) and linked_app.family_id == app_id:
                    found = True
                    app = update_linked_app(linked_app, app_id, user.user_id)

            if not found:
                return self._error_tuple(_("Could not find app"))

            if build_and_release:
                error_prefix = _("Updated app but did not build or release: ")
                build = app.make_build()
                build.is_released = True
                build.save(increment_version=False)
        except Exception as e:  # intentionally broad
            return self._error_tuple(error_prefix + str(e))

    def _release_report(self, domain_link, model):
        report_id = model['detail']['report_id']
        found = False
        for linked_report in get_report_configs_for_domain(domain_link.linked_domain):
            if linked_report.report_meta.master_id == report_id:
                found = True
                update_linked_ucr(domain_link, linked_report.get_id)

        if not found:
            report = ReportConfiguration.get(report_id)
            if report.report_meta.created_by_builder:
                view = 'edit_report_in_builder'
            else:
                view = 'edit_configurable_report'
            url = get_url_base() + reverse(view, args=[domain_link.master_domain, report_id])
            return self._error_tuple(
                _('Could not find report. <a href="{}">Click here</a> and click "Link Report" to link this '
                  + 'report.').format(url),
                text=_('Could not find report. Please check that the report has been linked.'),
            )

    def _release_case_search(self, domain_link, model, user):
        if not toggles.SYNC_SEARCH_CASE_CLAIM.enabled(domain_link.linked_domain):
            return self._error_tuple(_("Case claim flag is not on"))

        return self._release_model(domain_link, model, user)

    def _release_model(self, domain_link, model, user):
        update_model_type(domain_link, model['type'], model_detail=model['detail'])
        domain_link.update_last_pull(model['type'], user._id, model_detail=model['detail'])

    def _error_tuple(self, html, text=None):
        text = text or html
        return (html, text)
