from django.test import TestCase
from casexml.apps.case.models import CommCareCase
from casexml.apps.case.util import post_case_blocks
from casexml.apps.case.xml import V2
from casexml.apps.case.tests.util import CaseBlock
import uuid

class CaseRebuildTest(TestCase):

    def setUp(self):
        for item in CommCareCase.view("case/by_user", include_docs=True, reduce=False).all():
            item.delete()


    def testBasicRebuild(self):
        case_id = _post_util(create=True)
        _post_util(case_id=case_id, p1='p1-1', p2='p2-1')
        _post_util(case_id=case_id, p2='p2-2', p3='p3-2')

        # check initial state
        case = CommCareCase.get(case_id)
        self.assertEqual(case.p1, 'p1-1') # original
        self.assertEqual(case.p2, 'p2-2') # updated
        self.assertEqual(case.p3, 'p3-2') # new
        self.assertEqual(3, len(case.actions)) # create + 2 updates
        a1 = case.actions[1]
        self.assertEqual(a1.updated_unknown_properties['p1'], 'p1-1')
        self.assertEqual(a1.updated_unknown_properties['p2'], 'p2-1')
        a2 = case.actions[2]
        self.assertEqual(a2.updated_unknown_properties['p2'], 'p2-2')
        self.assertEqual(a2.updated_unknown_properties['p3'], 'p3-2')

        # rebuild by flipping the actions
        case.actions = [case.actions[0], a2, a1]
        case.rebuild()
        self.assertEqual(case.p1, 'p1-1') # original
        self.assertEqual(case.p2, 'p2-1') # updated (back!)
        self.assertEqual(case.p3, 'p3-2') # new

DEFAULT_TYPE = 'test'

def _post_util(create=False, case_id=None, user_id=None, owner_id=None,
               case_type=None, version=V2, **kwargs):

    uid = lambda: uuid.uuid4().hex 
    case_id = case_id or uid()
    block = CaseBlock(create=create,
                      case_id=case_id,
                      user_id=user_id or uid(),
                      owner_id=owner_id or uid(),
                      case_type=case_type or DEFAULT_TYPE,
                      version=version,
                      update=kwargs).as_xml()
    post_case_blocks([block])
    return case_id
    