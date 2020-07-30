from celery import chord
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
from corehq.apps.linked_domain.dbaccessors import get_domain_master_link
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
    ReleaseManager(master_domain, username).release(models, linked_domains, build_apps)


class ReleaseManager():
    def __init__(self, master_domain, username):
        self.master_domain = master_domain
        self.user = CouchUser.get_by_username(username)
        self._reset()

    def _reset(self):
        self.errors_by_domain = {'html': defaultdict(list), 'text': defaultdict(list)}
        self.successes_by_domain = {'html': defaultdict(list), 'text': defaultdict(list)}

    def results(self):
        return (self.successes_by_domain, self.errors_by_domain)

    def _add_error(self, domain, html, text=None):
        text = text or html
        self.errors_by_domain['html'][domain].append(html)
        self.errors_by_domain['text'][domain].append(text)

    def _add_success(self, domain, html, text=None):
        text = text or html
        self.successes_by_domain['html'][domain].append(html)
        self.successes_by_domain['text'][domain].append(text)

    def _update_successes(self, successes):
        self._update_messages(self.successes_by_domain, successes)

    def _update_errors(self, errors):
        self._update_messages(self.errors_by_domain, errors)

    def _update_messages(self, attr, messages):
        for fmt in ('html', 'text'):
            for domain, msgs in messages[fmt].items():
                attr[fmt][domain].extend(msgs)

    def _get_error_domain_count(self):
        return len(self.errors_by_domain['html'])

    def _get_success_domain_count(self):
        return len(self.successes_by_domain['html'])

    def _get_errors(self, domain, html=True):
        return self.errors_by_domain['html' if html else 'text'][domain]

    def _get_successes(self, domain, html=True):
        return self.successes_by_domain['html' if html else 'text'][domain]

    def release(self, models, linked_domains, build_apps=False):
        self._reset()
        header = [
            release_domain.si(self.master_domain, linked_domain, self.user.username, models, build_apps)
            for linked_domain in linked_domains
        ]
        callback = send_email.s(self.master_domain, self.user.username, models, linked_domains)
        chord(header)(callback)

    def get_email_message(self, models, linked_domains, html=True):
        error_domain_count = self._get_error_domain_count()
        message = _("""
Release complete. {} project(s) succeeded. {}

The following content was released:
{}

The following linked project spaces received content:
        """).format(
            self._get_success_domain_count(),
            _("{} project(s) encountered errors.").format(error_domain_count) if error_domain_count else "",
            "\n".join(["- " + m['name'] for m in models])
        )
        for linked_domain in sorted(linked_domains):
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


@task(queue='background_queue')
def release_domain(master_domain, linked_domain, username, models, build_apps=False):
    manager = ReleaseManager(master_domain, username)

    domain_link = get_domain_master_link(linked_domain)
    if not domain_link or domain_link.master_domain != master_domain:
        manager.add_error(linked_domain, _("Project space {} is no longer linked to {}. No content "
                                           "was released to it.").format(master_domain, linked_domain))
        return manager.results()

    for model in models:
        errors = None
        try:
            if model['type'] == MODEL_APP:
                errors = manager._release_app(domain_link, model, manager.user, build_apps)
            elif model['type'] == MODEL_REPORT:
                errors = manager._release_report(domain_link, model)
            elif model['type'] == MODEL_CASE_SEARCH:
                errors = manager._release_case_search(domain_link, model, manager.user)
            else:
                errors = manager._release_model(domain_link, model, manager.user)
        except Exception as e:   # intentionally broad
            errors = [str(e), str(e)]
            notify_exception(None, "Exception pushing linked domains: {}".format(e))

        if errors:
            manager._add_error(
                domain_link.linked_domain,
                _("Could not update {}: {}").format(model['name'], errors[0]),
                text=_("Could not update {}: {}").format(model['name'], errors[1]))
        else:
            manager._add_success(domain_link.linked_domain, _("Updated {} successfully").format(model['name']))

    return manager.results()


@task(queue='background_queue')
def send_email(results, master_domain, username, models, linked_domains):
    manager = ReleaseManager(master_domain, username)

    # chord sends a list of results only if there were multiple tasks
    if len(linked_domains) == 1:
        results = [results]

    for result in results:
        (successes, errors) = result
        manager._update_successes(successes)
        manager._update_errors(errors)

    subject = _("Linked project release complete.")
    if manager._get_error_domain_count():
        subject += _(" Errors occurred.")

    email = manager.user.email or manager.user.username
    send_html_email_async(
        subject,
        email,
        manager.get_email_message(models, linked_domains, html=True),
        text_content=manager.get_email_message(models, linked_domains, html=False),
        email_from=settings.DEFAULT_FROM_EMAIL
    )
