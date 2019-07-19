from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals
import json

import math
from django.test import TestCase
from elasticsearch import ConnectionError

from casexml.apps.case.tests.util import delete_all_cases, delete_all_xforms
from corehq.apps.callcenter.views import CallCenterOwnerOptionsView
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.groups.models import Group
from corehq.apps.locations.models import LocationType
from corehq.apps.locations.tests.util import make_loc
from corehq.apps.users.models import CommCareUser, WebUser
from corehq.elastic import get_es_new, send_to_elasticsearch
from corehq.pillows.mappings.group_mapping import GROUP_INDEX_INFO
from corehq.pillows.mappings.user_mapping import USER_INDEX_INFO
from corehq.toggles import CALL_CENTER_LOCATION_OWNERS, NAMESPACE_DOMAIN
from corehq.util import reverse
from corehq.util.elastic import ensure_index_deleted
from corehq.util.test_utils import trap_extra_setup
from django_digest.test import Client
from pillowtop.es_utils import initialize_index_and_mapping
from six.moves import range

TEST_DOMAIN = "cc-location-owner-test-domain"
CASE_TYPE = "cc-case-type"
LOCATION_TYPE = "my-location"


class CallCenterLocationOwnerOptionsViewTest(TestCase):

    @classmethod
    def setUpClass(cls):
        super(CallCenterLocationOwnerOptionsViewTest, cls).setUpClass()

        with trap_extra_setup(ConnectionError, msg="cannot connect to elasicsearch"):
            es = get_es_new()
            ensure_index_deleted(USER_INDEX_INFO.index)
            ensure_index_deleted(GROUP_INDEX_INFO.index)
            initialize_index_and_mapping(es, USER_INDEX_INFO)
            initialize_index_and_mapping(es, GROUP_INDEX_INFO)

        # Create domain
        cls.domain = create_domain(TEST_DOMAIN)
        cls.domain.save()

        CALL_CENTER_LOCATION_OWNERS.set(cls.domain.name, True, NAMESPACE_DOMAIN)

        cls.username = "foo"
        cls.password = "bar"
        cls.web_user = WebUser.create(cls.domain.name, cls.username, cls.password)
        cls.web_user.save()

        # Create case sharing groups
        cls.groups = []
        for i in range(2):
            group = Group(domain=TEST_DOMAIN, name="group{}".format(i), case_sharing=True)
            group.save()
            send_to_elasticsearch('groups', group.to_json())
            cls.groups.append(group)
        es.indices.refresh(GROUP_INDEX_INFO.index)
        cls.group_ids = {g._id for g in cls.groups}

        # Create locations
        LocationType.objects.get_or_create(
            domain=cls.domain.name,
            name=LOCATION_TYPE,
            shares_cases=True,
        )
        cls.locations = [
            make_loc('loc{}'.format(i), type=LOCATION_TYPE, domain=TEST_DOMAIN) for i in range(4)
        ]
        cls.location_ids = {l._id for l in cls.locations}

        # Create users
        cls.users = [CommCareUser.create(TEST_DOMAIN, 'user{}'.format(i), '***') for i in range(3)]
        for user in cls.users:
            send_to_elasticsearch('users', user.to_json())
        es.indices.refresh(USER_INDEX_INFO.index)
        cls.user_ids = {u._id for u in cls.users}

    @classmethod
    def tearDownClass(cls):
        super(CallCenterLocationOwnerOptionsViewTest, cls).tearDownClass()
        for user in cls.users:
            user.delete()
        CALL_CENTER_LOCATION_OWNERS.set(cls.domain.name, False, NAMESPACE_DOMAIN)
        cls.domain.delete()
        cls.web_user.delete()
        for loc in cls.locations:
            loc.delete()
        ensure_index_deleted(USER_INDEX_INFO.index)
        ensure_index_deleted(GROUP_INDEX_INFO.index)
        delete_all_cases()
        delete_all_xforms()

    def test_pages(self):
        """
        Confirm that all the groups/locations/users appear on the correct pages
        """
        client = Client()
        client.login(username=self.username, password=self.password)

        # expected_id_sets is a list of sets.
        # expected_id_sets is constructed such that
        # For option with index x yielded by the view:
        #   the option's id should be in expected_ids[x]
        expected_id_sets = [{"user_location"}, {"user_parent_location"}]

        for i in self.groups:
            expected_id_sets.append(self.group_ids)
        for i in self.locations:
            expected_id_sets.append(self.location_ids)
        for i in self.users:
            expected_id_sets.append(self.user_ids)

        page_size = 3  # using a small number because more pages will hopefully be more likely to reveal bugs
        expected_num_pages = int(math.ceil(len(expected_id_sets) / float(page_size)))
        for i in range(expected_num_pages):
            page = i + 1
            response = client.get(reverse(
                CallCenterOwnerOptionsView.url_name, args=[self.domain.name]),
                data={"page": page, "page_limit": page_size, "q": ""}
            )
            response_json = json.loads(response.content)
            self.assertEqual(response_json['total'], len(expected_id_sets))

            for item_index, item in enumerate(response_json['results']):
                id_ = item['id']
                option_index = ((page - 1) * page_size) + item_index
                self.assertTrue(
                    id_ in expected_id_sets[option_index],
                    "Unexpected item {} at index {}.".format(item, option_index)
                )
