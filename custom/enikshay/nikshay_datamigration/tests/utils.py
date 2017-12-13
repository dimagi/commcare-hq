from __future__ import absolute_import
from datetime import date

from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from custom.enikshay.nikshay_datamigration.models import Outcome, PatientDetail
from custom.enikshay.tests.utils import ENikshayLocationStructureMixin

ORIGINAL_PERSON_NAME = 'A B C'


class NikshayMigrationMixin(ENikshayLocationStructureMixin):

    def setUp(self):
        self.domain = "enikshay-test-domain"
        super(NikshayMigrationMixin, self).setUp()
        self.patient_detail = PatientDetail.objects.create(
            PregId='MH-ABD-05-16-0001',
            scode='MH',
            Dtocode='ABD',
            Tbunitcode=1,
            pname=ORIGINAL_PERSON_NAME,
            pgender='M',
            page=18,
            poccupation='4',
            paadharno=867386000000,
            paddress='Cambridge MA',
            pmob='5432109876',
            pregdate1=date(2016, 12, 13),
            cname='Secondary name',
            caddress='Secondary address',
            cmob='1234567890',
            dcpulmunory='N',
            dcexpulmunory='3',
            dotname='Bubble Bubbles',
            dotmob='9876543210',
            dotpType=1,
            PHI=2,
            atbtreatment='',
            Ptype='4',
            pcategory='1',
            cvisitedDate1='2016-12-25 00:00:00.000',
            InitiationDate1='2016-12-22 16:06:47.726',
            dotmosignDate1='2016-12-23 00:00:00.000',
        )
        self.outcome = Outcome.objects.create(
            PatientId=self.patient_detail,
            Outcome='NULL',
            HIVStatus='Neg',
        )
        self.case_accessor = CaseAccessors(self.domain)
