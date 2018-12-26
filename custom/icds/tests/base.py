from __future__ import absolute_import
from __future__ import unicode_literals
import uuid
from casexml.apps.case.mock import CaseBlock
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.form_processor.backends.sql.dbaccessors import CaseAccessorSQL
from corehq.form_processor.tests.utils import use_sql_backend
from django.test import TestCase
from xml.etree import cElementTree as ElementTree


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
        case = submit_case_blocks(ElementTree.tostring(caseblock.as_xml()).decode('utf-8'), cls.domain)[1][0]
        cls.created_case_ids.append(case.case_id)
        return case

    @classmethod
    def create_basic_related_cases(cls, owner_id=None):
        cls.mother_person_case = cls.create_case(
            'person',
            update={'language_code': 'en'},
            case_name="Sam",
            owner_id=owner_id,
        )
        cls.migrated_mother_person_case = cls.create_case(
            'person',
            update={'migration_status': 'migrated', 'language_code': 'en'},
            case_name="Eva",
            owner_id=owner_id,
        )
        cls.opted_out_mother_person_case = cls.create_case(
            'person',
            update={'registered_status': 'not_registered', 'language_code': 'en'},
            case_name="Kara",
            owner_id=owner_id,
        )
        cls.child_person_case = cls.create_case(
            'person',
            parent_case_id=cls.mother_person_case.case_id,
            parent_identifier='mother',
            parent_relationship='child',
            case_name="Joe",
            owner_id=owner_id,
        )
        cls.child_health_case = cls.create_case(
            'child_health',
            parent_case_id=cls.child_person_case.case_id,
            parent_identifier='parent',
            parent_relationship='extension',
            owner_id=owner_id,
        )
        cls.child_tasks_case = cls.create_case(
            'tasks',
            parent_case_id=cls.child_health_case.case_id,
            parent_identifier='parent',
            parent_relationship='extension',
            update={'tasks_type': 'child'},
            owner_id=owner_id,
        )
        cls.ccs_record_case = cls.create_case(
            'ccs_record',
            parent_case_id=cls.mother_person_case.case_id,
            parent_case_type=cls.mother_person_case.type,
            parent_identifier='parent',
            parent_relationship='child',
            owner_id=owner_id,
        )
        cls.migrated_mother_ccs_record_case = cls.create_case(
            'ccs_record',
            parent_case_id=cls.migrated_mother_person_case.case_id,
            parent_case_type=cls.migrated_mother_person_case.type,
            parent_identifier='parent',
            parent_relationship='child',
            owner_id=owner_id,
        )
        cls.opted_out_mother_ccs_record_case = cls.create_case(
            'ccs_record',
            parent_case_id=cls.opted_out_mother_person_case.case_id,
            parent_case_type=cls.opted_out_mother_person_case.type,
            parent_identifier='parent',
            parent_relationship='child',
            owner_id=owner_id,
        )
        cls.mother_tasks_case = cls.create_case(
            'tasks',
            parent_case_id=cls.ccs_record_case.case_id,
            parent_case_type=cls.ccs_record_case.type,
            parent_identifier='parent',
            parent_relationship='extension',
            update={'tasks_type': 'pregnancy'},
            owner_id=owner_id,
        )
        cls.lone_child_person_case = cls.create_case(
            'person',
            owner_id=owner_id,
        )
        cls.lone_child_health_case = cls.create_case(
            'child_health',
            owner_id=owner_id,
        )
        cls.lone_child_tasks_case = cls.create_case(
            'tasks',
            update={'tasks_type': 'child'},
            owner_id=owner_id,
        )
        cls.lone_ccs_record_case = cls.create_case(
            'ccs_record',
            owner_id=owner_id,
        )
        cls.lone_mother_tasks_case = cls.create_case(
            'tasks',
            update={'tasks_type': 'pregnancy'},
            owner_id=owner_id,
        )
