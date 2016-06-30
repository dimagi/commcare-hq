from django.utils.translation import ugettext as _
from casexml.apps.case.xml import V2
from casexml.apps.phone.restore import RestoreConfig, RestoreParams
from corehq.apps.domain.models import Domain
from dimagi.utils.logging import notify_exception

from corehq.apps.users.models import CommCareUser

from .models import DemoUserRestore


def turn_off_demo_mode(commcare_user):
    """
    Turns demo mode OFF for commcare_user and deletes existing demo restore
    """

    delete_demo_restore_for_user(commcare_user)
    commcare_user.demo_restore_id = None
    commcare_user.is_demo_user = False
    commcare_user.save()


def turn_on_demo_mode(commcare_user, domain):
    """
    Turns demo mode ON for commcare_user, and resets restore to latest
    """
    try:
        # the order of following two is important, because the restore XML will contain
        # <data user_type='demo'> only if commcare_user.is_demo_user is True
        commcare_user.is_demo_user = True
        reset_demo_user_restore(commcare_user, domain)
        return {'errors': []}
    except Exception as e:
        notify_exception(None, message=e.message)
        return {'errors': [
            _("Something went wrong in creating restore for the user. Please try again or report an issue")
        ]}


def reset_demo_user_restore(commcare_user, domain):
    """
    Updates demo restore for the demo commcare_user
    """
    assert commcare_user.domain == domain

    # if there is a restore already, delete it
    delete_demo_restore_for_user(commcare_user)
    # get latest restore
    restore = RestoreConfig(
        project=Domain.get_by_name(domain),
        restore_user=commcare_user.to_ota_restore_user(),
        params=RestoreParams(version=V2),
    ).get_payload().as_file()
    demo_restore = DemoUserRestore.create(commcare_user._id, restore)

    # set reference to new restore
    commcare_user.demo_restore_id = demo_restore.id
    commcare_user.save()


def delete_demo_restore_for_user(commcare_user):
    # Deletes the users' current demo restore object
    # Caller should save the user doc
    old_restore_id = commcare_user.demo_restore_id
    if old_restore_id:
        old_restore = DemoUserRestore.objects.get(id=old_restore_id)
        old_restore.delete()


def demo_user_restore_response(commcare_user):
    assert commcare_user.is_commcare_user()

    restore = DemoUserRestore.objects.get(id=commcare_user.demo_restore_id)
    return restore.get_restore_http_response()


def demo_restore_date_created(commcare_user):
    """
    Returns date of last restore for the demo commcare user
    """
    if commcare_user.is_demo_user:
        restore = DemoUserRestore.objects.get(id=commcare_user.demo_restore_id)
        if restore:
            return restore.timestamp_created


def is_permitted_to_restore(domain, couch_user, as_user, has_data_cleanup_privelege):
    message = None
    if couch_user.is_commcare_user() and domain != couch_user.domain:
        message = u"{} was not in the domain {}".format(couch_user.username, domain)
    elif couch_user.is_web_user() and domain not in couch_user.domains and not couch_user.is_superuser:
        message = u"{} was not in the domain {}".format(couch_user.username, domain)
    elif ((couch_user.is_web_user() and domain in couch_user.domains and as_user is not None) or
            (couch_user.is_superuser and as_user is not None)):
        if not has_data_cleanup_privelege and not couch_user.is_superuser:
            message = u"{} does not have permissions to restore as {}".format(
                couch_user.username,
                as_user,
            )

        try:
            username = as_user.split('@')[0]
            user_domain = as_user.split('@')[1]
        except IndexError:
            message = u"Invalid to restore user {}. Format is <user>@<domain>".format(as_user)

        else:
            if user_domain != domain:
                message = u"{} was not in the domain {}".format(username, domain)
    return message is None, message


def get_restore_user(domain, couch_user, as_user):
    if couch_user.is_commcare_user():
        restore_user = couch_user.to_ota_restore_user()
    elif (couch_user.is_web_user() and as_user is not None):
        username = as_user.split('@')[0]
        domain = as_user.split('@')[1]
        if username != couch_user.raw_username and domain == domain:
            commcare_user = CommCareUser.get_by_username('{}.commcarehq.org'.format(as_user))
            if not commcare_user:
                return None
            restore_user = commcare_user.to_ota_restore_user()
    elif couch_user.is_web_user():
        restore_user = couch_user.to_ota_restore_user(domain)

    return restore_user
