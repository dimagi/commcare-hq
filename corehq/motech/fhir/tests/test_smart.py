import base64
import hashlib
import json
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

from casexml.apps.case.mock import CaseFactory

from corehq.apps.consumer_user.models import (
    ConsumerUser,
    ConsumerUserCaseRelationship,
)
from corehq.form_processor.tests.utils import FormProcessorTestUtils
from corehq.motech.fhir.views import SmartAuthView

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

        self.application = Application.objects.create(
            name="Test Application",
            redirect_uris=("http://example.org"),
            user=self.test_user,
            client_type=Application.CLIENT_PUBLIC,
            authorization_grant_type=Application.GRANT_AUTHORIZATION_CODE,
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
                base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest())
                .decode()
                .rstrip("=")
            )
        else:
            code_challenge = code_verifier
        return code_verifier, code_challenge

    def _get_pkce_auth(self, code_challenge, code_challenge_method, case_id=None):
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
        query_dict = parse_qs(urlparse(response["Location"]).query)
        return query_dict["code"].pop()

    def test_patient_case_id_included_single_relationship(self):
        case = self.case_factory.create_case(case_name="Demographic Case")

        consumer_user = ConsumerUser.objects.create(user=self.test_user)
        consumer_user_case_relationship = ConsumerUserCaseRelationship.objects.create(
            consumer_user=consumer_user, case_id=case.case_id, domain=DOMAIN
        )

        self.client.login(username=self.test_user.username, password="123456")
        code_verifier, code_challenge = self._generate_pkce_codes("S256")
        authorization_code = self._get_pkce_auth(code_challenge, "S256", case_id=case.case_id)

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
        self.assertEqual(content["patient"], consumer_user_case_relationship.case_id)
