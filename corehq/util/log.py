import traceback
from celery.utils.mail import ErrorMail
from django.core import mail
from django.utils.log import AdminEmailHandler
from django.views.debug import get_exception_reporter_filter
from django.template.loader import render_to_string


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

        try:
            request = record.request
            subject = '%s (%s IP): %s' % (
                record.levelname,
                (request.META.get('REMOTE_ADDR') in settings.INTERNAL_IPS
                 and 'internal' or 'EXTERNAL'),
                record.getMessage()
            )
            filter = get_exception_reporter_filter(request)
            request_repr = filter.get_request_repr(request)
        except Exception:
            subject = '%s: %s' % (
                record.levelname,
                record.getMessage()
            )
            request = None
            request_repr = "Request repr() unavailable."
        subject = self.format_subject(subject)

        tb_list = None
        if record.exc_info:
            exc_info = record.exc_info
            etype, value, tb = exc_info
            tb_list = ['Traceback (most recent call first):\n']
            tb_list.extend(traceback.format_exception_only(etype, value))
            tb_list.extend(traceback.format_list(reversed(traceback.extract_tb(tb))))
            stack_trace = '\n'.join(tb_list)
        else:
            exc_info = (None, record.getMessage(), None)
            stack_trace = 'No stack trace available'

        message = "%s\n\n%s" % (stack_trace, request_repr)
        details = getattr(record, 'details', None)
        if details:
            message = "%s\n\n%s" % (self.format_details(details), message)

        context = {
            'details': details,
            'tb_list': tb_list,
            'get': request.GET,
            'post': request.POST,
            'request_repr': request_repr
        }
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
