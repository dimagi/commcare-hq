from __future__ import absolute_import
from __future__ import unicode_literals
from couchdbkit import (
    BooleanProperty,
    DocumentSchema,
    ResourceNotFound,
    StringProperty,
)
from django.core.cache import cache
from corehq.apps.domain.models import Domain


def domain_requires_auth(domain):
    timeout = 10
    key = 'domain_requires_auth/{}'.format(domain)

    result = cache.get(key)
    if result is None:
        result = _domain_requires_auth(domain)
        cache.set(key, result, timeout=timeout)
    return result


def _domain_requires_auth(domain):
    domain_obj = Domain.get_by_name(domain, strict=True)
    if domain_obj:
        return domain_obj.secure_submissions
    else:
        raise ResourceNotFound('No domain with name %s' % domain)


class AuthContext(DocumentSchema):
    authenticated = BooleanProperty(default=False)
    domain = StringProperty(required=True)
    user_id = StringProperty()

    def _auth_required(self):
        domain_requires_auth(self.domain)

    def is_valid(self):
        try:
            return self.authenticated or not self._auth_required()
        except ResourceNotFound:
            return False


class WaivedAuthContext(AuthContext):

    def _auth_required(self):
        return False
