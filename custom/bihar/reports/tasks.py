import os
from celery.task.base import task
from celery.utils.log import get_task_logger
from couchexport.export import export_from_tables
from couchexport.shortcuts import export_response
from django.contrib.sites.models import Site
from django.core.files.temp import NamedTemporaryFile
from django.core.urlresolvers import reverse
from dimagi.utils.django.email import send_HTML_email
from corehq.apps.users.models import WebUser
import uuid
from django.conf import settings
from dimagi.utils.couch.cache.cache_core import get_redis_client

logger = get_task_logger(__name__)
EXPIRE_TIME = 60 * 60 * 24

@task
def bihar_all_rows_task(ReportClass, report_state):
    report = object.__new__(ReportClass)

    # Somehow calling generic _init function or __setstate__ is raising AttributeError
    # on '_update_initial_context' function call...
    try:
        report.__setstate__(report_state)
    except AttributeError:
        pass

    # need to set request
    setattr(report.request, 'REQUEST', {})

    file = report.excel_response
    hash_id = store_excel_in_redis(file)
    user = WebUser.get(report_state["request"]["couch_user"])
    send_email(user.get_email(), report, hash_id)

def send_email(to, report, hash_id):

    link = "http://%s%s" % (Site.objects.get_current().domain,
                               reverse("bihar_export_report", args=[report.domain, str(hash_id)]))

    title = "%s: Requested export excel data" % report.name
    body = "You have requested generating excel export file from '%s' report for selected filters '%s': %s <br><br>" \
           "If download link is not working, please copy and paste following link in your browse: " \
           "<br>" \
           "%s" \
           "<br>" \
           "Please remind that link will be active by 24 hours."\
           % (report.name, report.request.GET, "<a href='%s'>%s</a>" % (link, 'download link'), link)

    send_HTML_email(title, to, body, email_from=settings.DEFAULT_FROM_EMAIL)


def store_excel_in_redis(file):
    hash_id = uuid.uuid4().hex

    tmp = NamedTemporaryFile(delete=False)
    tmp.file.write(file.getvalue())

    r = get_redis_client()
    r.set(hash_id, tmp.name)
    r.expire(hash_id, EXPIRE_TIME)
    remove_temp_file.apply_async(args=[tmp.name], countdown=EXPIRE_TIME)

    return hash_id

@task
def remove_temp_file(temp_file):
    os.unlink(temp_file)