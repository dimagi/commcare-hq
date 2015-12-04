from abc import ABCMeta, abstractmethod
from django.test import SimpleTestCase, TestCase
import mock
from corehq.apps.commtrack.tests.util import bootstrap_location_types, make_loc
from corehq.apps.es.fake.users_fake import UserESFake
from corehq.apps.locations.tests import delete_all_locations
from corehq.apps.reports_core.filters import Choice
from corehq.apps.userreports.models import ReportConfiguration
from corehq.apps.userreports.reports.filters.choice_providers import ChoiceProvider, \
    ChoiceQueryContext, LocationChoiceProvider, UserChoiceProvider, GroupChoiceProvider, \
    OwnerChoiceProvider
from corehq.apps.users.models import CommCareUser, WebUser, DomainMembership
from corehq.apps.users.util import normalize_username


class SearchableChoice(Choice):
    def __new__(cls, value, display, searchable_text=None):
        self = super(SearchableChoice, cls).__new__(cls, value, display)
        self.searchable_text = [text for text in searchable_text or []
                                if text is not None]
        return self


class StaticChoiceProvider(ChoiceProvider):

    def __init__(self, choices):
        self.choices = [
            choice if isinstance(choice, SearchableChoice)
            else SearchableChoice(
                choice.value, choice.display,
                searchable_text=[choice.display]
            )
            for choice in choices
        ]
        self.choices.sort(key=lambda choice: choice.display)
        super(StaticChoiceProvider, self).__init__(None, None)

    def query(self, query_context):
        filtered_set = [choice for choice in self.choices
                        if any(query_context.query in text for text in choice.searchable_text)]
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


class LocationChoiceProviderTest(TestCase, ChoiceProviderTestMixin):
    dependent_apps = [
        'corehq.apps.commtrack', 'corehq.apps.locations', 'corehq.apps.products',
        'custom.logistics', 'custom.ilsgateway', 'custom.ewsghana', 'corehq.couchapps'
    ]

    @classmethod
    def setUpClass(cls):
        cls.domain = 'location-choice-provider'
        report = ReportConfiguration(domain=cls.domain)
        bootstrap_location_types(cls.domain)

        location_code_name_pairs = (
            ('cambridge_ma', 'Cambridge'),
            ('somerville_ma', 'Somerville'),
            ('boston_ma', 'Boston'),
        )
        cls.locations = []
        choices = []

        for location_code, location_name in location_code_name_pairs:
            location = make_loc(location_code, location_name, type='outlet', domain=cls.domain)
            cls.locations.append(location)
            choices.append(SearchableChoice(location.location_id, location.sql_location.display_name,
                                            searchable_text=[location_code, location_name]))

        cls.choice_provider = LocationChoiceProvider(report, None)
        cls.static_choice_provider = StaticChoiceProvider(choices)

    @classmethod
    def tearDownClass(cls):
        delete_all_locations()

    def test_query_search(self):
        self._test_query(ChoiceQueryContext('e', 2, page=0))
        self._test_query(ChoiceQueryContext('e', 2, page=1))

    def test_get_choices_for_values(self):
        self._test_get_choices_for_values(
            ['made-up', self.locations[0].location_id, self.locations[1].location_id])


@mock.patch('corehq.apps.es.UserES', UserESFake)
class UserChoiceProviderTest(SimpleTestCase, ChoiceProviderTestMixin):
    @classmethod
    def setUpClass(cls):
        cls.domain = 'user-choice-provider'
        report = ReportConfiguration(domain=cls.domain)

        def make_mobile_worker(username, domain=cls.domain):
            user = CommCareUser(username=normalize_username(username, domain),
                                domain=domain)
            user.domain_membership = DomainMembership(domain=domain)
            UserESFake.save_doc(user._doc)
            return user

        def make_web_user(email):
            user = WebUser(username=email, domains=[cls.domain])
            user.domain_memberships = [DomainMembership(domain=cls.domain)]
            UserESFake.save_doc(user._doc)
            return user

        cls.users = [
            make_mobile_worker('bernice'),
            make_mobile_worker('dennis'),
            make_mobile_worker('elizabeth'),
            make_web_user('candice@example.com'),
            make_mobile_worker('albert'),
            # test that docs in other domains are filtered out
            make_mobile_worker('aaa', domain='some-other-domain'),
        ]
        choices = [
            SearchableChoice(
                user.get_id, user.raw_username,
                searchable_text=[user.username, user.last_name, user.first_name])
            for user in cls.users if user.is_member_of(cls.domain)
        ]
        cls.choice_provider = UserChoiceProvider(report, None)
        cls.static_choice_provider = StaticChoiceProvider(choices)

    @classmethod
    def tearDownClass(cls):
        UserESFake.reset_docs()

    def test_query_search(self):
        self._test_query(ChoiceQueryContext(query='ni', limit=10, page=0))

    def test_get_choices_for_values(self):
        self._test_get_choices_for_values(
            ['unknown-user'] + [user._id for user in self.users])


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
