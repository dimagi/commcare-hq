from casexml.apps.case.const import CASE_INDEX_EXTENSION
from casexml.apps.case.mock import CaseStructure, CaseIndex

from custom.enikshay.private_sector_datamigration.models import (
    Adherence,
    Episode,
    EpisodePrescription,
    LabTest,
)

from dimagi.utils.decorators.memoized import memoized

PERSON_CASE_TYPE = 'person'
OCCURRENCE_CASE_TYPE = 'occurrence'
EPISODE_CASE_TYPE = 'episode'
ADHERENCE_CASE_TYPE = 'adherence'
PRESCRIPTION_CASE_TYPE = 'prescription'
TEST_CASE_TYPE = 'test'


class BeneficiaryCaseFactory(object):

    def __init__(self, domain, beneficiary):
        self.domain = domain
        self.beneficiary = beneficiary

    def get_case_structures_to_create(self):
        person_structure = self.get_person_case_structure()
        ocurrence_structure = self.get_occurrence_case_structure(person_structure)
        episode_structure = self.get_episode_case_structure(ocurrence_structure)
        episode_descendants = [
            self.get_adherence_case_structure(adherence, episode_structure)
            for adherence in self._adherences
        ] + [
            self.get_prescription_case_structure(prescription, episode_structure)
            for prescription in self._prescriptions
        ]
        episode_or_descendants = episode_descendants or [episode_structure]

        tests = [
            self.get_test_case_structure(labtest, ocurrence_structure)
            for labtest in self._labtests
        ]

        return episode_or_descendants + tests

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

    def get_prescription_case_structure(self, prescription, episode_structure):
        kwargs = {
            'attrs': {
                'case_type': PRESCRIPTION_CASE_TYPE,
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

    def get_test_case_structure(self, labtest, occurrence_structure):
        kwargs = {
            'attrs': {
                'case_type': TEST_CASE_TYPE,
                'close': False,
                'create': True,
                'update': {
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

    @property
    @memoized
    def _episode(self):
        try:
            return Episode.objects.get(beneficiaryID=self.beneficiary)
        except Episode.DoesNotExist:
            return None

    @property
    @memoized
    def _adherences(self):
        return list(Adherence.objects.filter(beneficiaryId=self.beneficiary))

    @property
    @memoized
    def _prescriptions(self):
        return list(EpisodePrescription.objects.filter(beneficiaryId=self.beneficiary))

    @property
    @memoized
    def _labtests(self):
        if self._episode:
            return list(LabTest.objects.filter(episodeId=self._episode))
        else:
            return []
