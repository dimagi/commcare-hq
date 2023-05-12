from uuid import uuid4

from django.test import TestCase

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.es import case_adapter, case_search_adapter
from corehq.apps.es.tests.utils import es_test
from corehq.apps.locations.models import LocationType, SQLLocation
from corehq.form_processor.models import CommCareCase
from corehq.form_processor.tests.utils import create_case

from ..es import AttendeeSearchES, get_paginated_attendees
from ..models import LOCATION_IDS_CASE_PROPERTY, get_attendee_case_type
from ...case_search.models import CaseSearchConfig

DOMAIN = 'test-domain'


@es_test(requires=[case_search_adapter], setup_class=True)
class TestAttendeeLocationFilter(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain_obj = create_domain(DOMAIN)
        cls.config = CaseSearchConfig.objects.create(
            domain=DOMAIN,
            enabled=True,
        )

        cls.country = LocationType.objects.create(
            domain=DOMAIN,
            name='Country',
        )
        cls.city = LocationType.objects.create(
            domain=DOMAIN,
            name='City',
            parent_type=cls.country,
        )
        cls.suriname = SQLLocation.objects.create(
            domain=DOMAIN,
            name='Suriname',
            location_id=str(uuid4()),
            location_type=cls.country,
        )
        cls.paramaribo = SQLLocation.objects.create(
            domain=DOMAIN,
            name='Paramaribo',
            location_id=str(uuid4()),
            location_type=cls.city,
            parent=cls.suriname,
        )

        case_type = get_attendee_case_type(DOMAIN)
        cls.country_attendee = create_case(
            DOMAIN,
            case_id=uuid4().hex,
            case_type=case_type,
            name='Countryboy',
            case_json={
                LOCATION_IDS_CASE_PROPERTY: cls.suriname.location_id,
            },
            save=True,
        )
        cls.city_attendee = create_case(
            DOMAIN,
            case_id=uuid4().hex,
            case_type=case_type,
            name='Citygirl',
            case_json={
                LOCATION_IDS_CASE_PROPERTY: cls.paramaribo.location_id,
            },
            save=True,
        )
        cls.both_attendee = create_case(
            DOMAIN,
            case_id=uuid4().hex,
            case_type=case_type,
            name='Everywhereguy',
            case_json={
                LOCATION_IDS_CASE_PROPERTY: ' '.join((
                    cls.suriname.location_id,
                    cls.paramaribo.location_id,
                ))
            },
            save=True,
        )
        case_search_adapter.bulk_index([
            cls.country_attendee,
            cls.city_attendee,
            cls.both_attendee,
        ], refresh=True)

    @classmethod
    def tearDownClass(cls):
        CommCareCase.objects.hard_delete_cases(DOMAIN, [
            cls.city_attendee.case_id,
            cls.country_attendee.case_id,
        ])
        cls.paramaribo.delete()
        cls.suriname.delete()
        cls.city.delete()
        cls.country.delete()
        cls.config.delete()
        cls.domain_obj.delete()
        super().tearDownClass()

    def test_parent_location(self):
        case_ids = (
            AttendeeSearchES()
            .attendee_location_filter(self.suriname.location_id)
            .get_ids()
        )
        self.assertEqual(set(case_ids), {
            self.country_attendee.case_id,
            self.both_attendee.case_id,
        })

    def test_child_location(self):
        case_ids = (
            AttendeeSearchES()
            .attendee_location_filter(self.paramaribo.location_id)
            .get_ids()
        )
        self.assertEqual(set(case_ids), {
            self.city_attendee.case_id,
            self.both_attendee.case_id,
        })

    def test_location_ids_list(self):
        location_ids = [
            self.suriname.location_id,
            self.paramaribo.location_id,
        ]
        case_ids = (
            AttendeeSearchES()
            .attendee_location_filter(location_ids)
            .get_ids()
        )
        self.assertEqual(set(case_ids), {
            self.country_attendee.case_id,
            self.city_attendee.case_id,
            self.both_attendee.case_id,
        })

    def test_location_ids_str(self):
        location_ids = ' '.join((
            self.suriname.location_id,
            self.paramaribo.location_id,
        ))
        case_ids = (
            AttendeeSearchES()
            .attendee_location_filter(location_ids)
            .get_ids()
        )
        self.assertEqual(set(case_ids), {
            self.country_attendee.case_id,
            self.city_attendee.case_id,
            self.both_attendee.case_id,
        })

    def test_no_location_ids(self):
        case_ids = (
            AttendeeSearchES()
            .attendee_location_filter('')
            .get_ids()
        )
        self.assertEqual(case_ids, [])


@es_test(requires=[case_adapter], setup_class=True)
class TestGetPaginatedAttendees(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        case_type = get_attendee_case_type(DOMAIN)
        cls.alice = create_case(
            DOMAIN,
            case_id=uuid4().hex,
            case_type=case_type,
            name='Alice',
            save=True,
        )
        cls.bob = create_case(
            DOMAIN,
            case_id=uuid4().hex,
            case_type=case_type,
            name='Bob',
            save=True,
        )
        case_adapter.bulk_index([cls.alice, cls.bob], refresh=True)

    @classmethod
    def tearDownClass(cls):
        CommCareCase.objects.hard_delete_cases(DOMAIN, [
            cls.alice.case_id,
            cls.bob.case_id,
        ])
        super().tearDownClass()

    def test_page_1(self):
        cases, total = get_paginated_attendees(DOMAIN, limit=1, page=1)
        self.assertEqual(total, 2)
        self.assertEqual(cases, [self.alice])

    def test_page_2(self):
        cases, total = get_paginated_attendees(DOMAIN, limit=1, page=2)
        self.assertEqual(total, 2)
        self.assertEqual(cases, [self.bob])

    def test_page_0(self):
        with self.assertRaises(AssertionError):
            get_paginated_attendees(DOMAIN, limit=1, page=0)

    def test_limit_0(self):
        with self.assertRaises(AssertionError):
            get_paginated_attendees(DOMAIN, limit=0, page=1)

    def test_all(self):
        cases, total = get_paginated_attendees(DOMAIN, limit=5, page=1)
        self.assertEqual(total, 2)
        self.assertEqual(cases, [self.alice, self.bob])

    def test_query(self):
        cases, total = get_paginated_attendees(DOMAIN, limit=5, page=1,
                                               query='alice')
        self.assertEqual(total, 1)
        self.assertEqual(cases, [self.alice])
