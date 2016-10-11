import json
import datetime
from django.utils.translation import ugettext as _
from ws4redis.publisher import RedisPublisher
from ws4redis.redis_store import RedisMessage
from dimagi.utils.parsing import json_format_datetime


def notify_form_opened(domain, couch_user, app_id, unique_form_id):
    message = _('This form has been opened for editing by {}.').format(couch_user.username)
    notify_event(domain, couch_user, app_id, unique_form_id, message)


def notify_form_changed(domain, couch_user, app_id, unique_form_id):
    message = _(
        'This form has been updated by {}. Reload the page to see the latest changes.'
    ).format(couch_user.username)
    notify_event(domain, couch_user, app_id, unique_form_id, message)


def notify_event(domain, couch_user, app_id, unique_form_id, message):
    message = '{} (<a href="https://confluence.dimagi.com/display/ccinternal/App+Builder+Notifications">what is this?</a>)'.format(message)
    message_obj = RedisMessage(json.dumps({
        'domain': domain,
        'user_id': couch_user._id,
        'username': couch_user.username,
        'text': message,
        'timestamp': json_format_datetime(datetime.datetime.utcnow()),
    }))
    RedisPublisher(
        facility=get_facility_for_form(domain, app_id, unique_form_id), broadcast=True
    ).publish_message(message_obj)


def get_facility_for_form(domain, app_id, unique_form_id):
    """
    Gets the websocket facility (topic) for a particular form.
    """
    return '{}:{}:{}'.format(domain, app_id, unique_form_id)
