from couchdbkit import MultipleResultsFound
from dimagi.ext.couchdbkit import *
from django.conf import settings
from django.template.loader import render_to_string
from corehq.apps.users.models import WebUser, MultiMembershipMixin, Invitation
from corehq.util.view_utils import absolute_reverse
from dimagi.utils.couch.cache import cache_core
from dimagi.utils.couch.undo import UndoableDocument, DeleteDocRecord
from corehq.apps.hqwebapp.tasks import send_html_email_async


class Organization(Document):
    name = StringProperty() # for example "worldvision"
    title = StringProperty() # for example "World Vision"

    #metadata
    email = StringProperty()
    url = StringProperty()
    location = StringProperty()
    logo_filename = StringProperty()
    verified = BooleanProperty(default=False)

    @classmethod
    def get_by_name(cls, name, strict=False):
        extra_args = {'stale': settings.COUCH_STALE_QUERY} if not strict else {}
        results = cache_core.cached_view(cls.get_db(), "orgs/by_name", key=name, reduce=False,
                                         include_docs=True, wrapper=cls.wrap, **extra_args)

        length = len(results)
        if length > 1:
            raise MultipleResultsFound("Error, Organization.get_by_name returned more than 1 result for %s" % name)
        elif length == 1:
            return list(results)[0]
        else:
            return None

    @classmethod
    def get_all(cls):
        """This will eventually be a big operation"""
        result = cls.view("orgs/by_name",
            reduce=False,
            include_docs=True,
            #stale=settings.COUCH_STALE_QUERY,
        ).all()
        return result

    def get_logo(self):
        if self.logo_filename:
            return self.fetch_attachment(self.logo_filename), self._attachments[self.logo_filename]['content_type']
        else:
            return None, None

    def __str__(self):
        return self.title

    def get_members(self):
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
        return cache_core.cached_view(
            cls.get_db(), "orgs/team_by_org_and_name",
            startkey=[org_name],
            endkey=[org_name, {}],
            reduce=False,
            include_docs=True,
            wrapper=cls.wrap,
        )

    @classmethod
    def get_by_domain(cls, domain):
        return cache_core.cached_view(cls.get_db(), "orgs/team_by_domain", key=domain, reduce=False,
                                      include_docs=True, wrapper=cls.wrap)

    def save(self, *args, **kwargs):
        # forcibly replace empty name with '-'
        self.name = self.name or '-'
        super(Team, self).save()

    def create_delete_record(self, *args, **kwargs):
        return DeleteTeamRecord(*args, **kwargs)

    def soft_delete(self):
        return super(Team, self).soft_delete(domain_included=False)

class DeleteTeamRecord(DeleteDocRecord):
    def get_doc(self):
        return Team.get(self.doc_id)


class OrgInvitation(Invitation):
    doc_type = "OrgInvitation"
    organization = StringProperty()

    def send_activation_email(self):
        url = absolute_reverse("orgs_accept_invitation",
                               args=[self.organization, self.get_id])
        params = {"organization": self.organization, "url": url,
                  "inviter": self.get_inviter().formatted_name}
        text_content = render_to_string("orgs/email/org_invite.txt", params)
        html_content = render_to_string("orgs/email/org_invite.html", params)
        subject = 'Invitation from %s to join CommCareHQ' % self.get_inviter().formatted_name
        send_html_email_async.delay(subject, self.email, html_content,
                                    text_content=text_content,
                                    email_from=settings.DEFAULT_FROM_EMAIL)


class OrgRequest(Document):
    doc_type = "OrgRequest"
    organization = StringProperty()
    domain = StringProperty()
    requested_by = StringProperty()
    requested_on = DateTimeProperty()
    seen = BooleanProperty(default=False)

    @classmethod
    def get_requests(cls, organization, domain=None, user_id=None):
        key = [organization]
        if domain:
            key.append(domain)
        if user_id:
            key.append(user_id)

        # todo - forcing invalidating on all requests while we turn these features on slowly
        results = cache_core.cached_view(
            cls.get_db(), "orgs/org_requests",
            startkey=key,
            endkey=key + [{}],
            reduce=False,
            include_docs=True,
            wrapper=cls.wrap,
        )

        #return results.all() if not user_id else results.one()

        if not user_id:
            return results
        else:
            try:
                length = len(results)
                if length == 1:
                    return results[0]
                elif length > 0:
                    raise MultipleResultsFound("OrgRequests found multiple results for %s" % key)
            except IndexError:
                return None
