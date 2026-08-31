import datetime

from django.test import TestCase
from django.urls import reverse

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.models import WebUser
from corehq.form_processor.models import CommCareCase
from corehq.util.test_utils import flag_enabled

from ..populate import send_to_project_db
from ..views import QueryProjectDBView
from .util import project_db_table

SQL = "SELECT case_name FROM pet WHERE (:weight IS NULL OR number_prop__weight > :weight)"


class QueryProjectDBViewTest(TestCase):
    """The "Try it out" panel, which runs a query with values typed on the page"""

    domain = 'project-db-view-test'
    username = 'testuser@example.com'

    @classmethod
    def setUpTestData(cls):
        cls.domain_obj = create_domain(cls.domain)
        cls.addClassCleanup(cls.domain_obj.delete)
        cls.user = WebUser.create(
            cls.domain, cls.username, 'password', None, None, is_admin=True
        )
        cls.addClassCleanup(cls.user.delete, cls.domain, None)

    def setUp(self):
        self.client.login(username=self.username, password='password')
        flag = flag_enabled('PROJECT_DB')
        flag.__enter__()
        self.addCleanup(flag.__exit__, None, None, None)
        table = project_db_table(self.domain, 'pet', {'weight': 'number'})
        table.__enter__()
        self.addCleanup(table.__exit__, None, None, None)
        send_to_project_db(self.domain, 'pet', [CommCareCase(
            case_id='p1', domain=self.domain, type='pet', name='Fido',
            owner_id='o1',
            opened_on=datetime.datetime(2025, 1, 1),
            modified_on=datetime.datetime(2025, 6, 1),
            server_modified_on=datetime.datetime(2025, 6, 1),
            closed=False, external_id='', case_json={'weight': '20'}, indices=[],
        )])

    def _run(self, **params):
        return self.client.post(
            reverse(QueryProjectDBView.urlname, args=[self.domain]),
            {'sql': SQL, **{f'param:{k}': v for k, v in params.items()}},
            HTTP_HQ_HX_ACTION='run_query_with_parameters',
        )

    def test_blank_parameter_is_passed_as_null(self):
        # '' would fail to coerce to the numeric column it is compared against
        response = self._run(weight='')
        assert response.status_code == 200
        assert response.context.get('error') is None
        # a NULL parameter leaves the row unfiltered
        assert [row[0] for row in response.context['result'].rows] == ['Fido']

    def test_blank_parameter_is_rendered_back_as_blank(self):
        response = self._run(weight='')
        assert response.context['parameters'] == [{'name': 'weight', 'value': ''}]
        assert 'value="None"' not in response.content.decode()

    def test_parameter_value_is_rendered_back(self):
        response = self._run(weight='12')
        assert response.context['parameters'] == [{'name': 'weight', 'value': '12'}]
        assert [row[0] for row in response.context['result'].rows] == ['Fido']
