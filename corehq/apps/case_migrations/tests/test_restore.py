from __future__ import absolute_import
from __future__ import unicode_literals
import uuid
from django.test import TestCase
from casexml.apps.case.mock import CaseFactory, CaseStructure, CaseIndex
from casexml.apps.case.const import CASE_INDEX_CHILD

from ..views import get_related_case_ids


class TestRelatedCases(TestCase):
    domain = 'related-cases-domain'

    @classmethod
    def setUpClass(cls):
        super(TestRelatedCases, cls).setUpClass()
        cls.factory = CaseFactory(domain=cls.domain)

        cls.greatgranddad = cls._case_structure('Ymir', None, 'granddad')
        cls.granddad = cls._case_structure('Laufey', cls.greatgranddad, 'granddad')
        cls.dad = cls._case_structure('Loki', cls.granddad, 'dad')
        cls.kid = cls._case_structure('Sleipner', cls.dad, 'kid')
        cls.kid2 = cls._case_structure('Jormungandr', cls.dad, 'kid')
        cls.grandkid = cls._case_structure('Svadilfari', cls.kid, 'kid')

        cls.other_granddad = cls._case_structure('Odin', None, 'granddad')
        cls.other_dad = cls._case_structure('Thor', cls.other_granddad, 'dad')

        cls.factory.create_or_update_cases([cls.grandkid, cls.kid2, cls.other_dad])

    @staticmethod
    def _case_structure(name, parent, case_type):
        if parent:
            indices = [CaseIndex(
                parent,
                identifier='parent',
                relationship=CASE_INDEX_CHILD,
                related_type=parent.attrs['case_type'],
            )]
        else:
            indices = []
        return CaseStructure(
            case_id=uuid.uuid4().hex,
            attrs={
                "case_type": case_type,
                "create": True,
                "update": {"name": name},
            },
            indices=indices,
            walk_related=True,
        )

    def test_get_related_case_ids(self):
        related_ids = get_related_case_ids(self.domain, self.dad.case_id)
        self.assertItemsEqual(
            related_ids,
            [self.greatgranddad.case_id, self.granddad.case_id,
             self.dad.case_id, self.kid.case_id, self.kid2.case_id,
             self.grandkid.case_id]
        )
