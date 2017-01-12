from django.test.testcases import SimpleTestCase
from django.test.utils import override_settings

from corehq.form_processor.exceptions import AccessRestricted
from corehq.form_processor.models import XFormInstanceSQL, XFormOperationSQL, CommCareCaseSQL, \
    CaseTransaction, XFormAttachmentSQL, CommCareCaseIndexSQL, CaseAttachmentSQL
from corehq.util.test_utils import generate_cases

DOMAIN = 'test-form-accessor'


@override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
class RestrictedSQLAccessTests(SimpleTestCase):
    pass


# @generate_cases([
#     (XFormInstanceSQL,),
#     (XFormOperationSQL,),
#     (XFormAttachmentSQL,),
#     (CommCareCaseSQL,),
#     (CommCareCaseIndexSQL,),
#     (CaseAttachmentSQL,),
#     (CaseTransaction,),
# ], RestrictedSQLAccessTests)
# def test_restricted_direct_access(self, ModelClass):
#     with self.assertRaises(AccessRestricted):
#         ModelClass().save()
#
#     with self.assertRaises(AccessRestricted):
#         ModelClass().save_base()
#
#     with self.assertRaises(AccessRestricted):
#         ModelClass().delete()
#
#
# @generate_cases([
#     (XFormInstanceSQL,),
#     (XFormOperationSQL,),
#     (XFormAttachmentSQL,),
#     (CommCareCaseSQL,),
#     (CommCareCaseIndexSQL,),
#     (CaseAttachmentSQL,),
#     (CaseTransaction,),
# ], RestrictedSQLAccessTests)
# def test_restricted_query(self, ModelClass):
#     with self.assertRaises(AccessRestricted):
#         ModelClass.objects.get(id=1)
#
#     with self.assertRaises(AccessRestricted):
#         ModelClass.objects.filter(field='anything')
#
#     with self.assertRaises(AccessRestricted):
#         ModelClass.objects.create(field='something')
#
#     with self.assertRaises(AccessRestricted):
#         ModelClass.objects.all()
#
#     with self.assertRaises(AccessRestricted):
#         ModelClass.objects.order_by('other thing')
#
#     with self.assertRaises(AccessRestricted):
#         ModelClass.objects.exclude(field='the thing')
