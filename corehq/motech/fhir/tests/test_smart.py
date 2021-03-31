import base64
import hashlib
import json
from datetime import datetime, timedelta
from urllib.parse import parse_qs, urlparse

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils.crypto import get_random_string

from oauth2_provider.models import (
    get_access_token_model,
    get_application_model,
    get_grant_model,
    get_refresh_token_model,
)

from casexml.apps.case.mock import CaseFactory, CaseIndex, CaseStructure

from corehq.apps.consumer_user.models import (
    CaseRelationshipOauthToken,
    ConsumerUser,
    ConsumerUserCaseRelationship,
)
from corehq.form_processor.tests.utils import FormProcessorTestUtils
from corehq.motech.fhir.views import SmartAuthView
from corehq.motech.fhir.utils import case_access_authorized

Application = get_application_model()
AccessToken = get_access_token_model()
Grant = get_grant_model()
RefreshToken = get_refresh_token_model()
UserModel = get_user_model()

DOMAIN = "test_domain"


class TokenEndpointTests(TestCase):

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
            smart_on_fhir_compatible=True,
        )

    def tearDown(self):
        FormProcessorTestUtils.delete_all_cases()
        self.application.delete()
        self.test_user.delete()
        ConsumerUserCaseRelationship.objects.all().delete()
        ConsumerUser.objects.all().delete()
        super().tearDown()

    def _generate_pkce_codes(self, algorithm, length=43):
        """
        Helper method to generate pkce codes
        From https://github.com/jazzband/django-oauth-toolkit/blob/9d2aac2480b2a1875eb52612661992f73606bade/tests/test_authorization_code.py#L614  # noqa
        """
        code_verifier = get_random_string(length)
        if algorithm == "S256":
            code_challenge = (
                base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest()).decode().rstrip("=")
            )
        else:
            code_challenge = code_verifier
        return code_verifier, code_challenge

    def _get_pkce_auth_code(self, code_challenge, code_challenge_method, case_id=None):
        response = self._get_pkce_auth_response(code_challenge, code_challenge_method, case_id)
        query_dict = parse_qs(urlparse(response["Location"]).query)
        return query_dict["code"].pop()

    def _get_pkce_auth_response(self, code_challenge, code_challenge_method, case_id=None):
        """
        From https://github.com/jazzband/django-oauth-toolkit/blob/9d2aac2480b2a1875eb52612661992f73606bade/tests/test_authorization_code.py#L627  # noqa
        """
        authcode_data = {
            "client_id": self.application.client_id,
            "state": "random_state_string",
            "scope": "launch/patient",
            "redirect_uri": "http://example.org",
            "response_type": "code",
            "allow": True,
            "code_challenge": code_challenge,
            "code_challenge_method": code_challenge_method,
            "case_id": case_id,
        }

        response = self.client.post(reverse(SmartAuthView.urlname, kwargs={"domain": DOMAIN}), data=authcode_data)
        return response

    def test_patient_case_id_included_single_relationship(self):
        case = self.case_factory.create_case(case_name="Demographic Case")

        ConsumerUserCaseRelationship.objects.create(
            consumer_user=self.consumer_user, case_id=case.case_id, domain=DOMAIN
        )

        self.client.login(username=self.test_user.username, password="123456")
        code_verifier, code_challenge = self._generate_pkce_codes("S256")
        authorization_code = self._get_pkce_auth_code(code_challenge, "S256", case_id=case.case_id)

        token_request_data = {
            "grant_type": "authorization_code",
            "code": authorization_code,
            "redirect_uri": "http://example.org",
            "client_id": self.application.client_id,
            "code_verifier": code_verifier,
        }

        response = self.client.post(
            reverse("smart_token_view", kwargs={"domain": DOMAIN}), data=token_request_data
        )
        content = json.loads(response.content.decode("utf-8"))
        self.assertEqual(content["patient"], case.case_id)

    def test_token_rejected_invalid_case(self):
        case = self.case_factory.create_case(case_name="Demographic Case 1")

        ConsumerUserCaseRelationship.objects.create(
            consumer_user=self.consumer_user, case_id=case.case_id, domain=DOMAIN
        )

        self.client.login(username=self.test_user.username, password="123456")
        code_verifier, code_challenge = self._generate_pkce_codes("S256")
        auth_response = self._get_pkce_auth_response(code_challenge, "S256", case_id="INVALID CASE ID")
        auth_response.render()
        self.assertTrue(
            "INVALID CASE ID is not one of the available choices." in auth_response.content.decode('utf-8')
        )

    def test_no_cases_no_auth(self):
        self.client.login(username=self.test_user.username, password="123456")
        code_verifier, code_challenge = self._generate_pkce_codes("S256")
        auth_response = self._get_pkce_auth_response(code_challenge, "S256", case_id='')
        self.assertEqual(404, auth_response.status_code)


class TestSmartAuth(TestCase):
    """Test case access
    """

    # Case owned
    # case not owned
    # descendent case

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
