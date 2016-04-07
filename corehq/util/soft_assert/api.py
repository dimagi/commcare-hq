from django.conf import settings

from corehq.apps.hqwebapp.tasks import send_mail_async, mail_admins_async
from corehq.util.log import get_sanitized_request_repr
from corehq.util.global_request import get_request
from corehq.util.soft_assert.core import SoftAssert


def _send_message(info, backend):
    request = get_request()
    request_repr = get_sanitized_request_repr(request)

    backend(
        subject='Soft Assert: [{}] {}'.format(info.key[:8], info.msg),
        message=('Message: {info.msg}\n'
                 'Value: {info.obj!r}\n'
                 'Traceback:\n{info.traceback}\n'
                 'Request:\n{request}\n'
                 'Occurrences to date: {info.count}\n').format(
                info=info, request=request_repr)
    )


def soft_assert(to=None, notify_admins=False,
                fail_if_debug=False, exponential_backoff=True, skip_frames=0,
                send_to_ops=True,):
    """
    send an email with stack trace if assertion is not True

    Parameters:
    - to: Email address or list of email addresses that should receive the email
    - notify_admins: Send to all admins (using mail_admins) as well
    - fail_if_debug: if True, will fail hard (like a normal assert)
      if called in a developer environment (settings.DEBUG = True).
      If False, behavior will not depend on DEBUG setting.
    - exponential_backoff: if True, will only email every time an assert has
      failed 2**n times (1, 2, 4, 8, 16 times, etc.). If False, it will email
      every time.
    - skip_frames: number of frames of the traceback (from the bottom)
      to ignore. Useful if you're calling this from within a helper function.
      In that case if you want the call _to_ the helper function to be the
      last frame in the stack trace, then pass in skip_frames=1.
      This affects both the traceback in the email as the "key" by which
      errors are grouped.

    For the purposes of grouping errors into email threads,
    counting occurrences (sent in the email), and implementing exponential
    backoff, errors are always grouped by a key that varies on the
    last two frames (that aren't skipped by skip_frames) of the stack.

    Returns assertion. This makes it easy to do something like the following:

        if not soft_assert(to=['me@mycompany.com']).call(
                isinstance(n, float), 'myfunction should be passed a float'):
            n = float(n)

    etc.

    """

    if isinstance(to, basestring):
        to = [to]

    if to is not None and send_to_ops and settings.SOFT_ASSERT_EMAIL:
        to = to + [settings.SOFT_ASSERT_EMAIL]

    def send_to_recipients(subject, message):
        send_mail_async.delay(
            # this prefix is automatically added in mail_admins
            # but not send mail
            subject=settings.EMAIL_SUBJECT_PREFIX + subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=to,
        )

    def send_to_admins(subject, message):
        mail_admins_async.delay(
            subject=subject,
            message=message,
        )

    if to and notify_admins:
        def send(info):
            if not settings.DEBUG:
                _send_message(info, backend=send_to_admins)
            _send_message(info, backend=send_to_recipients)
    elif to:
        def send(info):
            _send_message(info, backend=send_to_recipients)
    elif notify_admins:
        def send(info):
            if not settings.DEBUG:
                _send_message(info, backend=send_to_admins)
    else:
        raise ValueError('You must call soft assert with either a '
                         'list of recipients or notify_admins=True')

    if fail_if_debug:
        debug = settings.DEBUG
    else:
        debug = False

    return SoftAssert(
        debug=debug,
        send=send,
        use_exponential_backoff=exponential_backoff,
        skip_frames=skip_frames,
    )
