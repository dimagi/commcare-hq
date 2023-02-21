from django.test import TestCase
from corehq.apps.events.utils import create_case_with_case_type


class TestEventUtils(TestCase):

    domain = 'test-domain'

    @classmethod
    def setUpClass(cls):
        super(TestEventUtils, cls).setUpClass()
        cls.created_cases = []

    @classmethod
    def tearDownClass(cls):
        for case_ in cls.created_cases:
            case_.delete()
        super(TestEventUtils, cls).tearDownClass()

    def test_create_case_with_case_type(self):
        case_ = create_case_with_case_type(
            case_type='muggle',
            case_args={
                'domain': self.domain,
                'properties': {'knows_the_function_of_a_rubber_duck': 'yes'}
            }
        )
        self.created_cases.append(case_)
        self.assertEqual(case_.type, 'muggle')
        self.assertEqual(case_.get_case_property('knows_the_function_of_a_rubber_duck'), 'yes')

    def test_create_case_with_case_type_with_index(self):
        parent_case = create_case_with_case_type(
            case_type='wizard',
            case_args={
                'domain': self.domain,
                'properties': {'knows_the_function_of_a_rubber_duck': 'no'},
            }
        )
        self.created_cases.append(parent_case)

        case_ = create_case_with_case_type(
            case_type='wizard',
            case_args={
                'domain': self.domain,
                'properties': {'plays_quidditch': 'yes'},
            },
            index={
                'parent_case_id': parent_case.case_id,
            }
        )
        self.created_cases.append(case_)

        extension_case = parent_case.get_subcases()[0]
        self.assertEqual(extension_case.type, 'wizard')
        self.assertEqual(extension_case.get_case_property('plays_quidditch'), 'yes')
