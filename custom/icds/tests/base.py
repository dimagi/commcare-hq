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
            parent_relationship=None, update=None, case_name=None, owner_id=None):

        kwargs = {}
        if parent_case_id:
            kwargs['index'] = {parent_identifier: (parent_case_type, parent_case_id, parent_relationship)}

        if case_name:
            kwargs['case_name'] = case_name

        if owner_id:
            kwargs['owner_id'] = owner_id

        caseblock = CaseBlock(
            uuid.uuid4().hex,
            case_type=case_type,
            create=True,
            update=update,
            **kwargs
        )
        case = submit_case_blocks(ElementTree.tostring(caseblock.as_xml()), cls.domain)[1][0]
        cls.created_case_ids.append(case.case_id)
        return case

    @classmethod
    def create_basic_related_cases(cls):
        cls.mother_person_case = cls.create_case('person')
        cls.child_person_case = cls.create_case(
            'person',
            parent_case_id=cls.mother_person_case.case_id,
            parent_identifier='mother',
            parent_relationship='child'
        )
        cls.child_health_case = cls.create_case(
            'child_health',
            parent_case_id=cls.child_person_case.case_id,
            parent_identifier='parent',
            parent_relationship='extension'
        )
        cls.child_tasks_case = cls.create_case(
            'tasks',
            parent_case_id=cls.child_health_case.case_id,
            parent_identifier='parent',
            parent_relationship='extension',
            update={'tasks_type': 'child'},
        )
        cls.ccs_record_case = cls.create_case(
            'ccs_record',
            parent_case_id=cls.mother_person_case.case_id,
            parent_case_type=cls.mother_person_case.type,
            parent_identifier='parent',
            parent_relationship='child'
        )
        cls.mother_tasks_case = cls.create_case(
            'tasks',
            parent_case_id=cls.ccs_record_case.case_id,
            parent_case_type=cls.ccs_record_case.type,
            parent_identifier='parent',
            parent_relationship='extension',
            update={'tasks_type': 'pregnancy'},
        )
        cls.lone_child_person_case = cls.create_case('person')
        cls.lone_child_health_case = cls.create_case('child_health')
        cls.lone_child_tasks_case = cls.create_case('tasks', update={'tasks_type': 'child'})
        cls.lone_ccs_record_case = cls.create_case('ccs_record')
        cls.lone_mother_tasks_case = cls.create_case('tasks', update={'tasks_type': 'pregnancy'})
