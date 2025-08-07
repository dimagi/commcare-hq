import uuid
import pytest
from casexml.apps.case.mock import CaseFactory
from django.contrib.auth.models import User
from django.test import TestCase

from corehq.apps.data_cleaning.models import (
    BulkEditChange,
    BulkEditRecord,
    BulkEditSession,
    EditActionType,
)
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.models import WebUser
from corehq.form_processor.tests.utils import FormProcessorTestUtils


class BulkEditChangeTest(TestCase):
    domain = 'planet'
    case_type = 'island'

    def setUp(self):
        factory = CaseFactory(domain=self.domain)
        self.case = factory.create_case(
            case_type=self.case_type,
            owner_id='q123',
            case_name='Vieques',
            update={
                'nearest_ocean': 'atlantic',
                'town': 'Isabel Segunda',
                'favorite_beach': 'Playa Bastimento',
                'art': '\n  :)   \n  \t',
                'second_favorite_beach': 'no idea',
                'friend': 'Brittney \t\nClaasen',
            },
        )

        super().setUp()

    def tearDown(self):
        FormProcessorTestUtils.delete_all_cases()
        super().tearDown()

    def test_replace(self):
        change = BulkEditChange(
            prop_id='town',
            action_type=EditActionType.REPLACE,
            replace_string='Esperanza',
        )
        assert change.edited_value(self.case) == 'Esperanza'
        assert change.edited_value(
            self.case,
            edited_properties={
                'town': 'Segunda',
            }
        ) == 'Esperanza'

    def test_replace_none(self):
        change = BulkEditChange(
            prop_id='unset',
            action_type=EditActionType.REPLACE,
            replace_string='Esperanza',
        )
        assert change.edited_value(self.case) == 'Esperanza'

    def test_find_replace(self):
        change = BulkEditChange(
            prop_id='favorite_beach',
            action_type=EditActionType.FIND_REPLACE,
            find_string='Playa',
            replace_string='Punta',
        )
        assert change.edited_value(self.case) == 'Punta Bastimento'
        assert change.edited_value(
            self.case,
            edited_properties={
                'favorite_beach': 'Bastimento Playa',
            }
        ) == 'Bastimento Punta'

    def test_find_replace_none(self):
        change = BulkEditChange(
            prop_id='unset',
            action_type=EditActionType.FIND_REPLACE,
            find_string='Playa',
            replace_string='Punta',
        )
        assert change.edited_value(self.case) is None

    def test_find_replace_regex(self):
        change = BulkEditChange(
            prop_id='friend',
            action_type=EditActionType.FIND_REPLACE,
            use_regex=True,
            find_string='(\\s)+',
            replace_string=' ',
        )
        assert change.edited_value(self.case) == 'Brittney Claasen'
        assert change.edited_value(
            self.case,
            edited_properties={
                'friend': 'brittney \t\nclaasen',
            },
        ) == 'brittney claasen'

    def test_find_replace_regex_none(self):
        change = BulkEditChange(
            prop_id='unset',
            action_type=EditActionType.FIND_REPLACE,
            use_regex=True,
            find_string='(\\s)+',
            replace_string=' ',
        )
        assert change.edited_value(self.case) is None

    def test_strip(self):
        change = BulkEditChange(
            prop_id='art',
            action_type=EditActionType.STRIP,
        )
        assert change.edited_value(self.case) == ':)'
        assert change.edited_value(
            self.case,
            edited_properties={
                'art': '    :-)\t\n  ',
            },
        ) == ':-)'

    def test_strip_none(self):
        change = BulkEditChange(
            prop_id='unset',
            action_type=EditActionType.STRIP,
        )
        assert change.edited_value(self.case) is None

    def test_copy_replace(self):
        change = BulkEditChange(
            prop_id='nearest_ocean',
            action_type=EditActionType.COPY_REPLACE,
            copy_from_prop_id='favorite_beach',
        )
        assert change.edited_value(self.case) == 'Playa Bastimento'
        assert change.edited_value(
            self.case,
            edited_properties={
                'favorite_beach': 'playa bastimento',
                'nearest_ocean': 'Atlantic',
            },
        ) == 'playa bastimento'

    def test_copy_replace_none(self):
        change = BulkEditChange(
            prop_id='unset',
            action_type=EditActionType.COPY_REPLACE,
            copy_from_prop_id='favorite_beach',
        )
        assert change.edited_value(self.case) == 'Playa Bastimento'

    def test_title_case(self):
        change = BulkEditChange(
            prop_id='nearest_ocean',
            action_type=EditActionType.TITLE_CASE,
        )
        assert change.edited_value(self.case) == 'Atlantic'
        assert change.edited_value(
            self.case,
            edited_properties={
                'nearest_ocean': 'atlantic  ',
            },
        ) == 'Atlantic  '

    def test_title_case_none(self):
        change = BulkEditChange(
            prop_id='unset',
            action_type=EditActionType.TITLE_CASE,
        )
        assert change.edited_value(self.case) is None

    def test_upper_case(self):
        change = BulkEditChange(
            prop_id='town',
            action_type=EditActionType.UPPER_CASE,
        )
        assert change.edited_value(self.case) == 'ISABEL SEGUNDA'
        assert change.edited_value(
            self.case,
            edited_properties={
                'town': 'isbel',
            },
        ) == 'ISBEL'

    def test_upper_case_none(self):
        change = BulkEditChange(
            prop_id='unset',
            action_type=EditActionType.UPPER_CASE,
        )
        assert change.edited_value(self.case) is None

    def test_lower_case(self):
        change = BulkEditChange(
            prop_id='town',
            action_type=EditActionType.LOWER_CASE,
        )
        assert change.edited_value(self.case) == 'isabel segunda'
        assert change.edited_value(
            self.case,
            edited_properties={
                'town': 'SEGUNDA',
            },
        ) == 'segunda'

    def test_lower_case_none(self):
        change = BulkEditChange(
            prop_id='unset',
            action_type=EditActionType.LOWER_CASE,
        )
        assert change.edited_value(self.case) is None

    def test_make_empty(self):
        change = BulkEditChange(
            prop_id='nearest_ocean',
            action_type=EditActionType.MAKE_EMPTY,
        )
        assert change.edited_value(self.case) == ''
        assert change.edited_value(
            self.case,
            edited_properties={
                'nearest_ocean': 'pacific',
            },
        ) == ''

    def test_empty_none(self):
        change = BulkEditChange(
            prop_id='unset',
            action_type=EditActionType.MAKE_EMPTY,
        )
        assert change.edited_value(self.case) == ''

    def test_make_null(self):
        change = BulkEditChange(
            prop_id='nearest_ocean',
            action_type=EditActionType.MAKE_NULL,
        )
        assert change.edited_value(self.case) is None
        assert change.edited_value(
            self.case,
            edited_properties={
                'nearest_ocean': 'pacific',
            },
        ) is None

    def test_make_null_none(self):
        change = BulkEditChange(
            prop_id='unset',
            action_type=EditActionType.MAKE_NULL,
        )
        assert change.edited_value(self.case) is None

    def test_reset(self):
        change = BulkEditChange(
            prop_id='nearest_ocean',
            action_type=EditActionType.RESET,
        )
        assert change.edited_value(self.case) == 'atlantic'
        assert change.edited_value(
            self.case,
            edited_properties={
                'nearest_ocean': 'pacific',
            },
        ) == 'atlantic'

    def test_reset_none(self):
        change = BulkEditChange(
            prop_id='unset',
            action_type=EditActionType.RESET,
        )
        assert change.edited_value(self.case) is None


class BulkEditRecordChangesTest(TestCase):
    domain_name = 'forest'
    case_type = 'plant'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain = create_domain(cls.domain_name)
        cls.addClassCleanup(cls.domain.delete)

        cls.web_user = WebUser.create(cls.domain.name, 'leaf@treeeeees.com', 'testpwd', None, None)
        cls.user = User.objects.get(username=cls.web_user.username)
        cls.addClassCleanup(cls.web_user.delete, cls.domain.name, deleted_by=None)

    def setUp(self):
        super().setUp()
        self.session = BulkEditSession.objects.new_case_session(self.user, self.domain_name, self.case_type)
        factory = CaseFactory(domain=self.domain_name)
        self.case = factory.create_case(
            case_type=self.case_type,
            owner_id='s124',
            case_name='WILD  \nRYE  ',
            update={
                'pot_type': 'terra Cotta',
                'friend': ' \tfearful \tBEAN',
                'light_level': '  LOW   \n',
            },
        )
        self.case_two = factory.create_case(
            case_type=self.case_type,
            owner_id='s123',
            case_name='  Zesty flora\n',
            update={
                'pot_type': 'terra Cotta',
                'friend': 'sugar  \n  wormWood  ',
                'light_level': 'full_sun',
            },
        )

    def tearDown(self):
        FormProcessorTestUtils.delete_all_cases()
        super().tearDown()

    def test_initial_has_no_property_updates_or_changes(self):
        record = BulkEditRecord.objects.create(
            session=self.session,
            doc_id=self.case.case_id,
        )
        assert not record.has_property_updates
        assert record.get_edited_case_properties(self.case) == {}

    def test_single_change_to_record(self):
        record = BulkEditRecord.objects.create(
            session=self.session,
            doc_id=self.case.case_id,
        )
        change = BulkEditChange.objects.create(
            session=self.session,
            prop_id='pot_type',
            action_type=EditActionType.MAKE_NULL,
        )
        change.records.add(record)
        assert record.has_property_updates
        edited_props = record.get_edited_case_properties(self.case)
        assert edited_props == {'pot_type': None}
        assert record.calculated_change_id == change.change_id
        assert record.calculated_properties == edited_props
        assert not record.has_property_updates

    def test_multiple_changes_and_views_to_record(self):
        record = BulkEditRecord.objects.create(
            session=self.session,
            doc_id=self.case.case_id,
        )
        change_one = BulkEditChange.objects.create(
            session=self.session,
            prop_id='name',
            action_type=EditActionType.STRIP,
        )
        change_one.records.add(record)
        change_two = BulkEditChange.objects.create(
            session=self.session,
            prop_id='pot_type',
            action_type=EditActionType.TITLE_CASE,
        )
        change_two.records.add(record)

        # simulating the first view of the case in the table:
        assert record.has_property_updates
        edited_props = record.get_edited_case_properties(self.case)
        assert edited_props == {'name': 'WILD  \nRYE', 'pot_type': 'Terra Cotta'}
        assert record.calculated_change_id == change_two.change_id
        assert record.calculated_properties == edited_props

        change_three = BulkEditChange.objects.create(
            session=self.session,
            prop_id='name',
            action_type=EditActionType.FIND_REPLACE,
            use_regex=True,
            find_string='(\\s)+',
            replace_string=' ',
        )
        change_three.records.add(record)

        # simulating the second view of the case in the table:
        assert record.has_property_updates
        edited_props_two = record.get_edited_case_properties(self.case)
        assert edited_props_two == {'name': 'WILD RYE', 'pot_type': 'Terra Cotta'}
        assert record.calculated_change_id == change_three.change_id
        assert record.calculated_properties == edited_props_two

    def test_changes_to_multiple_records(self):
        record_one = BulkEditRecord.objects.create(
            session=self.session,
            doc_id=self.case.case_id,
        )
        record_two = BulkEditRecord.objects.create(
            session=self.session,
            doc_id=self.case_two.case_id,
        )
        change_one = BulkEditChange.objects.create(
            session=self.session,
            prop_id='name',
            action_type=EditActionType.STRIP,
        )
        change_one.records.add(record_one, record_two)
        change_two = BulkEditChange.objects.create(
            session=self.session,
            prop_id='name',
            action_type=EditActionType.TITLE_CASE,
        )
        change_two.records.add(record_one)
        edited_props_one = record_one.get_edited_case_properties(self.case)
        assert record_one.calculated_change_id == change_two.change_id
        assert edited_props_one == {'name': 'Wild  \nRye'}
        edited_props_two = record_two.get_edited_case_properties(self.case_two)
        assert record_two.calculated_change_id == change_one.change_id
        assert edited_props_two == {'name': 'Zesty flora'}

    def test_get_edited_case_properties_with_other_case(self):
        record = BulkEditRecord.objects.create(
            session=self.session,
            doc_id=self.case.case_id,
        )
        change = BulkEditChange.objects.create(
            session=self.session,
            prop_id='name',
            action_type=EditActionType.LOWER_CASE,
        )
        change.records.add(record)
        with pytest.raises(ValueError, match="case.case_id doesn't match record.doc_id"):
            record.get_edited_case_properties(self.case_two)


class BulkEditChangeManagerTests(TestCase):
    domain_name = 'forest'
    case_type = 'plant'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain = create_domain(cls.domain_name)
        cls.addClassCleanup(cls.domain.delete)

        cls.web_user = WebUser.create(cls.domain.name, 'tester@datacleaning.org', 'testpwd', None, None)
        cls.django_user = User.objects.get(username=cls.web_user.username)
        cls.addClassCleanup(cls.web_user.delete, cls.domain.name, deleted_by=None)

    def setUp(self):
        super().setUp()
        self.session = BulkEditSession.objects.new_case_session(self.django_user, self.domain_name, self.case_type)

    def test_apply_inline_edit(self):
        doc_id = str(uuid.uuid4())
        record = BulkEditRecord.objects.create(
            session=self.session,
            doc_id=doc_id,
        )
        change = record.changes.last()
        assert change is None
        self.session.changes.apply_inline_edit(
            record=record,
            prop_id='town',
            value='Esperanza',
        )
        change = record.changes.last()
        assert change.prop_id == 'town'
        assert change.action_type == EditActionType.REPLACE
        assert change.replace_string == 'Esperanza'

    def test_apply_reset(self):
        doc_id = str(uuid.uuid4())
        record = BulkEditRecord.objects.create(
            session=self.session,
            doc_id=doc_id,
        )
        self.session.changes.apply_inline_edit(
            record=record,
            prop_id='town',
            value='Esperanza',
        )
        self.session.changes.apply_reset(
            record=record,
            prop_id='town',
        )
        change = record.changes.last()
        assert change.prop_id == 'town'
        assert change.action_type == EditActionType.RESET
