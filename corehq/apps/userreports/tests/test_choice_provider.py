from abc import ABCMeta, abstractmethod
from django.test import SimpleTestCase
import mock
from functools import partial

from corehq.apps.locations.tests.util import LocationHierarchyTestCase
from corehq.apps.es.fake.groups_fake import GroupESFake
from corehq.apps.es.fake.users_fake import UserESFake
from corehq.apps.groups.models import Group
from corehq.apps.locations.tests.util import delete_all_locations
from corehq.apps.users.dbaccessors.all_commcare_users import delete_all_users
from corehq.apps.reports_core.filters import Choice
from corehq.apps.userreports.models import ReportConfiguration
from corehq.apps.userreports.reports.filters.choice_providers import (
    ChoiceQueryContext, LocationChoiceProvider, UserChoiceProvider, GroupChoiceProvider,
    OwnerChoiceProvider, StaticChoiceProvider, SearchableChoice)
from corehq.apps.users.models import CommCareUser, WebUser, DomainMembership
from corehq.apps.users.util import normalize_username


class StaticChoiceProviderTest(SimpleTestCase):

    @classmethod
    def setUpClass(cls):
        super(StaticChoiceProviderTest, cls).setUpClass()
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
    choice_query_context = ChoiceQueryContext

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
        self._test_query(self.choice_query_context('', limit=20, page=0))

    def test_query_no_search_first_short_page(self):
        self._test_query(self.choice_query_context('', 2, page=0))

    def test_query_no_search_second_short_page(self):
        self._test_query(self.choice_query_context('', 2, page=1))

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


class LocationChoiceProviderTest(ChoiceProviderTestMixin, LocationHierarchyTestCase):
    domain = 'location-choice-provider'
    location_type_names = ['state', 'county', 'city']
    location_structure = [
        ('Massachusetts', [
            ('Middlesex', [
                ('Cambridge', []),
                ('Somerville', []),
            ]),
            ('Suffolke', [      # Make all locations contain the letter 'e'
                ('Bostone', []),
            ])
        ])
    ]

    @classmethod
    def setUpClass(cls):
        delete_all_locations()
        delete_all_users()
        super(LocationChoiceProviderTest, cls).setUpClass()
        report = ReportConfiguration(domain=cls.domain)
        choice_tuples = [
            (location.name, SearchableChoice(
                location.location_id,
                location.get_path_display(),
                searchable_text=[location.site_code, location.name]
            ))
            for location in cls.locations.itervalues()
        ]
        choice_tuples.sort()
        choices = [choice for name, choice in choice_tuples]
        cls.web_user = WebUser.create(cls.domain, 'blah', 'password')
        cls.choice_provider = LocationChoiceProvider(report, None)
        cls.choice_provider.configure({
            "include_descendants": False,
            "show_full_path": True,
        })
        cls.static_choice_provider = StaticChoiceProvider(choices)
        cls.choice_query_context = partial(ChoiceQueryContext, user=cls.web_user)

    @classmethod
    def tearDownClass(cls):
        cls.domain_obj.delete()
        delete_all_locations()

    def test_query_search(self):
        # Searching for something common to all locations gets you all locations
        self._test_query(self.choice_query_context('e', page=0))
        self._test_query(self.choice_query_context('e', page=1))

    def test_get_choices_for_values(self):
        self._test_get_choices_for_values(
            ['made-up', self.locations['Cambridge'].location_id, self.locations['Middlesex'].location_id])

    def test_scoped_to_location_search(self):
        self.web_user.set_location(self.domain, self.locations['Middlesex'])
        self.restrict_user_to_assigned_locations(self.web_user)
        scoped_choices = [
            SearchableChoice(
                location.location_id,
                location.get_path_display(),
                searchable_text=[location.site_code, location.name]
            )
            for location in [
                self.locations['Cambridge'],
                self.locations['Middlesex'],
                self.locations['Somerville'],
            ]
        ]
        self.static_choice_provider = StaticChoiceProvider(scoped_choices)

        # When an empty query is given, the user receives all the choices they can access
        self._test_query(self.choice_query_context('', page=0))
        # Searching for something common to all locations give only the accessible locations
        self._test_query(self.choice_query_context('e', page=0))
        # When a user queries for something they can access, it gets returned
        self._test_query(self.choice_query_context('Somerville', page=0))
        # When a user searches for something they can't access, it isn't returned
        self._test_query(self.choice_query_context('Boston', page=0))


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
        doc = user._doc
        doc['username.exact'] = doc['username']
        doc['base_username'] = username
        UserESFake.save_doc(doc)
        return user

    @classmethod
    def make_web_user(cls, email, domain=None):
        domain = domain or cls.domain
        domains = [domain]
        user = WebUser(username=email, domains=domains)
        user.domain_memberships = [DomainMembership(domain=cls.domain)]
        doc = user._doc
        doc['username.exact'] = doc['username']
        doc['base_username'] = email
        UserESFake.save_doc(doc)
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
class OwnerChoiceProviderTest(LocationHierarchyTestCase, ChoiceProviderTestMixin):
    domain = 'owner-choice-provider'
    location_type_names = ['state']
    location_structure = [('Massachusetts', [])]

    @classmethod
    def setUpClass(cls):
        super(OwnerChoiceProviderTest, cls).setUpClass()
        report = ReportConfiguration(domain=cls.domain)
        cls.group = GroupChoiceProviderTest.make_group('Group', domain=cls.domain)
        cls.mobile_worker = UserChoiceProviderTest.make_mobile_worker('mobile-worker', domain=cls.domain)
        cls.web_user = UserChoiceProviderTest.make_web_user('web-user@example.com', domain=cls.domain)
        cls.location = cls.locations['Massachusetts']
        cls.docs = [cls.group, cls.mobile_worker, cls.web_user, cls.location]
        cls.choices = [
            SearchableChoice(cls.group.get_id, cls.group.name, [cls.group.name]),
            SearchableChoice(cls.mobile_worker.get_id, cls.mobile_worker.raw_username,
                             [cls.mobile_worker.username]),
            SearchableChoice(cls.web_user.get_id, cls.web_user.username,
                             [cls.web_user.username]),
            SearchableChoice(cls.location.location_id, cls.location.display_name,
                             [cls.location.name, cls.location.site_code]),
        ]
        cls.choice_provider = OwnerChoiceProvider(report, None)
        cls.static_choice_provider = StaticChoiceProvider(cls.choices)
        cls.choice_query_context = partial(ChoiceQueryContext, user=cls.mobile_worker)

    @classmethod
    def tearDownClass(cls):
        UserESFake.reset_docs()
        GroupESFake.reset_docs()
        cls.domain_obj.delete()
        delete_all_locations()

    def test_query_search(self):
        self._test_query(self.choice_query_context('o', limit=10, offset=0))
        self._test_query(self.choice_query_context('l', limit=10, offset=0))
        self._test_query(self.choice_query_context('no-match', limit=10, offset=0))
        self._test_query(self.choice_query_context('o', limit=3, offset=2))

    def test_get_choices_for_values(self):
        self._test_get_choices_for_values(
            ['unknown', self.group._id, self.web_user._id, self.location.location_id,
             self.mobile_worker._id])
