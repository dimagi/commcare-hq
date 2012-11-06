from couchdbkit.ext.django.schema import *
from corehq import util
from django import forms
from django.db import models
from corehq.apps.users.models import AuthorizableMixin, WebUser
from dimagi.utils.couch.undo import UndoableDocument, DeleteDocRecord


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
        if guid not in self.members:
            self.members.append(guid)
            self.save()
        return self.members


class Team(UndoableDocument, AuthorizableMixin):
    name = StringProperty()
    organization = StringProperty()
    member_ids = StringListProperty()

#    def add_member(self, guid):
#    #consistency check to make sure member is not already on the team
#        if guid in self.members:
#            return False
#        self.members.append(guid)
#        self.save()
#        return self.members

    def add_member(self, couch_user_id):
        from corehq.apps.users.models import WebUser
        if not isinstance(couch_user_id, basestring):
            couch_user_id = couch_user_id.user_id
        if couch_user_id not in self.member_ids:
            self.member_ids.append(couch_user_id)
            user = WebUser.get_by_user_id(couch_user_id)
            user.teams.append([self.name, self.get_id])
            user.save()
        self.save()

    def remove_member(self, couch_user_id):
        from corehq.apps.users.models import WebUser
        if couch_user_id in self.member_ids:
            for i in range(0,len(self.member_ids)):
                if self.member_ids[i] == couch_user_id:
                    del self.member_ids[i]
                    user = WebUser.get_by_user_id(couch_user_id)
                    user.teams.remove([self.name, self.get_id])
                    self.save()
                    user.save()
                    return

    def get_member_ids(self, is_active=True):
        return [user.user_id for user in self.get_members(is_active)]

    def get_members(self, is_active=True):
        users = [WebUser.get_by_user_id(user_id) for user_id in self.member_ids]
        users = [user for user in users if not user.is_deleted()]
        if is_active is True:
            return [user for user in users if user.is_active]
        else:
            return users

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

    @classmethod
    def get_by_domain(cls, domain):
        return cls.view("orgs/team_by_domain",
            key=domain,
            reduce=False,
            include_docs=True).all()

    def save(self, *args, **kwargs):
        # forcibly replace empty name with '-'
        self.name = self.name or '-'
        super(Team, self).save()

    def create_delete_record(self, *args, **kwargs):
        return DeleteTeamRecord(*args, **kwargs)

class DeleteTeamRecord(DeleteDocRecord):
    def get_doc(self):
        return Team.get(self.doc_id)
