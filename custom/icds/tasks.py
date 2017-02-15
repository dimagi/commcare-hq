from celery.task import task
from corehq.apps.reminders.tasks import CELERY_REMINDERS_QUEUE
from corehq.apps.reminders.util import get_one_way_number_for_recipient
from corehq.apps.sms.api import send_sms
from corehq.apps.users.models import CommCareUser


@task(queue=CELERY_REMINDERS_QUEUE, ignore_result=True)
def run_indicator(domain, user_id, indicator_class):
    """
    Runs the given indicator for the given user and sends the SMS if needed.

    :param domain: The domain the indicator is being run for
    :param user_id: The id of either an AWW or LS CommCareUser
    :param indicator_class: a subclass of AWWIndicator or LSIndicator
    """
    user = CommCareUser.get_by_user_id(user_id, domain=domain)
    indicator = indicator_class(domain, user)
    messages = indicator.get_messages(language_code=usercase.get_language_code())

    if not isinstance(messages, list):
        raise ValueError("Expected a list of messages")

    if messages:
        # The user's phone number and preferred language is stored on the usercase
        usercase = user.get_usercase()

        phone_number = get_one_way_number_for_recipient(usercase)
        if not phone_number:
            return

        for message in messages:
            send_sms(domain, usercase, phone_number, message)
