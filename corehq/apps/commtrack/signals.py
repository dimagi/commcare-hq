from corehq.apps.commtrack.util import bootstrap_commtrack_settings_if_necessary
from corehq.apps.domain.signals import commcare_domain_post_save


def bootstrap_commtrack_settings_if_necessary_signal(sender, **kwargs):
    bootstrap_commtrack_settings_if_necessary(kwargs['domain'])

commcare_domain_post_save.connect(bootstrap_commtrack_settings_if_necessary_signal)
