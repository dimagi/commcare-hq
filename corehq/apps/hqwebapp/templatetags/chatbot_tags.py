from django import template

from corehq.apps.hqwebapp.chat_access import chatbot_enabled_for_request
from corehq.apps.hqwebapp.chat_quota import get_chatbot_message_quota

register = template.Library()


@register.filter
def has_chatbot_allowance(couch_user):
    return bool(couch_user and get_chatbot_message_quota(couch_user) != 0)


register.filter('chatbot_enabled', chatbot_enabled_for_request)
