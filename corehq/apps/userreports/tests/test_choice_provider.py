from abc import ABCMeta, abstractmethod
from django.test import SimpleTestCase
from corehq.apps.reports_core.filters import Choice
from corehq.apps.userreports.models import ReportConfiguration
from corehq.apps.userreports.reports.filters.choice_providers import ChoiceProvider, \
    ChoiceQueryContext, LocationChoiceProvider, UserChoiceProvider, GroupChoiceProvider, \
    OwnerChoiceProvider


class StaticChoiceProvider(ChoiceProvider):

    def __init__(self, choices):
        self.choices = choices
        super(StaticChoiceProvider, self).__init__(None, None)

    def query(self, query_context):
        filtered_set = [choice for choice in self.choices
                        if query_context.query in choice.display]
        return filtered_set[query_context.offset:query_context.offset + query_context.limit]

    def get_choices_for_known_values(self, values):
        return [choice for choice in self.choices
                if choice.value in values]


class StaticChoiceProviderTest(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        cls.choice_provider = StaticChoiceProvider([Choice('1', 'One'), Choice('2', 'Two'), Choice('3', 'Three')])

    def test_query_no_search(self):
        self.assertEqual(self.choice_provider.query(ChoiceQueryContext('', 2, page=0)),
                         [Choice('1', 'One'), Choice('2', 'Two')])
        self.assertEqual(self.choice_provider.query(ChoiceQueryContext('', 2, page=1)),
                         [Choice('3', 'Three')])

    def test_get_choices_for_values(self):
        self.assertEqual(
            set(self.choice_provider.get_choices_for_values(['2', '4', '6'])),
            {Choice('2', 'Two'), Choice('4', '4'), Choice('6', '6')}
        )


class ChoiceProviderTestMixin(object):
    __metaclass__ = ABCMeta
    choice_provider = None
    static_choice_provider = None

    def _test_query(self, query_context):
        self.assertEqual(
            self.choice_provider.query(query_context),
            self.static_choice_provider.query(query_context))

    def _test_get_choices_for_values(self, values):
        self.assertEqual(
            set(self.choice_provider.get_choices_for_values(values)),
            set(self.static_choice_provider.get_choices_for_values(values))
        )

    def test_query_no_search_first_short_page(self):
        self._test_query(ChoiceQueryContext('', 2, page=0))

    def test_query_no_search_second_short_page(self):
        self._test_query(ChoiceQueryContext('', 2, page=1))

    @abstractmethod
    def test_query_search(self):
        """
        Suggested implementation:

            self._test_query(ChoiceQueryContext('relevant_search_term', 2, page=1))

        """
        pass

    @abstractmethod
    def test_get_choices_for_values(self):
        """
        Suggested implementation:

            self._test_get_choices_for_values(
                [irrelevant_value, relevant_value, relevant_value])
        """
        pass


class LocationChoiceProviderTest(SimpleTestCase, ChoiceProviderTestMixin):
    @classmethod
    def setUpClass(cls):
        cls.domain = 'location-choice-provider'
        report = ReportConfiguration(domain=cls.domain)
        cls.choice_provider = LocationChoiceProvider(report, None)
        cls.static_choice_provider = StaticChoiceProvider([])

    def test_query_search(self):
        pass

    def test_get_choices_for_values(self):
        pass


class UserChoiceProviderTest(SimpleTestCase, ChoiceProviderTestMixin):
    @classmethod
    def setUpClass(cls):
        cls.domain = 'user-choice-provider'
        report = ReportConfiguration(domain=cls.domain)
        cls.choice_provider = UserChoiceProvider(report, None)
        cls.static_choice_provider = StaticChoiceProvider([])

    def test_query_search(self):
        pass

    def test_get_choices_for_values(self):
        pass


class GroupChoiceProviderTest(SimpleTestCase, ChoiceProviderTestMixin):
    @classmethod
    def setUpClass(cls):
        cls.domain = 'group-choice-provider'
        report = ReportConfiguration(domain=cls.domain)
        cls.choice_provider = GroupChoiceProvider(report, None)
        cls.static_choice_provider = StaticChoiceProvider([])

    def test_query_search(self):
        pass

    def test_get_choices_for_values(self):
        pass


class OwnerChoiceProviderTest(SimpleTestCase, ChoiceProviderTestMixin):
    @classmethod
    def setUpClass(cls):
        cls.domain = 'owner-choice-provider'
        report = ReportConfiguration(domain=cls.domain)
        cls.choice_provider = OwnerChoiceProvider(report, None)
        cls.static_choice_provider = StaticChoiceProvider([])

    def test_query_search(self):
        pass

    def test_get_choices_for_values(self):
        pass
