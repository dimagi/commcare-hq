import six
import sys
from collections import defaultdict
from itertools import islice
from logging import Filter
import traceback
from datetime import timedelta, datetime

from pygments import highlight
from pygments.lexers import PythonLexer
from pygments.formatters import HtmlFormatter

from dimagi.utils.django.email import send_HTML_email as _send_HTML_email
from django.core import mail
from django.http import HttpRequest
from django.utils.log import AdminEmailHandler
from django.views.debug import SafeExceptionReporterFilter, get_exception_reporter_filter
from django.template.loader import render_to_string
from corehq.apps.analytics.utils import analytics_enabled_for_email
from corehq.util.view_utils import get_request
from corehq.util.datadog.utils import get_url_group, sanitize_url
from corehq.util.datadog.metrics import ERROR_COUNT
from corehq.util.datadog.const import DATADOG_UNKNOWN


def clean_exception(exception):
    """
    Takes an Exception instance and strips potentially sensitive information
    """
    from django.conf import settings
    if settings.DEBUG:
        return exception

    # couchdbkit doesn't provide a better way for us to catch this exception
    if (
        isinstance(exception, AssertionError) and
        six.text_type(exception).startswith('received an invalid response of type')
    ):
        message = ("It looks like couch returned an invalid response to "
                   "couchdbkit.  This could contain sensitive information, "
                   "so it's being redacted.")
        return exception.__class__(message)

    return exception


def get_sanitized_request_repr(request):
    """
    Sanitizes sensitive data inside request object, if request has been marked sensitive
    via Django decorator, django.views.decorators.debug.sensitive_post_parameters
    """
    if isinstance(request, HttpRequest):
        filter = get_exception_reporter_filter(request)
        return repr(filter.get_post_parameters(request))

    return request


class HqAdminEmailHandler(AdminEmailHandler):
    """
    Custom AdminEmailHandler to include additional details which can be supplied as follows:

    logger.error(message,
        extra={
            'details': {'domain': 'demo', 'user': 'user1'}
        }
    )
    """

    def get_context(self, record):
        from corehq.util.datadog.gauges import datadog_counter
        try:
            request = record.request
        except Exception:
            request = None

        request_repr = get_sanitized_request_repr(request)

        tb_list = []
        code = None
        if record.exc_info:
            etype, _value, tb = record.exc_info
            value = clean_exception(_value)
            tb_list = ['Traceback (most recent call first):\n']
            formatted_exception = traceback.format_exception_only(etype, value)
            tb_list.extend(formatted_exception)
            extracted_tb = list(reversed(traceback.extract_tb(tb)))
            code = self.get_code(extracted_tb)
            tb_list.extend(traceback.format_list(extracted_tb))
            stack_trace = '\n'.join(tb_list)
            subject = '%s: %s' % (record.levelname,
                                  formatted_exception[0].strip() if formatted_exception else record.getMessage())
        else:
            stack_trace = 'No stack trace available'
            subject = '%s: %s' % (
                record.levelname,
                record.getMessage()
            )
        context = defaultdict(lambda: '')
        context.update({
            'subject': self.format_subject(subject),
            'message': record.getMessage(),
            'details': getattr(record, 'details', None),
            'tb_list': tb_list,
            'request_repr': request_repr,
            'stack_trace': stack_trace,
            'code': code,
        })
        if request:
            sanitized_url = sanitize_url(request.build_absolute_uri())
            datadog_counter(ERROR_COUNT, tags=[
                'url:{}'.format(sanitized_url),
                'group:{}'.format(get_url_group(sanitized_url)),
                'domain:{}'.format(getattr(request, 'domain', DATADOG_UNKNOWN)),
            ])

            context.update({
                'get': list(request.GET.items()),
                'post': SafeExceptionReporterFilter().get_post_parameters(request),
                'method': request.method,
                'username': request.user.username if getattr(request, 'user', None) else "",
                'url': request.build_absolute_uri(),
            })
        return context

    def emit(self, record):
        context = self.get_context(record)

        message = "\n\n".join([_f for _f in [
            context['message'],
            self.format_details(context['details']),
            context['stack_trace'],
            context['request_repr'],
        ] if _f])
        html_message = render_to_string('hqadmin/email/error_email.html', context)
        mail.mail_admins(self._clean_subject(context['subject']), message, fail_silently=True,
                         html_message=html_message)

    def format_details(self, details):
        if details:
            formatted = '\n'.join('{item[0]}: {item[1]}'.format(item=item) for item in details.items())
            return 'Details:\n{}'.format(formatted)

    @staticmethod
    def get_code(extracted_tb):
        try:
            trace = next((trace for trace in extracted_tb if 'site-packages' not in trace[0]), None)
            if not trace:
                return None

            filename = trace[0]
            lineno = trace[1]
            offset = 10
            with open(filename, encoding='utf-8') as f:
                code_context = list(islice(f, lineno - offset, lineno + offset))

            return highlight(''.join(code_context),
                PythonLexer(),
                HtmlFormatter(
                    noclasses=True,
                    linenos='table',
                    hl_lines=[offset, offset],
                    linenostart=(lineno - offset + 1),
                )
            )
        except Exception as e:
            return "Unable to extract code. {}".format(e)

    @classmethod
    def _clean_subject(cls, subject):
        # Django raises BadHeaderError if subject contains following bad_strings
        # to guard against Header Inejction.
        # see https://docs.djangoproject.com/en/1.8/topics/email/#preventing-header-injection
        # bad-strings list from http://nyphp.org/phundamentals/8_Preventing-Email-Header-Injection
        bad_strings = ["\r", "\n", "%0a", "%0d", "Content-Type:", "bcc:", "to:", "cc:"]
        replacement = "-"
        for i in bad_strings:
            subject = subject.replace(i, replacement)
        return subject


class NotifyExceptionEmailer(HqAdminEmailHandler):

    def get_context(self, record):
        context = super(NotifyExceptionEmailer, self).get_context(record)
        context['subject'] = record.getMessage()
        return context


class HQRequestFilter(Filter):
    """
    Filter that adds custom context to log records for HQ domain, username, and path.

    This lets you add custom log formatters to include this information. For example,
    the following format:

    [%(username)s:%(domain)s] %(hq_url)s %(message)s

    Will log:

    [user@example.com:my-domain] /a/my-domain/apps/ [original message]
    """

    def filter(self, record):
        request = get_request()
        if request is not None:
            record.domain = getattr(request, 'domain', '')
            record.username = request.couch_user.username if getattr(request, 'couch_user', None) else ''
            record.hq_url = request.path
        else:
            record.domain = record.username = record.hq_url = None
        return True


class SlowRequestFilter(Filter):
    """
    Filter that can be used to log a slow request or action.
    Expects that LogRecords passed in will have a .duration property that is a timedelta.
    Intended to be used primarily with the couchdbkit request_logger
    """

    def __init__(self, name='', duration=5):
        self.duration_cutoff = timedelta(seconds=duration)
        super(SlowRequestFilter, self).__init__(name)

    def filter(self, record):
        try:
            return record.duration > self.duration_cutoff
        except (TypeError, AttributeError):
            return False


class SuppressStaticLogs(Filter):
    def filter(self, record):
        try:
            request, status_code, _ = record.args
            return '/static/' not in request or int(status_code) != 200
        except ValueError:
            return True


def display_seconds(seconds):
    return str(timedelta(seconds=int(round(seconds))))


def with_progress_bar(iterable, length=None, prefix='Processing', oneline=True,
                      stream=sys.stdout, step=None):
    """Turns 'iterable' into a generator which prints a progress bar.

    :param oneline: Set to False to print each update on a new line.
        Useful if there will be other things printing to the terminal.
        Set to "concise" to use exactly one line for all output.
    """
    if length is None:
        if hasattr(iterable, "__len__"):
            length = len(iterable)
        else:
            raise AttributeError(
                "'{}' object has no len(), you must pass in the 'length' parameter"
                .format(type(iterable))
            )

    granularity = min(50, length or 50)
    start = datetime.now()

    def draw(position, done=False):
        percent = float(position) / length if length > 0 else 1
        dots = int(round(min(percent, 1) * granularity))
        spaces = granularity - dots
        elapsed = (datetime.now() - start).total_seconds()
        remaining = (display_seconds((elapsed / percent) * (1 - percent))
                     if position > 0 else "-:--:--")

        print(prefix, end=' ', file=stream)
        print("[{}{}]".format("." * dots, " " * spaces), end=' ', file=stream)
        print("{}/{}".format(position, length), end=' ', file=stream)
        print("{:.0%}".format(percent), end=' ', file=stream)
        if position >= length or done:
            print("{} elapsed".format(datetime.now() - start), end='', file=stream)
        else:
            print("{} remaining".format(remaining), end='', file=stream)
        print(("\r" if oneline and not done else "\n"), end='', file=stream)
        stream.flush()

    if oneline != "concise":
        print("Started at {:%Y-%m-%d %H:%M:%S}".format(start), file=stream)
    if step is None:
        step = length // granularity
    i = -1
    try:
        for i, x in enumerate(iterable):
            yield x
            if i % step == 0:
                draw(i)
    finally:
        draw(i + 1, done=True)
    if oneline != "concise":
        end = datetime.now()
        print("Finished at {:%Y-%m-%d %H:%M:%S}".format(end), file=stream)
        print("Elapsed time: {}".format(display_seconds((end - start).total_seconds())), file=stream)


def get_traceback_string():
    if six.PY3:
        from io import StringIO
        f = StringIO()
    else:
        from cStringIO import StringIO
        f = StringIO()
    traceback.print_exc(file=f)
    return f.getvalue()


def send_HTML_email(subject, recipient, html_content, *args, **kwargs):
    return _send_HTML_email(subject, recipient, html_content, *args, **kwargs)
