import datetime
import io
import json
import logging

from django.conf import settings
from django.contrib import messages
from django.http import Http404
from django.shortcuts import redirect
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_lazy

import dateutil
from memoized import memoized
from PIL import Image

from dimagi.utils.web import get_ip, get_site_domain

from corehq.apps.domain.decorators import domain_admin_required
from corehq.apps.domain.models import Domain
from corehq.apps.domain.views.settings import (
    BaseAdminProjectSettingsView,
    BaseProjectSettingsView,
)
from corehq.apps.fixtures.models import FixtureDataType
from corehq.apps.hqwebapp.decorators import use_jquery_ui
from corehq.apps.hqwebapp.tasks import send_html_email_async
from corehq.apps.linked_domain.dbaccessors import is_linked_domain


def _publish_snapshot(request, domain, published_snapshot=None):
    snapshots = domain.snapshots()
    for snapshot in snapshots:
        if snapshot.published:
            snapshot.published = False
            if not published_snapshot or snapshot.name != published_snapshot.name:
                snapshot.save()
    if published_snapshot:
        if published_snapshot.copied_from.name != domain.name:
            messages.error(request, "Invalid snapshot")
            return False

        # cda stuff. In order to publish a snapshot, a user must have agreed to this
        published_snapshot.cda.signed = True
        published_snapshot.cda.date = datetime.datetime.utcnow()
        published_snapshot.cda.type = 'Content Distribution Agreement'
        if request.couch_user:
            published_snapshot.cda.user_id = request.couch_user.get_id
        published_snapshot.cda.user_ip = get_ip(request)

        published_snapshot.published = True
        published_snapshot.save()
        _notification_email_on_publish(domain, published_snapshot, request.couch_user)
    return True


def _notification_email_on_publish(domain, snapshot, published_by):
    params = {"domain": domain, "snapshot": snapshot,
              "published_by": published_by, "url_base": get_site_domain()}
    text_content = render_to_string(
        "domain/email/published_app_notification.txt", params)
    html_content = render_to_string(
        "domain/email/published_app_notification.html", params)
    recipients = settings.EXCHANGE_NOTIFICATION_RECIPIENTS
    subject = "New App on Exchange: %s" % snapshot.title
    try:
        for recipient in recipients:
            send_html_email_async.delay(subject, recipient, html_content,
                                        text_content=text_content,
                                        email_from=settings.DEFAULT_FROM_EMAIL)
    except Exception:
        logging.warning("Can't send notification email, "
                        "but the message was:\n%s" % text_content)


@domain_admin_required
def set_published_snapshot(request, domain, snapshot_name=''):
    domain = request.project
    if request.method == 'POST':
        if snapshot_name != '':
            published_snapshot = Domain.get_by_name(snapshot_name)
            _publish_snapshot(request, domain, published_snapshot=published_snapshot)
        else:
            _publish_snapshot(request, domain)
    return redirect('domain_snapshot_settings', domain.name)


class ExchangeSnapshotsView(BaseAdminProjectSettingsView):
    template_name = 'domain/snapshot_settings.html'
    urlname = 'domain_snapshot_settings'
    page_title = ugettext_lazy("CommCare Exchange")

    @method_decorator(domain_admin_required)
    def dispatch(self, request, *args, **kwargs):
        if is_linked_domain(request.domain):
            raise Http404()
        msg = """
            The CommCare Exchange is being retired in early December 2019.
            If you have questions or concerns, please contact <a href='mailto:{}'>{}</a>.
        """.format(settings.SUPPORT_EMAIL, settings.SUPPORT_EMAIL)
        messages.add_message(self.request, messages.ERROR, msg, extra_tags="html")
        return super(BaseProjectSettingsView, self).dispatch(request, *args, **kwargs)

    @property
    def page_context(self):
        return {
            'project': self.domain_object,
            'snapshots': list(self.domain_object.snapshots()),
            'published_snapshot': self.domain_object.published_snapshot(),
        }
