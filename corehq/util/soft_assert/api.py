from django.core.mail import mail_admins, send_mail
from django.core.cache import cache
from corehq.util.soft_assert.core import SoftAssert
import settings


def _number_is_power_of_two(x):
    # it turns out that x & (x - 1) == 0 if and only if x is a power of two
    # http://stackoverflow.com/a/600306/240553
    return x > 0 and (x & (x - 1) == 0)


def _django_caching_counter(key):
    cache_key = 'django-soft-assert.{}'.format(key)
    try:
        return cache.incr(cache_key)
    except ValueError:
        cache.set(cache_key, 1)
        return 1


def _send_message(info, backend):
    backend(
        subject='Soft Assert: [{}] {}'.format(info.key[:8], info.msg),
        message=('Message: {info.msg}\n'
                 'Traceback:\n{info.traceback}\n'
                 'Occurrences to date: {info.count}\n').format(info=info)
    )


def soft_assert(to, notify_admins=False,
                fail_if_debug=False, exponential_backoff=True, skip_frames=0):
    """
    send an email with stack trace if assertion is not True

    Parameters:
    - to: List of email addresses that should receive the email
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

    def send_to_recipients(subject, message):
        send_mail(
            # this prefix is automatically added in mail_admins
            # but not send mail
            subject=settings.EMAIL_SUBJECT_PREFIX + subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=to,
        )

    if to and notify_admins:
        def send(info):
            _send_message(info, backend=mail_admins)
            _send_message(info, backend=send_to_recipients)
    elif to:
        def send(info):
            _send_message(info, backend=send_to_recipients)
    elif notify_admins:
        def send(info):
            _send_message(info, backend=mail_admins)
    else:
        raise ValueError('You must call soft assert with either a '
                         'list of recipients or notify_admins=True')

    if fail_if_debug:
        debug = settings.DEBUG
    else:
        debug = False

    if exponential_backoff:
        should_send = _number_is_power_of_two
    else:
        should_send = lambda count: True

    return SoftAssert(
        debug=debug,
        send=send,
        incrementing_counter=_django_caching_counter,
        should_send=should_send,
        skip_frames=skip_frames,
    )
