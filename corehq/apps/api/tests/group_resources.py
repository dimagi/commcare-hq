from __future__ import absolute_import, unicode_literals

import json

from corehq.apps.api.resources import v0_5
from corehq.apps.groups.models import Group

from .utils import APIResourceTest


class TestGroupResource(APIResourceTest):

    resource = v0_5.GroupResource
    api_name = 'v0.5'

    def test_get_list(self):

        group = Group({"name": "test", "domain": self.domain.name})
        group.save()
        self.addCleanup(group.delete)
        backend_id = group.get_id

        response = self._assert_auth_get_resource(self.list_endpoint)
        self.assertEqual(response.status_code, 200)

        api_groups = json.loads(response.content)['objects']
        self.assertEqual(len(api_groups), 1)
        self.assertEqual(api_groups[0]['id'], backend_id)

    def test_get_single(self):

        group = Group({"name": "test", "domain": self.domain.name})
        group.save()
        self.addCleanup(group.delete)
        backend_id = group.get_id

        response = self._assert_auth_get_resource(self.single_endpoint(backend_id))
        self.assertEqual(response.status_code, 200)

        api_groups = json.loads(response.content)
        self.assertEqual(api_groups['id'], backend_id)

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
