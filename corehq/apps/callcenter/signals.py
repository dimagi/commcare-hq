from corehq.apps.callcenter.utils import sync_user_cases, bootstrap_callcenter
from corehq.apps.domain.signals import commcare_domain_post_save
from corehq.apps.users.signals import commcare_user_post_save


def sync_user_cases_signal(sender, **kwargs):
    return sync_user_cases(kwargs["couch_user"])

commcare_user_post_save.connect(sync_user_cases_signal)


def bootstrap_callcenter_domain_signal(sender, **kwargs):
    return bootstrap_callcenter(kwargs['domain'])


commcare_domain_post_save.connect(bootstrap_callcenter_domain_signal)
