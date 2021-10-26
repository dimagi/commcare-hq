import uuid

from attr import attrs, attrib
from nose.tools import nottest

from corehq.apps.registry.models import DataRegistry


@nottest
def create_registry_for_test(user, domain, invitations=None, grants=None, name=None, case_types=None):
    name = name or uuid.uuid4().hex
    schema = [{"case_type": case_type} for case_type in case_types or []]
    registry = DataRegistry.create(user, domain=domain, name=name, schema=schema)
    for invite in (invitations or []):
        invitation = registry.invitations.create(domain=invite.domain)
        if invite.accepted:
            invitation.accept(user)
        if invite.rejected:
            invitation.reject(user)

    for grant in (grants or []):
        registry.grants.create(
            from_domain=grant.from_domain,
            to_domains=grant.to_domains,
        )

    return registry


@attrs
class Invitation:
    domain = attrib()
    accepted = attrib(default=True, kw_only=True)
    rejected = attrib(default=False, kw_only=True)


@attrs
class Grant:
    from_domain = attrib()
    to_domains = attrib(factory=list)
