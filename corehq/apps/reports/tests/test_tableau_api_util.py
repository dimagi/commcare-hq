from unittest import mock
from corehq.apps.reports.const import HQ_TABLEAU_GROUP_NAME
from corehq.apps.reports.tests.test_tableau_api_session import TestTableauAPISession
from corehq.apps.reports.models import (
    TableauUser,
    TableauAPISession
)
from corehq.apps.reports.util import (
    TableauGroupTuple,
    get_all_tableau_groups,
    get_tableau_groups_for_user,
    add_tableau_user,
    delete_tableau_user,
    update_tableau_user
)


def _mock_create_session_responses(test_case):
    return [test_case.tableau_instance.API_version_response(),
            test_case.tableau_instance.sign_in_response()]

class TestTableauAPIUtil(TestTableauAPISession):

    def setUp(self):
        super(TestTableauAPIUtil, self).setUp()
        TableauUser.objects.create(
            server=self.test_server,
            username='pbeasley',
            tableau_user_id='dfg789poi',
            role='Explorer'
        )
        TableauUser.objects.create(
            server=self.test_server,
            username='dschrute',
            tableau_user_id='wer789iop',
            role='Viewer'
        )

    @mock.patch('corehq.apps.reports.models.requests.request')
    def test_create_session_for_domain(self, mock_request):
        mock_request.side_effect = _mock_create_session_responses(self)
        session = TableauAPISession.create_session_for_domain(self.domain)
        self.assertTrue(session.signed_in)

    @mock.patch('corehq.apps.reports.models.requests.request')
    def test_get_all_tableau_groups(self, mock_request):
        mock_request.side_effect = _mock_create_session_responses(self) + [
            self.tableau_instance.query_groups_response()
        ]
        group_tuples = get_all_tableau_groups(self.domain)
        self.assertEqual(len(group_tuples), 3)
        self.assertEqual(group_tuples[0].name, 'group1')
        self.assertEqual(group_tuples[2].id, 'zx39n')

    @mock.patch('corehq.apps.reports.models.requests.request')
    def test_get_tableau_groups_for_user(self, mock_request):
        mock_request.side_effect = (_mock_create_session_responses(self)
        + [self.tableau_instance.get_groups_for_user_id_response()])
        group_tuples = get_tableau_groups_for_user(self.domain, 'pbeasley')
        self.assertEqual(len(group_tuples), 2)
        self.assertEqual(group_tuples[0].name, 'group1')
        self.assertEqual(group_tuples[1].id, 'c4d5e')

    @mock.patch('corehq.apps.reports.models.requests.request')
    def test_add_tableau_user(self, mock_request):
        new_username = 'ricardo@company.com'
        mock_request.side_effect = (_mock_create_session_responses(self)
        + [self.tableau_instance.create_user_response(new_username, None),
           self.tableau_instance.get_group_response(HQ_TABLEAU_GROUP_NAME),
           self.tableau_instance.add_user_to_group_response()])
        add_tableau_user(self.domain, new_username)
        created_user = TableauUser.objects.get(username=new_username)
        self.assertEqual(created_user.tableau_user_id, 'gh23jk')
        self.assertEqual(created_user.role, TableauUser.Roles.UNLICENSED.value)
        self.assertEqual(created_user.server, self.test_server)

    @mock.patch('corehq.apps.reports.models.requests.request')
    def test_delete_tableau_user(self, mock_request):
        mock_request.side_effect = (_mock_create_session_responses(self)
        + [self.tableau_instance.delete_user_response()])
        TableauUser.objects.get(username='pbeasley')
        delete_tableau_user(self.domain, 'pbeasley')
        self.assertFalse(TableauUser.objects.filter(username='pbeasley'))

    @mock.patch('corehq.apps.reports.models.requests.request')
    def test_update_tableau_user(self, mock_request):
        mock_request.side_effect = (_mock_create_session_responses(self)
        + [self.tableau_instance.delete_user_response(),
            self.tableau_instance.create_user_response('dschrute', 'Explorer'),
            self.tableau_instance.get_group_response(HQ_TABLEAU_GROUP_NAME),
            self.tableau_instance.add_user_to_group_response(),
            self.tableau_instance.add_user_to_group_response(),
            self.tableau_instance.add_user_to_group_response()])
        self.assertEqual(
            TableauUser.objects.get(username='dschrute').role,
            'Viewer'
        )
        update_tableau_user(self.domain, 'dschrute', 'Explorer',
            groups=[TableauGroupTuple(name='group4', id='d234u'), TableauGroupTuple(name='group5', id='u908e')]
        )
        updated_user = TableauUser.objects.get(username='dschrute')
        self.assertEqual(
            updated_user.role,
            'Explorer'
        )
