from couchdbkit.ext.django.schema import *
from django.contrib.sites.models import Site
from django.core.urlresolvers import reverse
from django.template.loader import render_to_string
from corehq.apps.users.models import WebUser, MultiMembershipMixin, Invitation
from dimagi.utils.couch.undo import UndoableDocument, DeleteDocRecord
from dimagi.utils.django.email import send_HTML_email


class Organization(Document):
    name = StringProperty() # for example "worldvision"
    title = StringProperty() # for example "World Vision"

    #metadata
    email = StringProperty()
    url = StringProperty()
    location = StringProperty()
    logo_filename = StringProperty()

    @classmethod
    def get_by_name(cls, name, strict=False):
        extra_args = {'stale': 'update_after'} if not strict else {}
        result = cls.view("orgs/by_name",
            key=name,
            reduce=False,
            include_docs=True,
            **extra_args
        ).one()
        return result

    @classmethod
    def get_all(cls):
        """This will eventually be a big operation"""
        result = cls.view("orgs/by_name",
            reduce=False,
            include_docs=True,
            stale='update_after',
        ).all()
        return result

    def get_logo(self):
        if self.logo_filename:
            return (self.fetch_attachment(self.logo_filename), self._attachments[self.logo_filename]['content_type'])
        else:
            return None

    def __str__(self):
        return self.title

    def get_members(self):
        from corehq.apps.users.models import WebUser
        return WebUser.by_organization(self.name)


class Team(UndoableDocument, MultiMembershipMixin):
    name = StringProperty()
    organization = StringProperty()

    def get_members(self):
        return WebUser.by_organization(self.organization, team_id=self.get_id)

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

class OrgInvitation(Invitation):
    doc_type = "OrgInvitation"
    organization = StringProperty()

    def send_activation_email(self):
        url = "http://%s%s" % (Site.objects.get_current().domain,
                               reverse("orgs_accept_invitation", args=[self.organization, self.get_id]))
        params = {"organization": self.organization, "url": url, "inviter": self.get_inviter().formatted_name}
        text_content = render_to_string("orgs/email/org_invite.txt", params)
        html_content = render_to_string("orgs/email/org_invite.html", params)
        subject = 'Invitation from %s to join CommCareHQ' % self.get_inviter().formatted_name
        send_HTML_email(subject, self.email, html_content, text_content=text_content)
