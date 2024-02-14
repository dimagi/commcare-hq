import json

from django.contrib.auth.models import User
from django.test import TestCase

from corehq.apps.dump_reload.sql.load import SqlDataLoader
from corehq.apps.users.models import SQLUserData
from corehq.apps.users.models_role import Permission, RolePermission, UserRole
from corehq.form_processor.models.cases import CaseTransaction
from corehq.form_processor.models.forms import XFormOperation
from corehq.form_processor.models.ledgers import LedgerTransaction
from corehq.form_processor.tests.utils import create_case, create_form_for_test


class TestSqlDataLoader(TestCase):

    def test_loading_foreign_keys_using_iterable_natural_key(self):
        user = User.objects.create(username='testuser')
        model = {
            "model": "users.sqluserdata",
            "fields": {
                "domain": "test",
                "user_id": "testuser",
                "django_user": ["testuser"],
                "modified_on": "2024-01-01T12:00:00.000000Z",
                "profile": None,
                "data": {"test": "1"},
            },
        }
        serialized_model = json.dumps(model)

        SqlDataLoader().load_objects([serialized_model])

        user_data = SQLUserData.objects.get(django_user=user)
        self.assertEqual(user_data.django_user.pk, user.pk)

    def test_loading_foreign_keys_using_non_iterable_natural_key(self):
        # create_case will create a CaseTransaction too so test verifies the serialized one is saved properly
        cc_case = create_case('test', case_id='abc123', save=True)
        model = {
            "model": "form_processor.casetransaction",
            "fields": {
                "case": "abc123",
                "form_id": "fk-test",
                "sync_log_id": None,
                "server_date": "2024-01-01T12:00:00.000000Z",
                "_client_date": None,
                "type": 1,
                "revoked": False,
                "details": {},
            },
        }
        serialized_model = json.dumps(model)

        SqlDataLoader().load_objects([serialized_model])

        transaction = CaseTransaction.objects.partitioned_query('abc123').get(case=cc_case, form_id='fk-test')
        self.assertEqual(transaction.case_id, 'abc123')

    def test_loading_foreign_keys_using_primary_key(self):
        role = UserRole.objects.create(domain='test', name='test-role')
        permission = Permission.objects.create(value='test')
        model = {
            "model": "users.rolepermission",
            "pk": 1,
            "fields": {"role": role.pk, "permission_fk": permission.pk, "allow_all": True, "allowed_items": []},
        }
        serialized_model = json.dumps(model)

        SqlDataLoader().load_objects([serialized_model])

        role_permission = RolePermission.objects.get(role=role, permission_fk=permission)
        self.assertEqual(role_permission.pk, 1)


class TestLoadingNonUniqueNaturalKeys(TestCase):
    """
    The models tested below have ``natural_key`` methods that do not guarantee a unique value. This means we need
    to avoid using ``get_by_natural_key`` on these models because if implemented, Django's deserializer will try
    to save an object using an existing primary key/inserted object.
    """

    def test_loading_conflicting_case_transactions_saves_distinct_objects_to_db(self):
        cc_case = create_case("test", case_id="abc123", save=True)
        model = {
            "model": "form_processor.casetransaction",
            "fields": {
                "case": cc_case.case_id,
                "form_id": None,
                "type": 16,
                "server_date": "2019-11-07T09:10:12.318008Z",
            }
        }
        serialized_models = [json.dumps(model) for _ in range(2)]

        SqlDataLoader().load_objects(serialized_models)

        self.assertEqual(
            CaseTransaction.objects.partitioned_query(cc_case.case_id).filter(
                case=cc_case.case_id,
                form_id=None,
                type=16
            ).count(),
            2,
        )

    def test_loading_conflicting_xform_operations_saves_distinct_objects_to_db(self):
        xform = create_form_for_test("test", form_id="abc123", save=True)
        model = {
            "model": "form_processor.xformoperationsql",
            "fields": {
                "form": xform.form_id,
                "user_id": 'conflicting-user-id',
                "date": "2019-11-07T09:10:12.318008Z",
                "operation": "test",
            }
        }
        serialized_models = [json.dumps(model) for _ in range(2)]

        SqlDataLoader().load_objects(serialized_models)

        self.assertEqual(
            XFormOperation.objects.partitioned_query(xform.form_id).filter(
                form=xform.form_id,
                user_id="conflicting-user-id"
            ).count(),
            2,
        )

    def test_loading_conflicting_ledger_transactions_saves_distinct_objects_to_db(self):
        cc_case = create_case("test", case_id="abc123", save=True)
        xform = create_form_for_test("test", form_id="abc123", save=True)
        model = {
            "model": "form_processor.ledgertransaction",
            "fields": {
                "case": cc_case.case_id,
                "form_id": xform.form_id,
                "section_id": "conflicting-section-id",
                "entry_id": "conflicting-entry-id",
                "server_date": "2019-11-07T09:10:12.318008Z",
                "report_date": "2019-11-07T09:10:12.318008Z",
                "type": 1,
            }
        }
        serialized_models = [json.dumps(model) for _ in range(2)]

        SqlDataLoader().load_objects(serialized_models)

        self.assertEqual(
            LedgerTransaction.objects.partitioned_query(cc_case.case_id).filter(
                case=cc_case.case_id,
                form_id=xform.form_id,
                section_id="conflicting-section-id",
                entry_id="conflicting-entry-id"
            ).count(),
            2,
        )
