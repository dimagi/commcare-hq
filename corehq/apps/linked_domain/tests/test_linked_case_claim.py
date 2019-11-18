import json

from mock import patch
from tastypie.models import ApiKey

from corehq.apps.case_search.models import (
    CaseSearchConfig,
    CaseSearchQueryAddition,
    FuzzyProperties,
    IgnorePatterns,
)
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.linked_domain.decorators import REMOTE_REQUESTER_HEADER
from corehq.apps.linked_domain.tests.test_linked_apps import BaseLinkedAppsTest
from corehq.apps.linked_domain.updates import update_case_search_config
from corehq.apps.users.models import WebUser
from corehq.util import reverse


class BaseLinkedCaseClaimTest(BaseLinkedAppsTest):
    @classmethod
    def setUpClass(cls):
        super(BaseLinkedCaseClaimTest, cls).setUpClass()
        cls.search_config = CaseSearchConfig(domain=cls.domain, enabled=True)
        cls.search_config.save()
        fuzzy_property = FuzzyProperties(domain=cls.domain, case_type='case', properties=['a', 'b', 'c'])
        fuzzy_property.save()
        ignore_patterns = IgnorePatterns(domain=cls.domain, case_type='case', case_property='a', regex='+')
        ignore_patterns.save()
        cls.search_config.fuzzy_properties.add(fuzzy_property)
        cls.search_config.ignore_patterns.add(ignore_patterns)

    @classmethod
    def tearDownClass(cls):
        CaseSearchConfig.objects.all().delete()
        super(BaseLinkedCaseClaimTest, cls).tearDownClass()


class TestLinkedCaseClaim(BaseLinkedCaseClaimTest):
    def test_link_enables_case_search(self):
        existing_search_config = CaseSearchConfig(domain=self.domain_link.linked_domain, enabled=False)
        existing_search_config.save()
        fuzzy_property = FuzzyProperties(domain=self.domain_link.linked_domain, case_type='case',
                                         properties=['a', 'b', 'd'])
        fuzzy_property.save()
        existing_search_config.fuzzy_properties.add(fuzzy_property)
        update_case_search_config(self.domain_link)
        search_config = (CaseSearchConfig.objects
                         .prefetch_related('fuzzy_properties')
                         .get(domain=self.domain_link.linked_domain))

        self.assertTrue(search_config.enabled)

        # overwrites the existing fuzzy properties settings
        self.assertEqual(1, search_config.fuzzy_properties.count())
        self.assertEqual(['a', 'b', 'c'], search_config.fuzzy_properties.all()[0].properties)

        self.assertNotEqual(search_config.pk, self.search_config.pk)

    def test_query_addition(self):
        name = 'test query addition'
        addition = {'test': 'addition'}
        self.query_addition = CaseSearchQueryAddition(
            domain=self.domain,
            name=name,
            query_addition=addition,
        )
        self.query_addition.save()

        update_case_search_config(self.domain_link)
        query_addition = CaseSearchQueryAddition.objects.get(domain=self.domain_link.linked_domain)
        self.assertEqual(name, query_addition.name)
        self.assertEqual(addition, query_addition.query_addition)
        self.assertNotEqual(query_addition.pk, self.query_addition.pk)


class TestRemoteLinkedCaseClaim(BaseLinkedCaseClaimTest):

    @classmethod
    def setUpClass(cls):
        super(TestRemoteLinkedCaseClaim, cls).setUpClass()
        cls.domain_obj = create_domain(cls.domain)
        cls.couch_user = WebUser.create(cls.domain, "test", "foobar")
        cls.django_user = cls.couch_user.get_django_user()
        cls.api_key, _ = ApiKey.objects.get_or_create(user=cls.django_user)
        cls.auth_headers = {'HTTP_AUTHORIZATION': 'apikey test:%s' % cls.api_key.key}
        cls.domain_link.save()

    @classmethod
    def tearDownClass(cls):
        cls.couch_user.delete()
        cls.api_key.delete()
        super(TestRemoteLinkedCaseClaim, cls).tearDownClass()
        cls.domain_obj.delete()  # deleting the domain before other things causes failures

    @patch('corehq.apps.linked_domain.updates.remote_get_case_search_config')
    def test_remote_linked_app(self, fake_case_search_config_getter):
        url = reverse('linked_domain:case_search_config', args=[self.domain])
        headers = self.auth_headers.copy()
        headers[REMOTE_REQUESTER_HEADER] = self.domain_link.linked_domain
        resp = self.client.get(url, **headers)

        fake_case_search_config_getter.return_value = json.loads(resp.content)

        update_case_search_config(self.domain_link)
        new_search_config = (CaseSearchConfig.objects
                         .prefetch_related('fuzzy_properties')
                         .get(domain=self.domain_link.linked_domain))

        self.assertTrue(new_search_config.enabled)
        self.assertEqual(
            set(new_search_config.fuzzy_properties.all()[0].properties),
            set(self.search_config.fuzzy_properties.all()[0].properties)
        )
