from corehq.apps.cachehq.invalidate import invalidate_document
from corehq.apps.domain.signals import commcare_domain_post_save
from corehq.apps.users.signals import couch_user_post_save


def invalidate_cached_domain(sender, domain, **kwargs):
    invalidate_document(domain, couch_db=domain.get_db())


def invalidate_cached_user(sender, couch_user, **kwargs):
    invalidate_document(couch_user, couch_db=couch_user.get_db())


commcare_domain_post_save.connect(invalidate_cached_domain)
couch_user_post_save.connect(invalidate_cached_user)
