from django.test import SimpleTestCase
from corehq.apps.reports_core.filters import Choice
from corehq.apps.userreports.reports.filters.choice_providers import ChoiceProvider, \
    ChoiceQueryContext


class ChoiceProviderTest(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        class StaticChoiceProvider(ChoiceProvider):
            choices = [Choice('1', 'One'), Choice('2', 'Two'), Choice('3', 'Three')]

            def query(self, query_context):
                filtered_set = [choice for choice in self.choices
                                if query_context.query in choice.display]
                return filtered_set[query_context.offset:query_context.offset + query_context.limit]

            def get_choices_for_known_values(self, values):
                return [choice for choice in self.choices
                        if choice.value in values]

        cls.choice_provider = StaticChoiceProvider(None, None)

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
