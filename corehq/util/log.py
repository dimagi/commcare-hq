import sys
from logging import Filter
import traceback
from datetime import timedelta, datetime

from celery._state import get_current_task

from dimagi.utils.django.email import send_HTML_email as _send_HTML_email
from django.http import HttpRequest
from django.views.debug import get_exception_reporter_filter
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
        str(exception).startswith('received an invalid response of type')
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
            record.domain = record.username = record.hq_url = '-'
        return True


class CeleryTaskFilter(Filter):
    """
    Filter that adds custom context to log records for celery task ID and name.

    This lets you add custom log formatters to include this information.
    """
    def filter(self, record):
        task = get_current_task()
        if task and task.request:
            record.task_id = task.request.id
            record.task_name = task.name
        else:
            record.task_id = record.task_name = '-'
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
                      stream=None, offset=0, step=None):
    """Turns 'iterable' into a generator which prints a progress bar.

    :param oneline: Set to False to print each update on a new line.
        Useful if there will be other things printing to the terminal.
        Set to "concise" to use exactly one line for all output.
    :param offset: Number of items already/previously iterated.
    :param step: deprecated, not used
    """
    if stream is None:
        stream = sys.stdout
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

    info_prefix = '' if oneline else f'{prefix} '

    def draw(position, done=False):
        overall_position = offset + position
        overall_percent = overall_position / length if length > 0 else 1
        dots = int(round(min(overall_percent, 1) * granularity))
        spaces = granularity - dots
        elapsed = (datetime.now() - start).total_seconds()
        percent = position / (length - offset) if length - offset > 0 else 1
        remaining = (display_seconds((elapsed / percent) * (1 - percent))
                     if position > 0 else "-:--:--")

        print(prefix, end=' ', file=stream)
        print("[{}{}]".format("." * dots, " " * spaces), end=' ', file=stream)
        print("{}/{}".format(overall_position, length), end=' ', file=stream)
        print("{:.0%}".format(overall_percent), end=' ', file=stream)
        if overall_position >= length or done:
            print("{} elapsed".format(datetime.now() - start), end='', file=stream)
        else:
            print("{} remaining".format(remaining), end='', file=stream)
        print(("\r" if oneline and not done else "\n"), end='', file=stream)
        stream.flush()

    if oneline != "concise":
        print("{}Started at {:%Y-%m-%d %H:%M:%S}".format(info_prefix, start), file=stream)
    should_update = step_calculator(length, granularity)
    i = 0
    try:
        draw(i)
        for i, x in enumerate(iterable, start=1):
            yield x
            if should_update(i):
                draw(i)
    finally:
        draw(i, done=True)
    if oneline != "concise":
        end = datetime.now()
        print("{}Finished at {:%Y-%m-%d %H:%M:%S}".format(info_prefix, end), file=stream)
        print("{}Elapsed time: {}".format(info_prefix, display_seconds((end - start).total_seconds())), file=stream)


def step_calculator(length, granularity):
    """Make a function that caculates when to post progress updates

    Approximates two updates per output granularity (dot) with update
    interval bounded at 0.1s <= t <= 5m. This assumes a uniform
    iteration rate.
    """
    def should_update(i):
        assert i, "divide by zero protection"
        nonlocal next_update, max_wait
        now = datetime.now()
        if now > next_update:
            rate = i / (now - start).total_seconds()  # iterations / second
            secs = min(max(twice_per_dot / rate, 0.1), max_wait)  # seconds / dot / 2
            next_update = now + timedelta(seconds=secs)
            if secs == max_wait < 300:
                max_wait = min(max_wait * 2, 300)
            return True
        return False
    # start with short delay to compensate for excessive initial estimates
    max_wait = 10
    twice_per_dot = max(length / granularity, 1) / 2  # iterations / dot / 2
    start = next_update = datetime.now()
    return should_update


def get_traceback_string():
    from io import StringIO
    f = StringIO()
    traceback.print_exc(file=f)
    return f.getvalue()


def send_HTML_email(subject, recipient, html_content, *args, **kwargs):
    return _send_HTML_email(subject, recipient, html_content, *args, **kwargs)
