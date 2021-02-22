import uuid
from datetime import datetime

from django.test import TestCase

from casexml.apps.case.mock import CaseBlock, IndexAttrs

from corehq.apps.domain.shortcuts import create_domain
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.util.test_utils import create_and_save_a_case

from ..api.core import serialize_case
from ..utils import submit_case_blocks


class TestAPISerialization(TestCase):
    domain = 'test-update-cases'
    maxDiff = None

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain_obj = create_domain(cls.domain)
        cls.case_accessor = CaseAccessors(cls.domain)

        cls.parent_case_id = str(uuid.uuid4())
        case_id = str(uuid.uuid4())
        xform, cases = submit_case_blocks([
            CaseBlock(
                case_id=cls.parent_case_id,
                case_type='player',
                case_name='Elizabeth Harmon',
                external_id='1',
                owner_id='methuen_home',
                create=True,
                update={
                    'sport': 'chess',
                    'rank': '1600',
                    'dob': '1948-11-02',
                }
            ).as_text(),
            CaseBlock(
                case_id=case_id,
                case_type='match',
                case_name='Harmon/Luchenko',
                owner_id='harmon',
                external_id='14',
                create=True,
                update={'winner': 'Harmon'},
                index={
                    'parent': IndexAttrs(case_type='player', case_id=cls.parent_case_id, relationship='child')
                },
            ).as_text()
        ], domain=cls.domain)

        cls.case = cls.case_accessor.get_case(case_id)
        cls.case.opened_on = datetime(2021, 2, 18, 10, 59)
        cls.case.modified_on = datetime(2021, 2, 18, 10, 59)
        cls.case.server_modified_on = datetime(2021, 2, 18, 10, 59)

    @classmethod
    def tearDownClass(cls):
        cls.domain_obj.delete()
        super().tearDownClass()

    def test_serialization(self):
        self.assertEqual(
            serialize_case(self.case),
            {
                "domain": self.domain,
                "@case_id": self.case.case_id,
                "@case_type": "match",
                "case_name": "Harmon/Luchenko",
                "external_id": "14",
                "@owner_id": "harmon",
                "date_opened": "2021-02-18T10:59:00",
                "last_modified": "2021-02-18T10:59:00",
                "server_last_modified": "2021-02-18T10:59:00",
                "closed": False,
                "date_closed": None,
                "properties": {
                    "winner": "Harmon",
                },
                "indices": {
                    "parent": {
                        "case_id": self.parent_case_id,
                        "@case_type": "player",
                        "@relationship": "child",
                    }
                }
            }
        )
