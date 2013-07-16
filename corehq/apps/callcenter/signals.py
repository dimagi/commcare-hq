from corehq.apps.callcenter.utils import sync_user_cases, bootstrap_callcenter
from corehq.apps.users.signals import commcare_user_post_save


def sync_user_cases_signal(sender, **kwargs):
    return sync_user_cases(kwargs["couch_user"])

commcare_user_post_save.connect(sync_user_cases_signal)
