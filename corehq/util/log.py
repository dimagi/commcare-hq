from collections import defaultdict
from itertools import islice
from logging import Filter
import traceback
from datetime import timedelta

from pygments import highlight
from pygments.lexers import PythonLexer
from pygments.formatters import HtmlFormatter

from celery.utils.mail import ErrorMail
from django.core import mail
from django.utils.log import AdminEmailHandler
from django.views.debug import SafeExceptionReporterFilter, get_exception_reporter_filter
from django.template.loader import render_to_string
from corehq.util.view_utils import get_request


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
        exception.message.startswith('received an invalid response of type')
    ):
        message = ("It looks like couch returned an invalid response to "
                   "couchdbkit.  This could contain sensitive information, "
                   "so it's being redacted.")
        return exception.__class__(message)

    return exception


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
        request = None
        try:
            request = record.request
            filter = get_exception_reporter_filter(request)
            request_repr = filter.get_request_repr(request)
        except Exception:
            request_repr = "Request repr() unavailable."

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
            context.update({
                'get': request.GET,
                'post': SafeExceptionReporterFilter().get_post_parameters(request),
                'method': request.method,
                'url': request.build_absolute_uri(),
            })
        return context

    def emit(self, record):
        context = self.get_context(record)

        message = "\n\n".join(filter(None, [
            context['message'],
            self.format_details(context['details']),
            context['stack_trace'],
            context['request_repr'],
        ]))
        html_message = render_to_string('hqadmin/email/error_email.html', context)
        mail.mail_admins(self._clean_subject(context['subject']), message, fail_silently=True,
                         html_message=html_message)

    def format_details(self, details):
        if details:
            formatted = '\n'.join('{item[0]}: {item[1]}'.format(item=item) for item in details.items())
            return 'Details:\n{}'.format(formatted)

    def get_code(self, extracted_tb):
        trace = next((trace for trace in extracted_tb if 'site-packages' not in trace[0]), None)
        if not trace:
            return None

        filename = trace[0]
        lineno = trace[1]
        offset = 10
        with open(filename) as f:
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


class SensitiveErrorMail(ErrorMail):
    """
    Extends Celery's ErrorMail class to prevents task args and kwargs from being printed in error emails.
    """
    replacement = '(excluded due to sensitive nature)'

    def format_body(self, context):
        context['args'] = self.replacement
        context['kwargs'] = self.replacement
        return self.body.strip() % context


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
