from corehq.apps.commtrack.const import RequisitionActions
from corehq.apps.users.cases import get_owning_users, get_owner_id
from custom.requisitions.const import UserRequisitionRoles


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
    # NOTE: it'd be weird if this was None but for now we won't fail hard
    guessed_location = requisitions[0].get_location()
    summary = ', '.join(r.sms_format() for r in requisitions)
    requester = requisitions[0].get_requester()
    return notification_template(next_action.action).format(
        name=requester.full_name if requester else "Unknown",
        summary=summary,
        loc=guessed_location.site_code if guessed_location else "<loc code>",
        keyword=next_action.keyword,
    )


def notification_template(action):
    # this had to be a method to do translations
    from django.utils.translation import ugettext as _
    return {
        RequisitionActions.APPROVAL: _('{name} has requested the following supplies: {summary}. please respond "{keyword} {loc}" to approve.'),
        RequisitionActions.FULFILL: _('{name} should be supplied with the following supplies: {summary}. please respond "{keyword} {loc}" to confirm the order.'),
        RequisitionActions.RECEIPTS: _('your order of {summary} is ready to be picked up. please respond with a "{keyword}" message to report receipts.'),
    }[action]
