from datetime import datetime, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase

from oauth2_provider.models import (
    get_access_token_model,
    get_application_model,
)

from casexml.apps.case.mock import CaseFactory, CaseIndex, CaseStructure

from corehq.apps.hqwebapp.models import HQOauthApplication
from corehq.apps.consumer_user.models import (
    CaseRelationshipOauthToken,
    ConsumerUser,
    ConsumerUserCaseRelationship,
)
from corehq.form_processor.tests.utils import FormProcessorTestUtils
from corehq.motech.fhir.utils import case_access_authorized

Application = get_application_model()
AccessToken = get_access_token_model()
UserModel = get_user_model()

DOMAIN = "test_domain"


class TestSmartAuth(TestCase):
    """Test case access
    """

    def setUp(self):
        super().setUp()
        self.case_factory = CaseFactory(DOMAIN)
        self.test_user = UserModel.objects.create_user("test_user", "test@example.com", "123456")
        self.consumer_user = ConsumerUser.objects.create(user=self.test_user)
        self.application = Application.objects.create(
            name="Test Application",
            redirect_uris=("http://example.org"),
            user=self.test_user,
            client_type=Application.CLIENT_PUBLIC,
            authorization_grant_type=Application.GRANT_AUTHORIZATION_CODE,
        )
        HQOauthApplication.objects.create(
            application=self.application,
            smart_on_fhir_compatible=True,
        )

        self.case = self.case_factory.create_case(case_name="Demographic Case")

        case_relationship = ConsumerUserCaseRelationship.objects.create(
            consumer_user=self.consumer_user, case_id=self.case.case_id, domain=DOMAIN
        )
        self.token = AccessToken.objects.create(
            user=self.test_user,
            token='a shiny token',
            application=self.application,
            expires=datetime.utcnow() + timedelta(days=15),
            scope='launch/patient user/Patient.read'
        )

        CaseRelationshipOauthToken.objects.create(
            consumer_user_case_relationship=case_relationship,
            access_token=self.token,
        )

    def tearDown(self):
        FormProcessorTestUtils.delete_all_cases()
        self.application.delete()
        self.test_user.delete()
        CaseRelationshipOauthToken.objects.all().delete()
        ConsumerUserCaseRelationship.objects.all().delete()
        ConsumerUser.objects.all().delete()
        super().tearDown()

    def test_can_access_owned_case(self):
        self.assertTrue(case_access_authorized(DOMAIN, self.token, self.case.case_id))

    def test_can_access_descendent_case(self):
        child_case = self.case_factory.create_or_update_case(
            CaseStructure(
                indices=[CaseIndex(CaseStructure(case_id=self.case.case_id))]
            )
        )[0]
        self.assertTrue(case_access_authorized(DOMAIN, self.token, child_case.case_id))

    def test_cant_access_parent_case(self):
        parent_case = self.case_factory.create_case(case_name="Parent")
        self.case_factory.create_or_update_case(
            CaseStructure(
                case_id=self.case.case_id,
                indices=[CaseIndex(CaseStructure(case_id=parent_case.case_id))]
            )
        )[0]
        self.assertFalse(case_access_authorized(DOMAIN, self.token, parent_case.case_id))

    def test_cant_access_unrelated_case(self):
        unrelated_case = self.case_factory.create_case()
        self.assertFalse(case_access_authorized(DOMAIN, self.token, unrelated_case.case_id))
