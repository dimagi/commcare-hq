
from casexml.apps.phone.restore import RestoreConfig
from corehq.apps.domain.models import Domain

from .models import DemoUserRestore


def turn_off_demo_mode(commcare_user):
    """
    Turns demo mode OFF for commcare_user and deletes existing demo restore
    """
    commcare_user.is_demo_user = False

    # delete old restore
    old_restore_id = commcare_user.demo_restore_id
    if old_restore_id:
        old_restore = DemoUserRestore.objects.get(id=old_restore_id)
        old_restore.delete()

    commcare_user.demo_restore_id = None


def turn_on_demo_mode(commcare_user, domain):
    """
    Turns demo mode ON for commcare_user, and resets restore to latest
    """
    # ToDo This should be in a task
    commcare_user.is_demo_user = True
    commcare_user.reset_demo_user_restore


def reset_demo_user_restore(commcare_user, domain):
    """
    Updates demo restore for the demo commcare_user
    """
    assert commcare_user.domain == domain
    assert commcare_user.is_demo_user

    # get latest restore
    restore = RestoreConfig(
        project=Domain.get_by_name(domain),
        user=commcare_user.to_case_xml_user()
    ).get_payload().as_file()
    demo_restore = DemoUserRestore.create(commcare_user._id, restore)

    # set reference to new restore
    commcare_user.demo_restore_id = demo_restore.id
