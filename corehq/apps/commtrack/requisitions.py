'''
Created on Feb 28, 2013

@author: czue
'''
from corehq.apps.commtrack.const import RequisitionActions, UserRequisitionRoles
import uuid
from corehq.apps.users.cases import get_owning_users, get_owner_id
from django.utils.translation import ugettext as _


def create_requisition(user_id, product_stock_case, transaction):
    raise NotImplementedError("this doesn't work anymore and should be removed. "
                              "requisitions are no longer product-specific.")


def should_notify_user(user, next_action_type):
    return user.user_data.get(UserRequisitionRoles.get_user_role(next_action_type), False)

def get_notification_recipients(next_action, requisition):
    # given a status and list of requisitions, get the exhaustive list of
    # people to notify about the requisition entering that status.
    users = get_owning_users(get_owner_id(requisition))
    if len(users) == 1:
        return users
    return [u for u in users if should_notify_user(u, next_action.action_type)]

def get_notification_message(next_action, requisitions):
    templates = {
        RequisitionActions.APPROVAL: _('{name} has requested the following supplies: {summary}. please respond "{keyword} {loc}" to approve.'),
        RequisitionActions.PACK: _('{name} should be supplied with the following supplies: {summary}. please respond "{keyword} {loc}" to confirm the order.'),
        RequisitionActions.RECEIPTS: _('your order of {summary} is ready to be picked up. please respond with a "{keyword}" message to report receipts.'),
    }

    # NOTE: it'd be weird if this was None but for now we won't fail hard
    guessed_location = requisitions[0].get_location()
    summary = ', '.join(r.sms_format() for r in requisitions)
    return templates[next_action.action_type].format(
        name=requisitions[0].get_requester().full_name,
        summary=summary,
        loc=guessed_location.site_code if guessed_location else "<loc code>",
        keyword=next_action.keyword,
    )
