from django.dispatch import receiver

from corehq.util.metrics import create_metrics_event
from corehq.util.signals import post_command


@receiver(post_command)
def record_command_event(sender, args, kwargs, outcome, **extra):
    if isinstance(outcome, BaseException):
        outcome = f'{outcome.__class__}: {outcome}'
    text = f'args: {args}\noptions: {kwargs}\noutcome: {outcome}'
    event = '{}'.format(sender.__name__)
    create_metrics_event(
        event, text, aggregation_key=sender.__name__
    )
