from collections import defaultdict

from django.conf import settings
from django.template.defaultfilters import linebreaksbr
from django.urls import reverse
from django.utils.translation import ugettext as _

from celery import chord
from celery.task import task

from dimagi.utils.logging import notify_exception
from dimagi.utils.web import get_url_base

from corehq import toggles
from corehq.apps.accounting.utils import domain_has_privilege
from corehq.apps.app_manager.dbaccessors import get_apps_in_domain
from corehq.apps.app_manager.util import is_linked_app
from corehq.apps.app_manager.views.utils import update_linked_app
from corehq.apps.hqwebapp.tasks import send_html_email_async
from corehq.apps.linked_domain.const import (
    FEATURE_FLAG_DATA_MODEL_TOGGLES,
    MODEL_APP,
    MODEL_KEYWORD,
    MODEL_REPORT,
)
from corehq.apps.linked_domain.dbaccessors import get_upstream_domain_link
from corehq.apps.linked_domain.exceptions import DomainLinkError
from corehq.apps.linked_domain.keywords import (
    create_linked_keyword,
    update_keyword,
)
from corehq.apps.linked_domain.models import (
    KeywordLinkDetail,
    ReportLinkDetail,
)
from corehq.apps.linked_domain.ucr import (
    create_linked_ucr,
    get_downstream_report,
    update_linked_ucr,
)
from corehq.apps.linked_domain.updates import update_model_type
from corehq.apps.linked_domain.util import (
    pull_missing_multimedia_for_app_and_notify,
)
from corehq.apps.reminders.views import KeywordsListView
from corehq.apps.sms.models import Keyword
from corehq.apps.userreports.models import ReportConfiguration
from corehq.apps.users.models import CouchUser
from corehq.privileges import RELEASE_MANAGEMENT


@task(queue='linked_domain_queue')
def pull_missing_multimedia_for_app_and_notify_task(domain, app_id, email=None):
    pull_missing_multimedia_for_app_and_notify(domain, app_id, email)


@task(queue='linked_domain_queue')
def push_models(upstream_domain, models, downstream_domains, build_apps, username):
    ReleaseManager(upstream_domain, username).release(models, downstream_domains, build_apps)


class ReleaseManager:
    def __init__(self, upstream_domain, username):
        self.upstream_domain = upstream_domain
        self.user = CouchUser.get_by_username(username)
        self._reset()

    def _reset(self):
        self.errors_by_domain = {'html': defaultdict(list), 'text': defaultdict(list)}
        self.successes_by_domain = {'html': defaultdict(list), 'text': defaultdict(list)}

    def results(self):
        return self.successes_by_domain, self.errors_by_domain

    def add_error(self, domain, html, text=None):
        text = text or html
        self.errors_by_domain['html'][domain].append(html)
        self.errors_by_domain['text'][domain].append(text)

    def add_success(self, domain, html, text=None):
        text = text or html
        self.successes_by_domain['html'][domain].append(html)
        self.successes_by_domain['text'][domain].append(text)

    def update_successes(self, successes):
        self._update_messages(self.successes_by_domain, successes)

    def update_errors(self, errors):
        self._update_messages(self.errors_by_domain, errors)

    def _update_messages(self, attr, messages):
        for fmt in ('html', 'text'):
            for domain, msgs in messages[fmt].items():
                attr[fmt][domain].extend(msgs)

    def get_error_domain_count(self):
        return len(self.errors_by_domain['html'])

    def get_success_domain_count(self):
        return len(self.successes_by_domain['html'])

    def _get_errors(self, domain, html=True):
        return self.errors_by_domain['html' if html else 'text'][domain]

    def _get_successes(self, domain, html=True):
        return self.successes_by_domain['html' if html else 'text'][domain]

    def release(self, models, downstream_domains, build_apps=False):
        self._reset()
        header = [
            release_domain.si(self.upstream_domain, downstream_domain, self.user.username, models, build_apps)
            for downstream_domain in downstream_domains
        ]
        callback = send_linked_domain_release_email.s(self.upstream_domain, self.user.username,
                                                      models, downstream_domains)
        chord(header)(callback)

    def get_email_message(self, models, linked_domains, html=True):
        error_domain_count = self.get_error_domain_count()
        separator = "\n"
        message = _("""
Release complete. {} project(s) succeeded. {}

The following content was released:
{}

The following linked project spaces received content:
        """).format(
            self.get_success_domain_count(),
            _("{} project(s) encountered errors.").format(error_domain_count) if error_domain_count else "",
            separator.join(["- {}".format(m['name']) for m in models])
        ).strip()
        for linked_domain in sorted(linked_domains):
            if not self._get_errors(linked_domain, html):
                message += _("{}- {} updated successfully").format(separator, linked_domain)
            else:
                message += _("{}- {} encountered errors:").format(separator, linked_domain)
                for msg in self._get_errors(linked_domain, html) + self._get_successes(linked_domain, html):
                    message += separator + "   - " + msg
        return linebreaksbr(message) if html else message

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

    def _release_report(self, domain_link, model, user_id):
        report_id = model['detail']['report_id']
        linked_report = get_downstream_report(domain_link.linked_domain, report_id)

        if not linked_report:
            if domain_has_privilege(self.upstream_domain, RELEASE_MANAGEMENT):
                try:
                    linked_report_info = create_linked_ucr(domain_link, report_id)
                    linked_report = linked_report_info.report
                except DomainLinkError as e:
                    return self._error_tuple(str(e))
            else:
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

        # have no hit an error case, so update the ucr
        update_linked_ucr(domain_link, linked_report.get_id)
        domain_link.update_last_pull(
            MODEL_REPORT,
            user_id,
            model_detail=ReportLinkDetail(report_id=linked_report.get_id).to_json(),
        )

    def _release_flag_dependent_model(self, domain_link, model, user, feature_flag):
        if not feature_flag.enabled(domain_link.linked_domain):
            return self._error_tuple(_("Feature flag for {} is not enabled").format(model['name']))

        return self._release_model(domain_link, model, user)

    def _release_keyword(self, domain_link, model, user_id):
        upstream_id = model['detail']['keyword_id']
        try:
            linked_keyword_id = (Keyword.objects.values_list('id', flat=True)
                                 .get(domain=domain_link.linked_domain, upstream_id=upstream_id))
        except Keyword.DoesNotExist:
            if domain_has_privilege(self.upstream_domain, RELEASE_MANAGEMENT):
                linked_keyword_id = create_linked_keyword(domain_link, upstream_id)
            else:
                return self._error_tuple(
                    _('Could not find linked keyword in {domain}. '
                      'Please check that the keyword has been linked from the '
                      '<a href="{keyword_url}">Keyword Page</a>.').format(
                        domain=domain_link.linked_domain,
                        keyword_url=(
                            get_url_base() + reverse(
                                KeywordsListView.urlname, args=[domain_link.master_domain]
                            ))
                    ),
                    _('Could not find linked keyword. Please check the keyword has been linked.'),
                )

        update_keyword(domain_link, linked_keyword_id)
        domain_link.update_last_pull(
            MODEL_KEYWORD,
            user_id,
            model_detail=KeywordLinkDetail(keyword_id=str(linked_keyword_id)).to_json(),
        )

    def _release_model(self, domain_link, model, user):
        update_model_type(domain_link, model['type'], model_detail=model['detail'])
        domain_link.update_last_pull(model['type'], user._id, model_detail=model['detail'])

    def _error_tuple(self, html, text=None):
        text = text or html
        return (html, text)


@task(queue='linked_domain_queue')
def release_domain(upstream_domain, downstream_domain, username, models, build_apps=False):
    manager = ReleaseManager(upstream_domain, username)

    domain_link = get_upstream_domain_link(downstream_domain)
    if not domain_link or domain_link.master_domain != upstream_domain:
        manager.add_error(downstream_domain, _("Project space {} is no longer linked to {}. No content "
                                           "was released to it.").format(upstream_domain, downstream_domain))
        return manager.results()

    for model in models:
        errors = None
        try:
            if model['type'] == MODEL_APP:
                errors = manager._release_app(domain_link, model, manager.user, build_apps)
            elif model['type'] == MODEL_REPORT:
                errors = manager._release_report(domain_link, model, manager.user._id)
            elif model['type'] in FEATURE_FLAG_DATA_MODEL_TOGGLES:
                errors = manager._release_flag_dependent_model(domain_link, model, manager.user,
                                                               FEATURE_FLAG_DATA_MODEL_TOGGLES[model['type']])
            elif model['type'] == MODEL_KEYWORD:
                errors = manager._release_keyword(domain_link, model, manager.user._id)
            else:
                manager._release_model(domain_link, model, manager.user)
        except Exception as e:   # intentionally broad
            errors = [str(e), str(e)]
            notify_exception(None, "Exception pushing linked domains: {}".format(e))

        if errors:
            manager.add_error(
                domain_link.linked_domain,
                _("Could not update {}: {}").format(model['name'], errors[0]),
                text=_("Could not update {}: {}").format(model['name'], errors[1]))
        else:
            manager.add_success(domain_link.linked_domain, _("Updated {} successfully").format(model['name']))

    return manager.results()


@task(queue='linked_domain_queue')
def send_linked_domain_release_email(results, upstream_domain, username, models, downstream_domains):
    manager = ReleaseManager(upstream_domain, username)

    # chord sends a list of results only if there were multiple tasks
    if len(downstream_domains) == 1:
        results = [results]

    for result in results:
        (successes, errors) = result
        manager.update_successes(successes)
        manager.update_errors(errors)

    subject = _("Linked project release complete.")
    if manager.get_error_domain_count():
        subject += _(" Errors occurred.")

    email = manager.user.email or manager.user.username
    send_html_email_async(
        subject,
        email,
        manager.get_email_message(models, downstream_domains, html=True),
        text_content=manager.get_email_message(models, downstream_domains, html=False),
        email_from=settings.DEFAULT_FROM_EMAIL
    )
