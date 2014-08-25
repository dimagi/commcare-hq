from django.test import TestCase
from django.test.utils import override_settings
from casexml.apps.case.models import CommCareCase
from couchdbkit.exceptions import ResourceConflict


@override_settings(CASEXML_FORCE_DOMAIN_CHECK=False)
class ForceSaveTest(TestCase):

    def testForceSave(self):
        original = CommCareCase()
        original.save()
        conflict = CommCareCase.get(original._id)
        original.foo = 'bar'
        conflict.foo = 'not bar'
        original.save()
        try:
            conflict.save()
            self.fail('conflicting save should fail hard!')
        except ResourceConflict:
            pass
        conflict.force_save()
        self.assertEqual('not bar', CommCareCase.get(original._id).foo) 

    def testConflictingIdsFail(self):
        original = CommCareCase()
        original.xform_ids = ['f1', 'f2']
        original.save()
        conflict = CommCareCase.get(original._id)
        original.xform_ids.append('f3')
        original.save()
        for xform_ids in [
            [],
            ['f1'],
            ['f1', 'f2'],
            ['f1', 'f2', 'f4']
        ]:
            conflict.xform_ids = xform_ids 
            try:
                conflict.force_save()
                self.fail('conflicting force save should fail if new forms found!')
            except ResourceConflict:
                pass

        # adding should be ok
        conflict.xform_ids = ['f1', 'f2', 'f3', 'f4']
        conflict.force_save()
