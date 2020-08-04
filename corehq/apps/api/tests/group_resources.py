import json

from corehq.apps.api.resources import v0_5
from corehq.apps.groups.models import Group
from corehq.elastic import send_to_elasticsearch, get_es_new
from corehq.pillows.mappings.group_mapping import GROUP_INDEX_INFO
from corehq.util.elastic import ensure_index_deleted
from pillowtop.es_utils import initialize_index_and_mapping

from .utils import APIResourceTest


class TestGroupResource(APIResourceTest):

    resource = v0_5.GroupResource
    api_name = 'v0.5'

    @classmethod
    def setUpClass(cls):
        super(TestGroupResource, cls).setUpClass()
        cls.es = get_es_new()
        ensure_index_deleted(GROUP_INDEX_INFO.index)
        initialize_index_and_mapping(cls.es, GROUP_INDEX_INFO)

    def test_get_list(self):

        # create groups in jumbled (non-alphabetical) order
        group_b = self._add_group(Group({"name": "test_b", "domain": self.domain.name}), send_to_es=True)
        group_d = self._add_group(Group({"name": "test_d", "domain": self.domain.name}), send_to_es=True)
        group_c = self._add_group(Group({"name": "test_c", "domain": self.domain.name}), send_to_es=True)
        group_a = self._add_group(Group({"name": "test_a", "domain": self.domain.name}), send_to_es=True)
        groups_in_order = [group_a, group_b, group_c, group_d]

        response = self._assert_auth_get_resource(self.list_endpoint)
        self.assertEqual(response.status_code, 200)

        api_groups = json.loads(response.content)['objects']
        self.assertEqual(len(api_groups), 4)
        for i, group in enumerate(groups_in_order):
            self.assertEqual(api_groups[i]['id'], group.get_id, f"group_id for api_groups[{i}] is wrong")
            self.assertEqual(api_groups[i], {
                'case_sharing': False,
                'domain': 'qwerty',
                'id': group.get_id,
                'metadata': {},
                'name': group.name,
                'reporting': True,
                'resource_uri': '/a/qwerty/api/v0.5/group/{}/'.format(group.get_id),
                'users': [],
            })

    def test_get_single(self):
        group = self._add_group(Group({"name": "test", "domain": self.domain.name}))
        backend_id = group.get_id

        response = self._assert_auth_get_resource(self.single_endpoint(backend_id))
        self.assertEqual(response.status_code, 200)

        api_groups = json.loads(response.content)
        self.assertEqual(api_groups['id'], backend_id)
        self.assertEqual(api_groups, {
            'case_sharing': False,
            'domain': 'qwerty',
            'id': backend_id,
            'metadata': {},
            'name': 'test',
            'reporting': True,
            'resource_uri': '/a/qwerty/api/v0.5/group/{}/'.format(backend_id),
            'users': [],
        })

    def test_create(self):

        self.assertEqual(0, len(Group.by_domain(self.domain.name)))

        group_json = {
            "case_sharing": True,
            "metadata": {
                "localization": "Ghana"
            },
            "name": "test group",
            "reporting": True,
        }
        response = self._assert_auth_post_resource(self.list_endpoint,
                                    json.dumps(group_json),
                                    content_type='application/json')
        self.assertEqual(response.status_code, 201)
        [group_back] = Group.by_domain(self.domain.name)
        self.addCleanup(group_back.delete)
        self.assertEqual(group_back.name, "test group")
        self.assertTrue(group_back.reporting)
        self.assertTrue(group_back.case_sharing)
        self.assertEqual(group_back.metadata["localization"], "Ghana")

    def test_update(self):

        group = self._add_group(Group({"name": "test", "domain": self.domain.name}))

        group_json = {
            "case_sharing": True,
            "metadata": {
                "localization": "Ghana"
            },
            "name": "test group",
            "reporting": True,
        }

        backend_id = group._id
        response = self._assert_auth_post_resource(self.single_endpoint(backend_id),
                                                   json.dumps(group_json),
                                                   content_type='application/json',
                                                   method='PUT')
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(1, len(Group.by_domain(self.domain.name)))
        modified = Group.get(backend_id)
        self.assertEqual(modified.name, "test group")
        self.assertTrue(modified.reporting)
        self.assertTrue(modified.case_sharing)
        self.assertEqual(modified.metadata["localization"], "Ghana")

    def test_delete_group(self):

        group = self._add_group(Group({"name": "test", "domain": self.domain.name}))

        backend_id = group._id
        response = self._assert_auth_post_resource(self.single_endpoint(backend_id), '', method='DELETE')
        self.assertEqual(response.status_code, 204, response.content)
        self.assertEqual(0, len(Group.by_domain(self.domain.name)))

    def _add_group(self, group, send_to_es=False):
        group.save()
        self.addCleanup(group.delete)
        if send_to_es:
            send_to_elasticsearch('groups', group.to_json())
            self.addCleanup(lambda: send_to_elasticsearch('groups', group.to_json(), delete=True))
            self.es.indices.refresh(GROUP_INDEX_INFO.index)
        return group
