import json

from django.test import TestCase
from django.urls import reverse

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.userreports.const import UCR_NAMED_EXPRESSION
from corehq.apps.userreports.models import UCRExpression
from corehq.apps.users.models import HQApiKey, WebUser
from corehq.motech.generic_inbound.models import ConfigurableAPI


class TestGenericInboundAPI(TestCase):
    domain_name = 'ucr-api-test'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain = create_domain(cls.domain_name)
        cls.user = WebUser.create(cls.domain_name, 'test@dimagi.com', 'secret', None, None)
        cls.addClassCleanup(cls.domain.delete)

        cls.expression = UCRExpression.objects.create(
            name='create_sport',
            domain=cls.domain_name,
            expression_type=UCR_NAMED_EXPRESSION,
            definition={
                'type': 'dict',
                'properties': {
                    'case_type': 'sport',
                    'case_name': {
                        'type': 'jsonpath',
                        'jsonpath': 'body.name',
                    },
                    'is_team_sport': {
                        'type': 'jsonpath',
                        'jsonpath': 'body.is_team_sport'
                    }
                }
            },
        )

        cls.generic_api = ConfigurableAPI.objects.create(
            domain=cls.domain_name,
            transform_expression=cls.expression
        )

        cls.api_key, _ = HQApiKey.objects.get_or_create(user=cls.user.get_django_user())

        cls.url = reverse('generic_inbound_api', args=[cls.domain_name, cls.generic_api.url_key])

    def test_post_denied(self):
        response = self.client.post(self.url, data={})
        self.assertEqual(response.status_code, 401)

    def test_post_not_json(self):
        response = self.client.post(
            self.url, data={}, HTTP_AUTHORIZATION=f"apikey {self.user.username}:{self.api_key.key}"
        )
        self.assertEqual(response.status_code, 400)

    def test_post(self):
        data = json.dumps({'name': 'cricket', 'is_team_sport': True})
        response = self.client.post(
            self.url, data=data, content_type="application/json",
            HTTP_AUTHORIZATION=f"apikey {self.user.username}:{self.api_key.key}"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'case_type': 'sport', 'case_name': 'cricket', 'is_team_sport': True})
