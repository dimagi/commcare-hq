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

    # delete old restore
    old_restore_id = commcare_user.demo_restore_id
    if old_restore_id:
        old_restore = DemoUserRestore.objects.get(uuid=old_restore_id)
        old_restore.delete()

    commcare_user.demo_restore_id = None
    commcare_user.is_demo_user = False
    commcare_user.save()


def turn_on_demo_mode(commcare_user, domain):
    """
    Turns demo mode ON for commcare_user, and resets restore to latest
    """
    try:
        # the order of following two is important, because the restore XML should contain...
        # user_type='demo' in user_data element
        commcare_user.is_demo_user = True
        reset_demo_user_restore(commcare_user, domain)
    except Exception as e:
        notify_exception(None, message=e.message)
        return {'errors': [
            _("Something went wrong in creating restore for the user. Please try again or report an issue")
        ]}
    else:
        commcare_user.save()
        return {'errors': []}


def reset_demo_user_restore(commcare_user, domain):
    """
    Updates demo restore for the demo commcare_user
    """
    assert commcare_user.domain == domain

    # get latest restore
    restore = RestoreConfig(
        project=Domain.get_by_name(domain),
        user=commcare_user.to_casexml_user(),
        params=RestoreParams(version=V2),
    ).get_payload().as_string()
    demo_restore = DemoUserRestore.create(commcare_user._id, restore)

    # set reference to new restore
    commcare_user.demo_restore_id = str(demo_restore.uuid)


def demo_user_restore_response(commcare_user):
    # Todo handle case where user is in demo-mode, but demo restore is not set due to task fail
    assert commcare_user.is_commcare_user()
    assert bool(commcare_user.demo_restore_id)

    restore = DemoUserRestore.objects.get(uuid=commcare_user.demo_restore_id)
    return restore.get_restore_http_response()
