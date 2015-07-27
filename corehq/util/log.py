from collections import defaultdict
import traceback
from celery.utils.mail import ErrorMail
from django.core import mail
from django.utils.log import AdminEmailHandler
from django.views.debug import get_exception_reporter_filter
from django.template.loader import render_to_string


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

    def emit(self, record):
        # avoid circular dependency
        from django.conf import settings

        request = None
        try:
            request = record.request
            filter = get_exception_reporter_filter(request)
            request_repr = filter.get_request_repr(request)
        except Exception:
            request_repr = "Request repr() unavailable."

        tb_list = []
        if record.exc_info:
            exc_info = record.exc_info
            etype, _value, tb = exc_info
            value = clean_exception(_value)
            tb_list = ['Traceback (most recent call first):\n']
            formatted_exception = traceback.format_exception_only(etype, value)
            tb_list.extend(formatted_exception)
            tb_list.extend(traceback.format_list(reversed(traceback.extract_tb(tb))))
            stack_trace = '\n'.join(tb_list)
            subject = '%s: %s' % (record.levelname,
                                  formatted_exception[0].strip() if formatted_exception else record.getMessage())
        else:
            stack_trace = 'No stack trace available'
            subject = '%s: %s' % (
                record.levelname,
                record.getMessage()
            )

        subject = self.format_subject(subject)

        message = "%s\n\n%s" % (stack_trace, request_repr)
        details = getattr(record, 'details', None)
        if details:
            message = "%s\n\n%s" % (self.format_details(details), message)

        context = defaultdict(lambda: '')
        context.update({
            'details': details,
            'tb_list': tb_list,
            'request_repr': request_repr
        })
        if request:
            context.update({
                'get': request.GET,
                'post': request.POST,
                'method': request.method,
                'url': request.build_absolute_uri(),
            })
        html_message = render_to_string('hqadmin/email/error_email.html', context)
        mail.mail_admins(subject, message, fail_silently=True, html_message=html_message)

    def format_details(self, details):
        if details:
            formatted = '\n'.join('{item[0]}: {item[1]}'.format(item=item) for item in details.items())
            return 'Details:\n{}'.format(formatted)


class SensitiveErrorMail(ErrorMail):
    """
    Extends Celery's ErrorMail class to prevents task args and kwargs from being printed in error emails.
    """
    replacement = '(excluded due to sensitive nature)'

    def format_body(self, context):
        context['args'] = self.replacement
        context['kwargs'] = self.replacement
        return self.body.strip() % context
