import dataclasses
from datetime import datetime

from django.test import SimpleTestCase

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

    def test_spec_error(self):
        api_model = ConfigurableAPI(
            domain=self.domain_name,
            transform_expression=UCRExpression(definition={})
        )
        user = MockUser()
        context = get_evaluation_context(user, 'post', {}, {}, {})
        with self.assertRaises(BadSpecError):
            _execute_case_api(self.domain_name, user, "device_id", context, api_model)
