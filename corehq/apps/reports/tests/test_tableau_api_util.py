from unittest import mock
from corehq.apps.reports.const import HQ_TABLEAU_GROUP_NAME
from corehq.apps.reports.tests.test_tableau_api_session import TestTableauAPISession
from corehq.apps.reports.models import (
    TableauConnectedApp,
    TableauServer,
    TableauUser,
    TableauAPISession
)
from corehq.apps.reports.util import (
    TableauGroupTuple,
    get_all_tableau_groups,
    get_tableau_groups_for_user,
    get_matching_tableau_users_from_other_domains,
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

        self.domain2 = 'test-domain-name2'
        self.repeated_tableau_server = TableauServer.objects.create(
            domain=self.domain2,
            server_type='server',
            server_name='test_server',
            target_site='target site'
        )
        TableauConnectedApp.objects.create(
            server=self.repeated_tableau_server
        )
        self.repeated_tableau_user = TableauUser.objects.create(
            server=self.repeated_tableau_server,
            username='pbeasley',
            tableau_user_id='asdf',
            role='Explorer'
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
    def test_add_repeated_tableau_user(self, mock_request):
        # Call to API to add user should not be made if another TableauUser with username exists.
        mock_request.side_effect = _mock_create_session_responses(self)
        new_username = 'dschrute'
        add_tableau_user(self.domain2, new_username)
        self.assertEqual(len(TableauUser.objects.filter(username=new_username)), 2)
        new_user = TableauUser.objects.get(username=new_username, server__domain=self.domain2)
        # New TableauUser should copy the user ID from the existing TableauUser with the same username.
        self.assertEqual(new_user.tableau_user_id, 'wer789iop')

    @mock.patch('corehq.apps.reports.models.requests.request')
    def test_delete_tableau_user(self, mock_request):
        mock_request.side_effect = (_mock_create_session_responses(self)
        + [self.tableau_instance.delete_user_response()])
        TableauUser.objects.get(username='dschrute')
        delete_tableau_user(self.domain, 'dschrute')
        self.assertFalse(TableauUser.objects.filter(username='dschrute'))

    @mock.patch('corehq.apps.reports.models.requests.request')
    def test_delete_repeated_tableau_user(self, mock_request):
        # No delete user call to the API should be made if another TableauUser with username exists.
        mock_request.side_effect = _mock_create_session_responses(self)
        delete_username = 'pbeasley'
        TableauUser.objects.get(username=delete_username, server__domain=self.domain2)
        delete_tableau_user(self.domain2, delete_username)
        self.assertFalse(TableauUser.objects.filter(username=delete_username, server__domain=self.domain2))
        self.assertTrue(TableauUser.objects.filter(username=delete_username, server__domain=self.domain))

    @mock.patch('corehq.apps.reports.models.requests.request')
    @mock.patch('corehq.apps.reports.util._update_user_remote')
    def test_update_tableau_user(self, mock_update_user_remote, mock_request):
        TableauServer.objects.filter(domain=self.domain).update(allowed_tableau_groups=['group3', 'group5',
                                                                                        'group6'])
        mock_request.side_effect = (_mock_create_session_responses(self)
        + [self.tableau_instance.get_groups_for_user_id_response()])
        self.assertEqual(
            TableauUser.objects.get(username='pbeasley', server__domain=self.domain).role,
            'Explorer'
        )
        self.assertEqual(
            TableauUser.objects.get(username='pbeasley', server__domain=self.domain2).role,
            'Explorer'
        )
        update_tableau_user(self.domain, 'pbeasley', 'Viewer',
            groups=[TableauGroupTuple(name='group4', id='d234u'), TableauGroupTuple(name='group5', id='u908e')]
        )
        self.assertEqual(
            TableauUser.objects.get(username='pbeasley', server__domain=self.domain).role,
            'Viewer'
        )
        # User with matching username from another domain should have role updated.
        self.assertEqual(
            TableauUser.objects.get(username='pbeasley', server__domain=self.domain2).role,
            'Viewer'
        )
        mock_update_user_remote.assert_called_once()
        self.assertListEqual(sorted([TableauGroupTuple(name='group5', id='u908e'),
                                     TableauGroupTuple(name='group1', id='1a2b3'),
                                     TableauGroupTuple(name='group2', id='c4d5e')]),
                             sorted(mock_update_user_remote.call_args.kwargs['groups']))

    @mock.patch('corehq.apps.reports.models.requests.request')
    def test_update_tableau_user_remote(self, mock_request):
        mock_request.side_effect = (_mock_create_session_responses(self)
        + [self.tableau_instance.get_groups_for_user_id_response(),
            self.tableau_instance.delete_user_response(),
            self.tableau_instance.create_user_response('pbeasley', 'Viewer'),
            self.tableau_instance.get_group_response(HQ_TABLEAU_GROUP_NAME),
            self.tableau_instance.add_user_to_group_response(),
            self.tableau_instance.add_user_to_group_response(),
            self.tableau_instance.add_user_to_group_response()])
        self.assertEqual(
            TableauUser.objects.get(username='pbeasley', server__domain=self.domain2).tableau_user_id,
            'asdf'
        )
        update_tableau_user(self.domain, 'pbeasley', 'Viewer',
            groups=[TableauGroupTuple(name='group4', id='d234u'), TableauGroupTuple(name='group5', id='u908e')]
        )
        # User with matching username from another domain should have ID updated.
        self.assertEqual(
            TableauUser.objects.get(username='pbeasley', server__domain=self.domain2).tableau_user_id,
            'gh23jk'
        )

    def test_get_matching_tableau_users_from_other_domains(self):
        matching_local_users = list(get_matching_tableau_users_from_other_domains(self.repeated_tableau_user))
        self.assertEqual(len(matching_local_users), 1)
        matched_user = matching_local_users[0]
        self.assertEqual(matched_user.username, 'pbeasley')
        self.assertEqual(matched_user.tableau_user_id, 'dfg789poi')
