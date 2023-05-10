import doctest
from uuid import uuid4

from django.test import TestCase

from corehq.apps.es import case_adapter
from corehq.apps.es.tests.utils import es_test
from corehq.form_processor.models import CommCareCase
from corehq.form_processor.tests.utils import create_case

from ..es import get_paginated_attendees
from ..models import get_attendee_case_type

DOMAIN = 'test-domain'


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
        cases, total = get_paginated_attendees(DOMAIN, limit=1, page=0)
        self.assertEqual(total, 2)
        self.assertEqual(cases, [self.alice])

    def test_limit_0(self):
        cases, total = get_paginated_attendees(DOMAIN, limit=0, page=1)
        self.assertEqual(total, 2)
        self.assertEqual(cases, [])

    def test_all(self):
        cases, total = get_paginated_attendees(DOMAIN, limit=5, page=1)
        self.assertEqual(total, 2)
        self.assertEqual(cases, [self.alice, self.bob])

    def test_query(self):
        cases, total = get_paginated_attendees(DOMAIN, limit=5, page=1,
                                               query='alice')
        self.assertEqual(total, 1)
        self.assertEqual(cases, [self.alice])


def test_doctests():
    import corehq.apps.events.es as module
    results = doctest.testmod(module, optionflags=doctest.ELLIPSIS)
    assert results.failed == 0
