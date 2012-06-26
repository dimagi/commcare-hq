from couchdbkit.ext.django.schema import *
import util
from django import forms
from django.db import models
from corehq.apps.users.models import AuthorizableMixin


class Organization(Document):
    name = StringProperty() # for example "worldvision"
    title = StringProperty() # for example "World Vision"

    #metadata
    email = StringProperty()
    url = StringProperty()
    location = StringProperty()
    logo_filename = StringProperty()


    members = StringListProperty()

    @classmethod
    def get_by_name(cls, name):
        result = cls.view("orgs/by_name",
            key=name,
            reduce=False,
            include_docs=True).first()
        return result

    @classmethod
    def get_all(cls):
        result = cls.view("orgs/by_name",
            reduce=False,
            include_docs=True).all()
        return result

    def get_logo(self):
        if self.logo_filename:
            return (self.fetch_attachment(self.logo_filename), self._attachments[self.logo_filename]['content_type'])
        else:
            return None

    def __str__(self):
        return self.title

    def add_member(self, guid):
        for member in self.members:
            if member.id == guid:
                return False #already a member
        self.members.append(guid)
        self.save()
        return self.members


class Team(Document, AuthorizableMixin):
    name = StringProperty()
    organization = StringProperty()
    members = StringListProperty()

    def add_member(self, guid):
    #consistency check to make sure member is not already on the team
        if guid in self.members:
            return False
        self.members.append(guid)
        self.save()
        return self.members

    @classmethod
    def get_by_org_and_name(cls, org_name, name):
        return cls.view("orgs/team_by_org_and_name",
            key=[org_name,name],
            reduce=False,
            include_docs=True).one()

    @classmethod
    def get_by_org(cls, org_name):
        return cls.view("orgs/team_by_org_and_name",
            startkey = [org_name],
            endkey=[org_name,{}],
            reduce=False,
            include_docs=True).all()
