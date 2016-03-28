from abc import ABCMeta, abstractmethod
from django.test import SimpleTestCase, TestCase
import mock
from corehq.apps.commtrack.tests.util import bootstrap_location_types, make_loc
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.es.fake.groups_fake import GroupESFake
from corehq.apps.es.fake.users_fake import UserESFake
from corehq.apps.groups.models import Group
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
        """
        choices must be passed in in desired sort order
        """
        self.choices = [
            choice if isinstance(choice, SearchableChoice)
            else SearchableChoice(
                choice.value, choice.display,
                searchable_text=[choice.display]
            )
            for choice in choices
        ]
        super(StaticChoiceProvider, self).__init__(None, None)

    def query(self, query_context):
        filtered_set = [choice for choice in self.choices
                        if any(query_context.query in text for text in choice.searchable_text)]
        return filtered_set[query_context.offset:query_context.offset + query_context.limit]

    def get_choices_for_known_values(self, values):
        return {choice for choice in self.choices
                if choice.value in values}


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
    """
    A mixin for a creating uniform tests for different ChoiceProvider subclasses.

    ChoiceProviderTestMixin creates a simple framework in which the real choice provider
    being tested gets compared to a static choice provider (one that simply filters,
    sorts, and slices Choice objects in memory), and verifies they produce the same result.

    Classes that want to use this framework must

    1. subclass TestCase/SimpleTestCase and ChoiceProviderTestMixin
    2. Initialize `choice_provider` and the data it requires in setUpClass
    3. Initialize `static_choice_provider` with Choices (or SearchableChoices)
       that correspond to the data set up in part (2) in setUpClass
    4. Implement the abstract test methods according to the suggestions in the docstrings

    """
    __metaclass__ = ABCMeta
    choice_provider = None
    static_choice_provider = None

    def _test_query(self, query_context):
        self.assertEqual(
            self.choice_provider.query(query_context),
            self.static_choice_provider.query(query_context))

    def _test_get_choices_for_values(self, values):
        self.assertEqual(
            self.choice_provider.get_choices_for_values(values),
            self.static_choice_provider.get_choices_for_values(values),
        )

    def test_query_no_search_all(self):
        self._test_query(ChoiceQueryContext('', limit=20, page=0))

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
    domain = 'location-choice-provider'

    @classmethod
    def make_location(cls, location_code, location_name, domain=None):
        domain = domain or cls.domain
        return make_loc(location_code, location_name, type='outlet', domain=domain)

    @classmethod
    def setUpClass(cls):
        cls.domain_obj = create_domain(cls.domain)
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
            location = cls.make_location(location_code, location_name)
            cls.locations.append(location)
            choices.append(SearchableChoice(location.location_id, location.sql_location.display_name,
                                            searchable_text=[location_code, location_name]))
        choices.sort(key=lambda choice: choice.display)
        cls.choice_provider = LocationChoiceProvider(report, None)
        cls.static_choice_provider = StaticChoiceProvider(choices)

    @classmethod
    def tearDownClass(cls):
        cls.domain_obj.delete()
        delete_all_locations()

    def test_query_search(self):
        self._test_query(ChoiceQueryContext('e', 2, page=0))
        self._test_query(ChoiceQueryContext('e', 2, page=1))

    def test_get_choices_for_values(self):
        self._test_get_choices_for_values(
            ['made-up', self.locations[0].location_id, self.locations[1].location_id])


@mock.patch('corehq.apps.users.analytics.UserES', UserESFake)
@mock.patch('corehq.apps.userreports.reports.filters.choice_providers.UserES', UserESFake)
class UserChoiceProviderTest(SimpleTestCase, ChoiceProviderTestMixin):
    domain = 'user-choice-provider'

    @classmethod
    def make_mobile_worker(cls, username, domain=None):
        domain = domain or cls.domain
        user = CommCareUser(username=normalize_username(username, domain),
                            domain=domain)
        user.domain_membership = DomainMembership(domain=domain)
        UserESFake.save_doc(user._doc)
        return user

    @classmethod
    def make_web_user(cls, email, domain=None):
        domain = domain or cls.domain
        domains = [domain]
        user = WebUser(username=email, domains=domains)
        user.domain_memberships = [DomainMembership(domain=cls.domain)]
        UserESFake.save_doc(user._doc)
        return user

    @classmethod
    def setUpClass(cls):
        report = ReportConfiguration(domain=cls.domain)

        cls.users = [
            cls.make_mobile_worker('bernice'),
            cls.make_web_user('candice@example.com'),
            cls.make_mobile_worker('dennis'),
            cls.make_mobile_worker('elizabeth'),
            cls.make_mobile_worker('albert'),
            # test that docs in other domains are filtered out
            cls.make_mobile_worker('aaa', domain='some-other-domain'),
        ]
        choices = [
            SearchableChoice(
                user.get_id, user.raw_username,
                searchable_text=[user.username, user.last_name, user.first_name])
            for user in cls.users if user.is_member_of(cls.domain)
        ]
        choices.sort(key=lambda choice: choice.display)
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


@mock.patch('corehq.apps.userreports.reports.filters.choice_providers.GroupES', GroupESFake)
class GroupChoiceProviderTest(SimpleTestCase, ChoiceProviderTestMixin):
    domain = 'group-choice-provider'

    @classmethod
    def make_group(cls, name, domain=None):
        domain = domain or cls.domain
        group = Group(name=name, domain=domain, case_sharing=True)
        GroupESFake.save_doc(group._doc)
        return group

    @classmethod
    def setUpClass(cls):
        report = ReportConfiguration(domain=cls.domain)

        cls.groups = [
            cls.make_group('Team B no'),
            cls.make_group('Team C no'),
            cls.make_group('Team D', domain='not-this-domain'),
            cls.make_group('Team E yes'),
            cls.make_group('Team A yes'),
        ]
        choices = [
            SearchableChoice(group.get_id, group.name, searchable_text=[group.name])
            for group in cls.groups if group.domain == cls.domain]
        choices.sort(key=lambda choice: choice.display)
        cls.choice_provider = GroupChoiceProvider(report, None)
        cls.static_choice_provider = StaticChoiceProvider(choices)

    @classmethod
    def tearDownClass(cls):
        GroupESFake.reset_docs()

    def test_query_search(self):
        self._test_query(ChoiceQueryContext('yes', limit=10, page=0))

    def test_get_choices_for_values(self):
        self._test_get_choices_for_values(
            ['unknown-group'] + [group.get_id for group in self.groups])


@mock.patch('corehq.apps.users.analytics.UserES', UserESFake)
@mock.patch('corehq.apps.userreports.reports.filters.choice_providers.UserES', UserESFake)
@mock.patch('corehq.apps.userreports.reports.filters.choice_providers.GroupES', GroupESFake)
class OwnerChoiceProviderTest(TestCase, ChoiceProviderTestMixin):
    dependent_apps = [
        'corehq.apps.commtrack', 'corehq.apps.locations', 'corehq.apps.products',
        'custom.logistics', 'custom.ilsgateway', 'custom.ewsghana', 'corehq.couchapps'
    ]
    domain = 'owner-choice-provider'

    @classmethod
    def setUpClass(cls):
        cls.domain_obj = create_domain(cls.domain)
        report = ReportConfiguration(domain=cls.domain)
        cls.group = GroupChoiceProviderTest.make_group('Group', domain=cls.domain)
        cls.mobile_worker = UserChoiceProviderTest.make_mobile_worker('mobile-worker', domain=cls.domain)
        cls.web_user = UserChoiceProviderTest.make_web_user('web-user@example.com', domain=cls.domain)
        cls.location = LocationChoiceProviderTest.make_location('location', 'Location', domain=cls.domain)
        cls.docs = [cls.group, cls.mobile_worker, cls.web_user, cls.location]
        cls.choices = [
            SearchableChoice(cls.group.get_id, cls.group.name, [cls.group.name]),
            SearchableChoice(cls.mobile_worker.get_id, cls.mobile_worker.raw_username,
                             [cls.mobile_worker.username]),
            SearchableChoice(cls.web_user.get_id, cls.web_user.username,
                             [cls.web_user.username]),
            SearchableChoice(cls.location.location_id, cls.location.sql_location.display_name,
                             [cls.location.name, cls.location.site_code]),
        ]
        cls.choice_provider = OwnerChoiceProvider(report, None)
        cls.static_choice_provider = StaticChoiceProvider(cls.choices)

    @classmethod
    def tearDownClass(cls):
        UserESFake.reset_docs()
        GroupESFake.reset_docs()
        cls.domain_obj.delete()
        delete_all_locations()

    def test_query_search(self):
        self._test_query(ChoiceQueryContext('o', limit=10, offset=0))
        self._test_query(ChoiceQueryContext('l', limit=10, offset=0))
        self._test_query(ChoiceQueryContext('no-match', limit=10, offset=0))
        self._test_query(ChoiceQueryContext('o', limit=3, offset=2))

    def test_get_choices_for_values(self):
        self._test_get_choices_for_values(
            ['unknown', self.group._id, self.web_user._id, self.location.location_id,
             self.mobile_worker._id])
