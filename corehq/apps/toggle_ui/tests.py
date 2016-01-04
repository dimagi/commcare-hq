import uuid
from django.test import TestCase
from corehq.apps.toggle_ui.migration_helpers import move_toggles
from couchdbkit import ResourceNotFound
from toggle.models import Toggle


class MigrationHelperTest(TestCase):

    @staticmethod
    def _delete_toggles(self, *toggles):
        for toggle in toggles:
            try:
                Toggle.get(toggle).delete()
            except ResourceNotFound:
                pass

    def test_move_nonexistent_source(self):
        dsa = uuid.uuid4().hex
        try:
            Toggle(slug=dsa, enabled_users=['kieran']).save()
            move_toggles('missing-src', dsa)
            self.assertEqual(['kieran'], Toggle.get(dsa).enabled_users)
        finally:
            MigrationHelperTest._delete_toggles(dsa)

    def test_move_nonexistent_destination(self):
        moz, dsa = [uuid.uuid4().hex for i in range(2)]
        try:
            Toggle(slug=moz, enabled_users=['claire']).save()
            move_toggles(moz, dsa)
            dsa_toggle = Toggle.get(dsa)
            self.assertEqual(['claire'], dsa_toggle.enabled_users)
            with self.assertRaises(ResourceNotFound):
                Toggle.get(moz)
        finally:
            MigrationHelperTest._delete_toggles(moz, dsa)

    def test_move(self):
        moz, dsa = [uuid.uuid4().hex for i in range(2)]
        try:
            moz_users = ['marco', 'lauren', 'claire']
            dsa_users = ['kieran', 'jolani', 'claire']
            Toggle(slug=moz, enabled_users=moz_users).save()
            Toggle(slug=dsa, enabled_users=dsa_users).save()
            move_toggles(moz, dsa)
            # ensure original is delted
            with self.assertRaises(ResourceNotFound):
                Toggle.get(moz)
            dsa_toggle = Toggle.get(dsa)
            expected_users = set(moz_users) | set(dsa_users)
            self.assertEqual(len(expected_users), len(dsa_toggle.enabled_users))
            self.assertEqual(expected_users, set(dsa_toggle.enabled_users))
        finally:
            MigrationHelperTest._delete_toggles(moz, dsa)
