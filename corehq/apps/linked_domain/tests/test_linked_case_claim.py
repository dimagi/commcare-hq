from __future__ import absolute_import, unicode_literals

from corehq.apps.case_search.models import (
    CaseSearchConfig,
    CaseSearchQueryAddition,
    FuzzyProperties,
    IgnorePatterns,
)
from corehq.apps.linked_domain.updates import update_case_search_config
from corehq.apps.linked_domain.tests.test_linked_apps import BaseLinkedAppsTest


class TestLinkedCaseClaim(BaseLinkedAppsTest):

    @classmethod
    def setUpClass(cls):
        super(TestLinkedCaseClaim, cls).setUpClass()
        cls.search_config = CaseSearchConfig(domain=cls.domain, enabled=True)
        cls.search_config.save()
        fuzzy_property = FuzzyProperties(domain=cls.domain, case_type='case', properties=['a', 'b', 'c'])
        fuzzy_property.save()
        ignore_patterns = IgnorePatterns(domain=cls.domain, case_type='case', case_property='a', regex='+')
        ignore_patterns.save()
        cls.search_config.fuzzy_properties.add(fuzzy_property)
        cls.search_config.ignore_patterns.add(ignore_patterns)

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
