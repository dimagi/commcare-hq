import os

from django.conf import settings
from django.core.management import call_command
from django.urls import reverse
from django.utils.translation import ugettext_lazy as _

from celery.task import task

from couchexport.models import Format
from dimagi.utils import web
from soil.util import expose_blob_download

from corehq.apps.hqwebapp.tasks import send_html_email_async
from corehq.util.files import safe_filename_header


@task(queue='icds_dashboard_reports_queue')
def run_data_pull(data_pull_slug, month, location_id=None, email=None):
    subject = _('Custom ICDS Data Pull')
    try:
        filename = call_command("run_custom_data_pull", data_pull_slug, "icds-ucr-citus", month=month,
                                location_id=location_id, skip_confirmation=True)
    except Exception as e:
        if email:
            message = _("""
                            Hi,
                            Could not generate the requested data pull.
                            The error has been notified. Please report as an issue for quicker followup
                        """)
            send_html_email_async.delay(subject, [email], message,
                                        email_from=settings.DEFAULT_FROM_EMAIL)
        raise e
    else:
        if email and filename:
            exposed_download = expose_blob_download(
                filename, expiry=24 * 60 * 60,
                mimetype=Format.from_format(Format.ZIP).mimetype,
                content_disposition=safe_filename_header(filename))
            os.remove(filename)
            path = reverse('retrieve_download', kwargs={'download_id': exposed_download.download_id})
            link = f"{web.get_url_base()}{path}?get_file"
            message = _("""
            Hi,
            Please download the data from {link}.
            The data is available only for 24 hours.
            """).format(link=link)
            send_html_email_async.delay(subject, [email], message,
                                        email_from=settings.DEFAULT_FROM_EMAIL)
