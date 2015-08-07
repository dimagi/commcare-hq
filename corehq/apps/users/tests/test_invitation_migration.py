from corehq.apps.users.models import DomainInvitation, SQLDomainInvitation
from couchdbkit.exceptions import ResourceNotFound
from datetime import datetime
from django.test import TestCase
from time import sleep


class InvitationMigrationTestCase(TestCase):
    def setUp(self):
        self.domain = 'test-domain-invitation-migration'

    def tearDown(self):
        for invitation in DomainInvitation.view(
            'users/open_invitations_by_domain',
            startkey=[self.domain],
            endkey=[self.domain, {}],
            include_docs=True,
            reduce=False,
        ).all():
            invitation.delete()

        SQLDomainInvitation.objects.filter(domain=self.domain).delete()

    def getCouchCount(self):
        result = DomainInvitation.view(
            'users/open_invitations_by_domain',
            startkey=[self.domain],
            endkey=[self.domain, {}],
            include_docs=False,
            reduce=True,
        ).all()
        if result:
            return result[0]['value']
        return 0

    def getSQLCount(self):
        return SQLDomainInvitation.objects.filter(domain=self.domain).count()

    def testCRUD(self):
        initialCouchCount = self.getCouchCount()
        initialSQLCount = self.getSQLCount()

        # Creating couch should create SQL
        couch = DomainInvitation()
        couch.email = 'one@dimagi.com'
        couch.role = 'role1'
        couch.invited_by = 'fake_user_id'
        couch.invited_on = datetime.now()
        couch.domain = self.domain
        couch.save()
        sleep(1)
        couch_copy = SQLDomainInvitation.objects.get(couch_id=couch.get_id)
        self.assertEquals(couch_copy.email, 'one@dimagi.com')
        self.assertEquals(couch_copy.role, 'role1')
        self.assertEquals(self.getCouchCount(), initialCouchCount + 1)
        self.assertEquals(self.getSQLCount(), initialSQLCount + 1)

        # Creating SQL should create couch
        sql = SQLDomainInvitation()
        sql.email = 'two@dimagi.com'
        sql.role = 'role2'
        sql.invited_by = 'fake_user_id'
        sql.invited_on = datetime.now()
        sql.domain = self.domain
        sql.save()
        sleep(1)
        sql_copy = DomainInvitation.get(sql.couch_id)
        self.assertEquals(sql_copy.email, 'two@dimagi.com')
        self.assertEquals(sql_copy.role, 'role2')
        self.assertEquals(self.getCouchCount(), initialCouchCount + 2)
        self.assertEquals(self.getSQLCount(), initialSQLCount + 2)

        # Updating Couch should update SQL
        couch.email = 'three@dimagi.com'
        couch.role = 'role3'
        couch.save()
        sleep(1)
        couch_copy = SQLDomainInvitation.objects.get(couch_id=couch.get_id)
        self.assertEquals(couch_copy.email, 'three@dimagi.com')
        self.assertEquals(couch_copy.role, 'role3')
        self.assertEquals(self.getCouchCount(), initialCouchCount + 2)
        self.assertEquals(self.getSQLCount(), initialSQLCount + 2)

        # Updating SQL should update couch
        sql.email = 'four@dimagi.com'
        sql.role = 'role4'
        sql.save()
        sleep(1)
        sql_copy = DomainInvitation.get(sql.couch_id)
        self.assertEquals(sql_copy.email, 'four@dimagi.com')
        self.assertEquals(sql_copy.role, 'role4')
        self.assertEquals(self.getCouchCount(), initialCouchCount + 2)
        self.assertEquals(self.getSQLCount(), initialSQLCount + 2)

        # Deleting SQL should delete couch
        couch_id = couch.get_id
        couch.delete()
        with self.assertRaises(ResourceNotFound):
            DomainInvitation.get(couch_id)
        self.assertEquals(self.getCouchCount(), initialCouchCount + 1)
        self.assertEquals(self.getSQLCount(), initialSQLCount + 1)

        # Deleting couch should delete SQL
        couch_id = sql.couch_id
        sql.delete()
        with self.assertRaises(SQLDomainInvitation.DoesNotExist):
            SQLDomainInvitation.objects.get(couch_id=couch_id)
        self.assertEquals(self.getCouchCount(), initialCouchCount)
        self.assertEquals(self.getSQLCount(), initialSQLCount)
