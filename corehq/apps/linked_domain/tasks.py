from celery.task import task
from collections import defaultdict

from django.conf import settings
from django.utils.translation import ugettext as _

from corehq import toggles
from corehq.apps.app_manager.dbaccessors import get_apps_in_domain
from corehq.apps.app_manager.util import is_linked_app
from corehq.apps.app_manager.views.utils import update_linked_app
from corehq.apps.hqwebapp.tasks import send_mail_async
from corehq.apps.linked_domain.const import MODEL_APP, MODEL_REPORT
from corehq.apps.linked_domain.dbaccessors import get_linked_domains
from corehq.apps.linked_domain.ucr import update_linked_ucr
from corehq.apps.linked_domain.updates import update_model_type
from corehq.apps.linked_domain.util import pull_missing_multimedia_for_app_and_notify
from corehq.apps.userreports.dbaccessors import get_report_configs_for_domain
from corehq.apps.users.models import CouchUser


@task(queue='background_queue')
def pull_missing_multimedia_for_app_and_notify_task(domain, app_id, email=None):
    pull_missing_multimedia_for_app_and_notify(domain, app_id, email)


@task(queue='background_queue')
def push_models(master_domain, models, linked_domains, build_apps, username):
    domain_links_by_linked_domain = {link.linked_domain: link for link in get_linked_domains(master_domain)}
    user = CouchUser.get_by_username(username)
    errors_by_domain = defaultdict(list)
    successes_by_domain = defaultdict(list)
    for linked_domain in linked_domains:
        if linked_domain not in domain_links_by_linked_domain:
            errors_by_domain[linked_domain].append(_("Project space {} is no longer linked to {}. No content "
                                                     "was released to it.").format(master_domain, linked_domain))
            continue
        domain_link = domain_links_by_linked_domain[linked_domain]
        for model in models:
            try:
                found = False
                updated_app = False
                built_app = False
                if model['type'] == MODEL_APP:
                    app_id = model['detail']['app_id']
                    for linked_app in get_apps_in_domain(linked_domain, include_remote=False):
                        if is_linked_app(linked_app) and linked_app.family_id == app_id:
                            found = True
                            if toggles.MULTI_MASTER_LINKED_DOMAINS.enabled(linked_domain):
                                errors_by_domain[linked_domain].append(_("""
                                    Could not update {} because multi master flag is in use
                                """.strip()).format(model['name']))
                                continue
                            app = update_linked_app(linked_app, app_id, user.user_id)
                            updated_app = True
                            if build_apps:
                                build = app.make_build()
                                build.is_released = True
                                build.save(increment_version=False)
                                built_app = True
                elif model['type'] == MODEL_REPORT:
                    report_id = model['detail']['report_id']
                    for linked_report in get_report_configs_for_domain(linked_domain):
                        if linked_report.report_meta.master_id == report_id:
                            found = True
                            update_linked_ucr(domain_link, linked_report.get_id)
                else:
                    found = True
                    update_model_type(domain_link, model['type'], model_detail=model['detail'])
                if found:
                    successes_by_domain[linked_domain].append(_("{} was updated").format(model['name']))
                else:
                    errors_by_domain[linked_domain].append(_("Could not find {}").format(model['name']))
            except Exception as e:   # intentionally broad
                if model['type'] == MODEL_APP and updated_app and build_apps and not built_app:
                    # Updating an app can be a 2-step process, make it clear which one failed
                    errors_by_domain[linked_domain].append(_("""
                        Updated {} but could not make and release build: {}
                    """.strip()).format(model['name'], str(e)))
                else:
                    errors_by_domain[linked_domain].append(_("""
                        Could not update {}: {}
                    """.strip()).format(model['name'], str(e)))

    subject = _("Linked project release complete.")
    if errors_by_domain:
        subject += _(" Errors occurred.")

    error_domain_count = len(errors_by_domain)
    success_domain_count = len(linked_domains) - error_domain_count
    message = _("""
Release complete. {} project(s) succeeded. {}

The following content was released:
{}

The following linked project spaces received content:
    """).format(
        success_domain_count,
        _("{} project(s) encountered errors.").format(error_domain_count) if error_domain_count else "",
        "\n".join(["- " + m['name'] for m in models])
    )
    for linked_domain in linked_domains:
        if linked_domain not in errors_by_domain:
            message += _("\n- {} updated successfully").format(linked_domain)
        else:
            message += _("\n- {} encountered errors:").format(linked_domain)
            for msg in errors_by_domain[linked_domain] + successes_by_domain[linked_domain]:
                message += "\n   - " + msg
    send_mail_async.delay(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email or user.username])
