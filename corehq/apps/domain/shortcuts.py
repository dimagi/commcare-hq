"""
Shortcuts for working with domains and users.
"""


def create_domain(name, active=True):
    """Create domain without secure submissions for tests"""
    return Domain.get_or_create_with_name(name=name, is_active=active,
                                          secure_submissions=False)


def create_user(username, password, is_staff=False, is_superuser=False, is_active=True, password_hashed=False, **kwargs):
    user = User()
    user.username = username.lower()
    for key, val in kwargs.items():
        if key and val:
            setattr(user, key, val)
    user.is_staff = is_staff
    user.is_active = is_active
    user.is_superuser = is_superuser
    if not password_hashed:
        user.set_password(password)
    else:
        user.password = password

    # at this stage in the process there is no couch user so it's pointless
    # trying to update it.
    user.DO_NOT_SAVE_COUCH_USER = True
    user.save()
    return user


def publish_domain_saved(domain_obj):
    from corehq.apps.change_feed import topics
    from corehq.apps.change_feed.producer import producer

    producer.send_change(topics.DOMAIN, _domain_to_change_meta(domain_obj))


def _domain_to_change_meta(domain_obj):
    from corehq.apps.change_feed import data_sources
    from corehq.apps.change_feed.document_types import change_meta_from_doc

    domain_doc = domain_obj.to_json()
    return change_meta_from_doc(
        document=domain_doc,
        data_source_type=data_sources.SOURCE_COUCH,
        data_source_name=Domain.get_db().dbname,
    )


from django.contrib.auth.models import User

from corehq.apps.domain.models import Domain
