# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from couchdbkit.ext.django import schema

from dimagi.ext.couchdbkit import Document


class RemoteLinkedDomainAuth(schema.DocumentSchema):
    username = schema.StringProperty()
    api_key = schema.StringProperty()


class DomainLink(Document):
    master_domain = schema.StringProperty()
    linked_domain = schema.StringProperty()
    # used for linking across remote instances of HQ
    remote_base_url = schema.StringProperty()
    remote_auth = schema.SchemaProperty(RemoteLinkedDomainAuth)
    last_pull = schema.DateTimeProperty()

    @classmethod
    def link_domains(cls, master_domain, linked_domain, remote_base_url=None):
        link = DomainLink(
            master_domain=master_domain,
            linked_domain=linked_domain,
            remote_base=remote_base_url
        )
        link.save()
        return link
