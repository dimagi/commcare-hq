import os
import tempfile
import uuid
from StringIO import StringIO
from django.test import SimpleTestCase, TestCase
from casexml.apps.phone.cache_utils import extract_synclog_id_from_filelike_payload, \
    replace_sync_log_id_in_filelike_payload, copy_payload_and_synclog_and_get_new_file
from casexml.apps.phone.exceptions import SyncLogCachingError
from casexml.apps.phone.models import SimplifiedSyncLog, get_properly_wrapped_sync_log
from casexml.apps.phone.tests.dummy import dummy_restore_xml
from casexml.apps.phone.tests.utils import synclog_id_from_restore_payload
from corehq.form_processor.tests import run_with_all_backends


class CacheUtilsTest(SimpleTestCase):

    def test_extract_restore_id_basic(self):
        restore_id = uuid.uuid4().hex
        fd, path = tempfile.mkstemp()
        restore_payload = dummy_restore_xml(restore_id).strip()
        with os.fdopen(fd, 'wb') as f:
            f.write(restore_payload)

        with open(path, 'r') as f:
            extracted, position = extract_synclog_id_from_filelike_payload(f)
            self.assertEqual(restore_id, extracted)
            self.assertEqual(restore_payload.index(restore_id), position)
            # also make sure we reset the file pointer
            self.assertEqual('<OpenRosaResponse', f.read(17))

    def test_extract_restore_id_not_found(self):
        f = StringIO('not much here')
        with self.assertRaises(SyncLogCachingError):
            extract_synclog_id_from_filelike_payload(f)

    def test_replace_synclog_id(self):
        initial_id = uuid.uuid4().hex
        fd, path = tempfile.mkstemp()
        restore_payload = dummy_restore_xml(initial_id).strip()
        self.assertTrue(_restore_id_block(initial_id) in restore_payload)
        with os.fdopen(fd, 'wb') as f:
            f.write(restore_payload)

        new_id = uuid.uuid4().hex
        with open(path, 'r') as f:
            position = restore_payload.index(initial_id)
            file_reference = replace_sync_log_id_in_filelike_payload(f, initial_id, new_id, position)

        updated_payload = file_reference.file.read()
        self.assertTrue(_restore_id_block(new_id) in updated_payload)
        self.assertFalse(initial_id in updated_payload)
        self.assertEqual(restore_payload, updated_payload.replace(new_id, initial_id))
        self.assertEqual(updated_payload, restore_payload.replace(initial_id, new_id))


class CacheUtilsDbTest(TestCase):

    @run_with_all_backends
    def test_copy_payload(self):
        sync_log = SimplifiedSyncLog(case_ids_on_phone=set(['case-1', 'case-2']))
        sync_log.save()
        payload = dummy_restore_xml(sync_log._id).strip()
        fd, path = tempfile.mkstemp()
        with os.fdopen(fd, 'wb') as f:
            f.write(payload)

        with open(path, 'r') as f:
            updated_fileref = copy_payload_and_synclog_and_get_new_file(f)

        updated_payload = updated_fileref.file.read()
        updated_id = synclog_id_from_restore_payload(updated_payload)
        self.assertNotEqual(sync_log._id, updated_id)
        self.assertTrue(_restore_id_block(updated_id) in updated_payload)
        self.assertFalse(sync_log._id in updated_payload)
        updated_log = get_properly_wrapped_sync_log(updated_id)
        self.assertEqual(updated_log.case_ids_on_phone, sync_log.case_ids_on_phone)


def _restore_id_block(sync_id):
    return '<restore_id>{}</restore_id>'.format(sync_id)
