import dataclasses
from datetime import datetime

from django.test import SimpleTestCase

from corehq.apps.userreports.const import UCR_NAMED_EXPRESSION
from corehq.apps.userreports.exceptions import BadSpecError
from corehq.apps.userreports.models import UCRExpression
from corehq.motech.generic_inbound.models import ConfigurableAPI
from corehq.motech.generic_inbound.utils import get_evaluation_context
from corehq.motech.generic_inbound.views import _execute_case_api


@dataclasses.dataclass
class MockUser:
    user_id: str = "123"
    username: str = "integration_user"
    password: str = "sha256:123123"
    date_joined: datetime = dataclasses.field(default_factory=datetime.utcnow)
    user_session_data: dict = dataclasses.field(default_factory=dict)


class TestGenericInboundAPI(SimpleTestCase):
    domain_name = 'ucr-api-test'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = MockUser()

        cls.expression = UCRExpression(
            name='create_sport',
            domain=cls.domain_name,
            expression_type=UCR_NAMED_EXPRESSION,
            definition={
                'type': 'dict',
                'properties': {
                    'create': True,
                    'case_type': 'sport',
                    'case_name': {
                        'type': 'jsonpath',
                        'jsonpath': 'body.name',
                    },
                    'owner_id': {
                        'type': 'jsonpath',
                        'jsonpath': 'user.uuid'
                    },
                    'properties': {
                        'type': 'dict',
                        'properties': {
                            'is_team_sport': {
                                'type': 'jsonpath',
                                'jsonpath': 'body.is_team_sport',
                                'datatype': 'string',
                            }
                        }
                    }
                }
            },
        )

        cls.generic_api = ConfigurableAPI(
            domain=cls.domain_name,
            transform_expression=cls.expression
        )

        cls.context = get_evaluation_context(cls.user, 'post', "", {}, {})

    def test_spec_error(self):
        api_model = ConfigurableAPI(
            domain=self.domain_name,
            transform_expression=UCRExpression(definition={})
        )
        with self.assertRaises(BadSpecError):
            _execute_case_api(self.domain_name, self.user, "device_id", self.context, api_model)
