from corehq.apps.domain.models import Domain
"""
Shortcuts for working with domains and users.
"""


def create_domain(name, active=True):
    """Create domain without secure submissions for tests"""
    return Domain.get_or_create_with_name(name=name, is_active=active,
                                          secure_submissions=False)
