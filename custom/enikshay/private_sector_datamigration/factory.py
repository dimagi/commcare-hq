from casexml.apps.case.const import CASE_INDEX_EXTENSION
from casexml.apps.case.mock import CaseStructure, CaseIndex

from custom.enikshay.private_sector_datamigration.models import Adherence
from dimagi.utils.decorators.memoized import memoized

PERSON_CASE_TYPE = 'person'
OCCURRENCE_CASE_TYPE = 'occurrence'
EPISODE_CASE_TYPE = 'episode'
ADHERENCE_CASE_TYPE = 'adherence'


class BeneficiaryCaseFactory(object):

    def __init__(self, domain, beneficiary):
        self.domain = domain
        self.beneficiary = beneficiary

    def get_case_structures_to_create(self):
        person_structure = self.get_person_case_structure()
        ocurrence_structure = self.get_occurrence_case_structure(person_structure)
        episode_structure = self.get_episode_case_structure(ocurrence_structure)
        case_structures_to_create = [
            self.get_adherence_case_structure(adherence, episode_structure)
            for adherence in self._adherences
        ]
        return case_structures_to_create or [episode_structure]

    def get_person_case_structure(self):
        kwargs = {
            'attrs': {
                'case_type': PERSON_CASE_TYPE,
                'close': False,
                'create': True,
                'update': {
                }
            }
        }
        return CaseStructure(**kwargs)

    def get_occurrence_case_structure(self, person_structure):
        kwargs = {
            'attrs': {
                'case_type': OCCURRENCE_CASE_TYPE,
                'close': False,
                'create': True,
                'update': {
                    'name': 'Occurrence #1',
                }
            },
            'indices': [CaseIndex(
                person_structure,
                identifier='host',
                relationship=CASE_INDEX_EXTENSION,
                related_type=PERSON_CASE_TYPE,
            )],
        }
        return CaseStructure(**kwargs)

    def get_episode_case_structure(self, occurrence_structure):
        kwargs = {
            'attrs': {
                'case_type': EPISODE_CASE_TYPE,
                'close': False,
                'create': True,
                'update': {
                    'name': 'Episode #1: Confirmed TB (Patient)',
                }
            },
            'indices': [CaseIndex(
                occurrence_structure,
                identifier='host',
                relationship=CASE_INDEX_EXTENSION,
                related_type=OCCURRENCE_CASE_TYPE,
            )],
        }
        return CaseStructure(**kwargs)

    def get_adherence_case_structure(self, adherence, episode_structure):
        kwargs = {
            'attrs': {
                'case_type': ADHERENCE_CASE_TYPE,
                'close': False,
                'create': True,
                'update': {
                }
            },
            'indices': [CaseIndex(
                episode_structure,
                identifier='host',
                relationship=CASE_INDEX_EXTENSION,
                related_type=EPISODE_CASE_TYPE,
            )],
        }
        return CaseStructure(**kwargs)

    @property
    @memoized
    def _adherences(self):
        return list(Adherence.objects.filter(beneficiaryId=self.beneficiary))
