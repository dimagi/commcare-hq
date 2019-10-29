import json

from corehq.apps.api.resources import v0_5
from corehq.apps.groups.models import Group
from corehq.elastic import send_to_elasticsearch, get_es_instance
from corehq.pillows.mappings.group_mapping import GROUP_INDEX_INFO
from pillowtop.es_utils import initialize_index_and_mapping

from .utils import APIResourceTest


class TestGroupResource(APIResourceTest):

    resource = v0_5.GroupResource
    api_name = 'v0.5'

    @classmethod
    def setUpClass(cls):
        super(TestGroupResource, cls).setUpClass()
        cls.es = get_es_instance()
        cls.es.indices.delete(GROUP_INDEX_INFO.index)
        initialize_index_and_mapping(cls.es, GROUP_INDEX_INFO)

    def test_get_list(self):

        group = Group({"name": "test", "domain": self.domain.name})
        group.save()
        send_to_elasticsearch('groups', group.to_json())
        self.es.indices.refresh(GROUP_INDEX_INFO.index)
        self.addCleanup(group.delete)
        self.addCleanup(lambda: send_to_elasticsearch('groups', group.to_json(), delete=True))
        backend_id = group.get_id

        response = self._assert_auth_get_resource(self.list_endpoint)
        self.assertEqual(response.status_code, 200)

        api_groups = json.loads(response.content)['objects']
        self.assertEqual(len(api_groups), 1)
        self.assertEqual(api_groups[0]['id'], backend_id)
        self.assertEqual(api_groups[0], {
            'case_sharing': False,
            'domain': 'qwerty',
            'id': backend_id,
            'metadata': {},
            'name': 'test',
            'path': [],
            'reporting': True,
            'resource_uri': '/a/qwerty/api/v0.5/group/{}/'.format(backend_id),
            'users': [],
        })

    def test_get_single(self):

        group = Group({"name": "test", "domain": self.domain.name})
        group.save()
        self.addCleanup(group.delete)
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
            'path': [],
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

        group = Group({"name": "test", "domain": self.domain.name})
        group.save()
        self.addCleanup(group.delete)

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

        group = Group({"name": "test", "domain": self.domain.name})
        group.save()
        self.addCleanup(group.delete)

        backend_id = group._id
        response = self._assert_auth_post_resource(self.single_endpoint(backend_id), '', method='DELETE')
        self.assertEqual(response.status_code, 204, response.content)
        self.assertEqual(0, len(Group.by_domain(self.domain.name)))
