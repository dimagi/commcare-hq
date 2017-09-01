import uuid
from casexml.apps.case.mock import CaseBlock
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.form_processor.backends.sql.dbaccessors import CaseAccessorSQL
from corehq.form_processor.tests.utils import use_sql_backend
from django.test import TestCase
from xml.etree import ElementTree


@use_sql_backend
class BaseICDSTest(TestCase):
    domain = 'base-icds-test'

    @classmethod
    def setUpClass(cls):
        super(BaseICDSTest, cls).setUpClass()
        cls.domain_obj = create_domain(cls.domain)
        cls.created_case_ids = []

    @classmethod
    def tearDownClass(cls):
        CaseAccessorSQL.hard_delete_cases(
            cls.domain,
            cls.created_case_ids
        )
        cls.domain_obj.delete()
        super(BaseICDSTest, cls).tearDownClass()

    @classmethod
    def create_case(cls, case_type, parent_case_id=None, parent_case_type=None, parent_identifier=None,
            parent_relationship=None):

        kwargs = {}
        if parent_case_id:
            kwargs['index'] = {parent_identifier: (parent_case_type, parent_case_id, parent_relationship)}

        caseblock = CaseBlock(
            uuid.uuid4().hex,
            case_type=case_type,
            create=True,
            **kwargs
        )
        case = submit_case_blocks(ElementTree.tostring(caseblock.as_xml()), cls.domain)[1][0]
        cls.created_case_ids.append(case.case_id)
        return case
