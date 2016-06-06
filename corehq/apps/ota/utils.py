from django.utils.translation import ugettext as _
from casexml.apps.case.xml import V2
from casexml.apps.phone.restore import RestoreConfig, RestoreParams
from corehq.apps.domain.models import Domain
from dimagi.utils.logging import notify_exception

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
