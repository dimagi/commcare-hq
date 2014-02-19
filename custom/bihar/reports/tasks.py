from celery.task.base import task
from StringIO import StringIO
from celery.utils.log import get_task_logger
from couchexport.export import export_from_tables
from couchexport.shortcuts import export_response
from django.contrib.sites.models import Site
from django.core.urlresolvers import reverse, get_script_prefix
from django.http.request import HttpRequest
import redis
from dimagi.utils.django.email import send_HTML_email
from corehq.apps.users.models import CouchUser, CommCareUser, WebUser
import uuid
from django.conf import settings
from custom.bihar.utils import get_redis_client

logger = get_task_logger(__name__)
EXPIRE_TIME = 60 * 60 * 24

@task
def bihar_all_rows_task(ReportClass, report_state):

    report = get_report(ReportClass)
    set_report_state(report, report_state)
    file = get_excel_file(report)
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

    r = get_redis_client()
    r.set(hash_id, file.getvalue())
    r.expire(hash_id, EXPIRE_TIME)

    return hash_id

def get_excel_file(mch):

    """
    Exports the report as excel.

    When rendering a complex cell, it will assign a value in the following order:
    1. cell['raw']
    2. cell['sort_key']
    3. str(cell)
    """
    try:
        import xlwt
    except ImportError:
        raise Exception("It doesn't look like this machine is configured for "
                        "excel export. To export to excel you have to run the "
                        "command:  easy_install xlutils")
    headers = mch.headers
    formatted_rows = mch.get_all_rows

    def _unformat_row(row):
        def _unformat_val(val):
            if isinstance(val, dict):
                return val.get('raw', val.get('sort_key', val))
            return val

        return [_unformat_val(val) for val in row]

    table = headers.as_table
    rows = [_unformat_row(row) for row in formatted_rows]
    table.extend(rows)
    if mch.total_row:
        table.append(_unformat_row(mch.total_row))
    if mch.statistics_rows:
        table.extend([_unformat_row(row) for row in mch.statistics_rows])

    file = StringIO()
    export_from_tables([[mch.export_sheet_name, table]], file, mch.export_format)

    return file


def get_report(ReportClass):
    """
    Utility method to run a report for an arbitrary month without a request
    """
    class Report(ReportClass):
        report_class = ReportClass

        def __init__(self, *args, **kwargs):
            None
    return Report()


def set_report_state(report, state):
        """
            For unpickling a pickled report.
        """
        logging = get_task_logger(__name__) # logging lis likely to happen within celery.
        report.domain = state.get('domain')
        report.context = state.get('context', {})

        class FakeHttpRequest(object):
            GET = {}
            META = {}
            couch_user = None
            datespan = None

        request_data = state.get('request')
        request = FakeHttpRequest()
        request.GET = request_data.get('GET', {})
        request.META = request_data.get('META', {})
        request.datespan = request_data.get('datespan')

        try:
            couch_user = CouchUser.get(request_data.get('couch_user'))
            request.couch_user = couch_user
        except Exception as e:
            logging.error("Could not unpickle couch_user from request for report %s. Error: %s" %
                            (report.name, e))
        report.request = request
        report._caching = True
        report.request_params = state.get('request_params')

        report._pagination = FakeHttpRequest()
        report._pagination.start = 1
        report._pagination.count = 10