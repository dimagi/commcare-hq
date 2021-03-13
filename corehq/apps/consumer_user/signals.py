from corehq.form_processor.models import CommCareCaseSQL
from corehq.form_processor.signals import sql_case_post_save

from .const import CONSUMER_INVITATION_CASE_TYPE
from .tasks import create_new_invitation


def send_email_case_changed_receiver(sender, case, **kwargs):
    if case.type != CONSUMER_INVITATION_CASE_TYPE:
        return
    create_new_invitation.delay(case)


def connect_signals():
    sql_case_post_save.connect(
        send_email_case_changed_receiver,
        CommCareCaseSQL,
        dispatch_uid='send_email_case_changed_receiver'
    )
