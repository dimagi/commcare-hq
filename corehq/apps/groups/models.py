"""
couch models go here
"""
from __future__ import absolute_import
import datetime
from couchdbkit.ext.django.schema import *
from couchdbkit.schema.properties_proxy import SchemaListProperty
from corehq.apps.domain.models import Domain

class Group(Document):
    """
    The main use case for these 'groups' of users is currently
    so that we can break down reports by arbitrary regions.
    
    (Things like who sees what reports are determined by permissions.) 
    """
    domain = StringProperty()
    name = StringProperty()
    # a list of user ids for users
    users = ListProperty()
    # a list of Documents for groups
    groups = SchemaListProperty(Document)
    # hm, couchdbkit doesn't seem to support 'self'. 
    # but maybe that's ok. this is, after all, couch.

    def add_user(self, couch_user_id):
        if couch_user_id not in self.users:
            self.users.append(couch_user_id)
        
    def remove_user(self, couch_user_id):
        if couch_user_id in self.users:
            for user in self.users:
                if user == couch_user_id:
                    del user
                    return
