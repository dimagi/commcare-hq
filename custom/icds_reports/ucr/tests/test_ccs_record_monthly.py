import uuid
from datetime import datetime, date
from xml.etree import ElementTree
from corehq.apps.receiverwrapper.util import submit_form_locally
from casexml.apps.case.const import CASE_INDEX_CHILD
from casexml.apps.case.mock import CaseStructure, CaseIndex
from custom.icds_reports.ucr.tests.base_test import BaseICDSDatasourceTest, create_element_with_value

XMNLS_BP_FORM = 'http://openrosa.org/formdesigner/2864010F-B1B1-4711-8C59-D5B2B81D65DB'
XMLNS_THR_FORM = 'http://openrosa.org/formdesigner/F1B73934-8B70-4CEE-B462-3E4C81F80E4A'
XMLNS_PNC_FORM = 'http://openrosa.org/formdesigner/D4A7ABD2-A7B8-431B-A88B-38245173B0AE'
XMLNS_EBF_FORM = 'http://openrosa.org/formdesigner/89097FB1-6C08-48BA-95B2-67BCF0C5091D'


class TestCCSRecordDataSource(BaseICDSDatasourceTest):
    datasource_filename = 'ccs_record_cases_monthly_tableau'

    def _create_ccs_case(
            self, case_id, dob, edd, add=None,
            caste='st', minority='no', resident='yes', disabled='no',
            sex='F', last_preg_tt='no', tt_complete_date=None,
            num_anc_complete=0, bp1_date=None, bp2_date=None,
            bp3_date=None, pnc1_date=None, date_death=None,
            date_opened=datetime.utcnow(), date_modified=datetime.utcnow(), closed=False):

        household_case = CaseStructure(
            case_id='hh-' + case_id,
            attrs={
                'case_type': 'household',
                'create': True,
                'date_opened': date_opened,
                'date_modified': date_modified,
                'update': dict(
                    hh_caste=caste,
                    hh_minority=minority
                )
            },
        )

        person_case = CaseStructure(
            case_id='p-' + case_id,
            attrs={
                'case_type': 'person',
                'create': True,
                'close': closed,
                'date_opened': date_opened,
                'date_modified': date_modified,
                'update': dict(
                    resident=resident,
                    sex=sex,
                    disabled=disabled,
                    dob=dob,
                    date_death=date_death,
                    last_preg_tt=last_preg_tt,
                )
            },
            indices=[CaseIndex(
                household_case,
                identifier='parent',
                relationship=CASE_INDEX_CHILD,
                related_type=household_case.attrs['case_type'],
            )],
        )

        ccs_record_case = CaseStructure(
            case_id=case_id,
            attrs={
                'case_type': 'ccs_record',
                'create': True,
                'close': closed,
                'date_opened': date_opened,
                'date_modified': date_modified,
                'update': dict(
                    edd=edd,
                    add=add,
                    tt_complete_date=tt_complete_date,
                    num_anc_complete=num_anc_complete,
                    bp1_date=bp1_date,
                    bp2_date=bp2_date,
                    bp3_date=bp3_date,
                    pnc1_date=pnc1_date,
                )
            },
            indices=[CaseIndex(
                person_case,
                identifier='parent',
                relationship=CASE_INDEX_CHILD,
                related_type=person_case.attrs['case_type'],
            )],
        )
        self.casefactory.create_or_update_cases([ccs_record_case])

    def _submit_bp_form(
            self, form_date, case_id, using_ifa='no', num_ifa_consumed_last_seven_days=0,
            anemia=None, extra_meal='no', resting_during_pregnancy='no',
            counsel_immediate_bf='no', counsel_bp_vid='no', counsel_preparation='no',
            counsel_fp_vid='no', counsel_immediate_conception='no',
            counsel_accessible_postpartum_fp='no'):

        form = ElementTree.Element('data')
        form.attrib['xmlns'] = XMNLS_BP_FORM
        form.attrib['xmlns:jrm'] = 'http://openrosa.org/jr/xforms'

        meta = ElementTree.Element('meta')
        meta.append(create_element_with_value('timeEnd', form_date.isoformat()))
        form.append(meta)

        case = ElementTree.Element('case')
        case.attrib['date_modified'] = form_date.isoformat()
        case.attrib['case_id'] = case_id
        case.attrib['xmlns'] = 'http://commcarehq.org/case/transaction/v2'
        form.append(case)

        form.append(create_element_with_value('play_family_planning_vid', counsel_fp_vid))
        form.append(create_element_with_value('conceive', counsel_immediate_conception))

        bp1 = ElementTree.Element('bp1')
        bp1.append(create_element_with_value('using_ifa', using_ifa))
        if using_ifa == 'yes':
            bp1.append(create_element_with_value('ifa_last_seven_days', num_ifa_consumed_last_seven_days))
        bp1.append(create_element_with_value('anemia', anemia))
        bp1.append(create_element_with_value('eating_extra', extra_meal))
        bp1.append(create_element_with_value('resting', resting_during_pregnancy))
        form.append(bp1)

        bp2 = ElementTree.Element('bp2')
        bp2.append(create_element_with_value('immediate_breastfeeding', counsel_immediate_bf))
        bp2.append(create_element_with_value('play_birth_preparedness_vid', counsel_bp_vid))
        bp2.append(create_element_with_value('counsel_preparation', counsel_preparation))
        form.append(bp2)

        fp_group = ElementTree.Element('family_planning_group')
        fp_group.append(
            create_element_with_value('counsel_accessible_ppfp', counsel_accessible_postpartum_fp))
        form.append(fp_group)

        submit_form_locally(ElementTree.tostring(form), self.domain, **{})

    def _submit_thr_rations_form(
            self, form_date, case_id, thr_given_mother='0', rations_distributed=0):

        form = ElementTree.Element('data')
        form.attrib['xmlns'] = XMLNS_THR_FORM
        form.attrib['xmlns:jrm'] = 'http://openrosa.org/jr/xforms'

        meta = ElementTree.Element('meta')
        meta.append(create_element_with_value('timeEnd', form_date.isoformat()))
        form.append(meta)

        case = ElementTree.Element('case')
        case.attrib['date_modified'] = form_date.isoformat()
        case.attrib['case_id'] = case_id
        case.attrib['xmlns'] = 'http://commcarehq.org/case/transaction/v2'
        form.append(case)

        form.append(create_element_with_value('thr_given_mother', thr_given_mother))

        if thr_given_mother == '1':
            mother_thr = ElementTree.Element('mother_thr')
            mother_thr.append(create_element_with_value('days_ration_given_mother', rations_distributed))
            form.append(mother_thr)

        submit_form_locally(ElementTree.tostring(form), self.domain, **{})

    def _submit_pnc_form(self, form_date, case_id, counsel_methods='no'):

        form = ElementTree.Element('data')
        form.attrib['xmlns'] = XMLNS_PNC_FORM
        form.attrib['xmlns:jrm'] = 'http://openrosa.org/jr/xforms'

        meta = ElementTree.Element('meta')
        meta.append(create_element_with_value('timeEnd', form_date.isoformat()))
        form.append(meta)

        case = ElementTree.Element('case')
        case.attrib['date_modified'] = form_date.isoformat()
        case.attrib['case_id'] = case_id
        case.attrib['xmlns'] = 'http://commcarehq.org/case/transaction/v2'
        form.append(case)

        form.append(create_element_with_value('counsel_methods', counsel_methods))

        submit_form_locally(ElementTree.tostring(form), self.domain, **{})

    def _submit_ebf_form(self, form_date, case_id, counsel_methods='no'):

        form = ElementTree.Element('data')
        form.attrib['xmlns'] = XMLNS_EBF_FORM
        form.attrib['xmlns:jrm'] = 'http://openrosa.org/jr/xforms'

        meta = ElementTree.Element('meta')
        meta.append(create_element_with_value('timeEnd', form_date.isoformat()))
        form.append(meta)

        case = ElementTree.Element('case')
        case.attrib['date_modified'] = form_date.isoformat()
        case.attrib['case_id'] = case_id
        case.attrib['xmlns'] = 'http://commcarehq.org/case/transaction/v2'
        form.append(case)

        form.append(create_element_with_value('counsel_methods', counsel_methods))

        submit_form_locally(ElementTree.tostring(form), self.domain, **{})

    def test_open_in_month(self):
        case_id = uuid.uuid4().hex
        self._create_ccs_case(
            case_id=case_id,
            dob=date(1990, 1, 1),
            edd=date(2016, 6, 2),
            date_opened=datetime(2016, 1, 10),
            date_modified=datetime(2016, 3, 12),
            closed=True,
        )

        query = self._rebuild_table_get_query_object()
        self.assertEqual(query.count(), 7)

        row = query.all()[0]
        self.assertEqual(row.month, date(2015, 12, 1))
        self.assertEqual(row.open_in_month, 0)

        row = query.all()[1]
        self.assertEqual(row.month, date(2016, 1, 1))
        self.assertEqual(row.open_in_month, 1)

        row = query.all()[2]
        self.assertEqual(row.month, date(2016, 2, 1))
        self.assertEqual(row.open_in_month, 1)

        row = query.all()[3]
        self.assertEqual(row.month, date(2016, 3, 1))
        self.assertEqual(row.open_in_month, 1)

        row = query.all()[4]
        self.assertEqual(row.month, date(2016, 4, 1))
        self.assertEqual(row.open_in_month, 0)

    def test_alive_in_month(self):
        case_id = uuid.uuid4().hex
        self._create_ccs_case(
            case_id=case_id,
            dob=date(1990, 1, 1),
            edd=date(2016, 6, 2),
            date_opened=datetime(2016, 1, 10),
            date_modified=datetime(2016, 3, 12),
            date_death=date(2016, 1, 10),
        )

        query = self._rebuild_table_get_query_object()
        self.assertEqual(query.count(), 7)

        row = query.all()[0]
        self.assertEqual(row.month, date(2015, 12, 1))
        self.assertEqual(row.alive_in_month, 1)

        row = query.all()[1]
        self.assertEqual(row.month, date(2016, 1, 1))
        self.assertEqual(row.alive_in_month, 1)

        row = query.all()[2]
        self.assertEqual(row.month, date(2016, 2, 1))
        self.assertEqual(row.alive_in_month, 0)

        row = query.all()[3]
        self.assertEqual(row.month, date(2016, 3, 1))
        self.assertEqual(row.alive_in_month, 0)

    def test_demographic_data(self):
        case_id = uuid.uuid4().hex
        self._create_ccs_case(
            case_id=case_id,
            caste='sc',
            minority='yes',
            resident='yes',
            disabled='yes',
            dob=date(1990, 1, 1),
            edd=date(2016, 11, 10),
            date_opened=datetime(2015, 1, 10),
            date_modified=datetime(2016, 3, 12),
        )

        query = self._rebuild_table_get_query_object()
        self.assertEqual(query.count(), 7)

        row = query.all()[0]
        self.assertEqual(row.caste, 'sc')
        self.assertEqual(row.disabled, 'yes')
        self.assertEqual(row.minority, 'yes')
        self.assertEqual(row.resident, 'yes')

    def test_thr_rations(self):
        case_id = uuid.uuid4().hex
        self._create_ccs_case(
            case_id=case_id,
            dob=date(1990, 1, 1),
            edd=date(2016, 9, 10),
            date_opened=datetime(2015, 12, 10),
            date_modified=datetime(2016, 3, 12),
        )

        self._submit_thr_rations_form(
            form_date=datetime(2016, 2, 2),
            case_id=case_id,
            thr_given_mother='1',
            rations_distributed=5,
        )

        self._submit_thr_rations_form(
            form_date=datetime(2016, 2, 6),
            case_id=case_id,
            thr_given_mother='1',
            rations_distributed=6,
        )

        self._submit_thr_rations_form(
            form_date=datetime(2016, 3, 10),
            case_id=case_id,
            thr_given_mother='1',
            rations_distributed=21,
        )

        query = self._rebuild_table_get_query_object()
        self.assertEqual(query.count(), 7)

        row = query.all()[1]
        self.assertEqual(row.month, date(2016, 1, 1))
        self.assertEqual(row.num_rations_distributed, 0)
        self.assertEqual(row.rations_21_plus_distributed, 0)

        row = query.all()[2]
        self.assertEqual(row.month, date(2016, 2, 1))
        self.assertEqual(row.num_rations_distributed, 11)
        self.assertEqual(row.rations_21_plus_distributed, 0)

        row = query.all()[3]
        self.assertEqual(row.month, date(2016, 3, 1))
        self.assertEqual(row.num_rations_distributed, 21)
        self.assertEqual(row.rations_21_plus_distributed, 1)

        row = query.all()[4]
        self.assertEqual(row.month, date(2016, 4, 1))
        self.assertEqual(row.num_rations_distributed, 0)
        self.assertEqual(row.rations_21_plus_distributed, 0)

    def test_lactating_post(self):
        case_id = uuid.uuid4().hex
        self._create_ccs_case(
            case_id=case_id,
            dob=date(1990, 1, 1),
            edd=date(2015, 8, 10),
            add=date(2015, 8, 12),
            date_opened=datetime(2015, 12, 10),
            date_modified=datetime(2016, 3, 12),
        )

        query = self._rebuild_table_get_query_object()
        self.assertEqual(query.count(), 7)

        row = query.all()[1]
        self.assertEqual(row.month, date(2016, 1, 1))
        self.assertEqual(row.pregnant, 0)
        self.assertEqual(row.lactating, 1)
        self.assertEqual(row.ccs_status, 'lactating')

        row = query.all()[2]
        self.assertEqual(row.month, date(2016, 2, 1))
        self.assertEqual(row.pregnant, 0)
        self.assertEqual(row.lactating, 1)
        self.assertEqual(row.ccs_status, 'lactating')

        row = query.all()[3]
        self.assertEqual(row.month, date(2016, 3, 1))
        self.assertEqual(row.pregnant, 0)
        self.assertEqual(row.lactating, 0)
        self.assertEqual(row.ccs_status, 'other')

        row = query.all()[4]
        self.assertEqual(row.month, date(2016, 4, 1))
        self.assertEqual(row.pregnant, 0)
        self.assertEqual(row.lactating, 0)
        self.assertEqual(row.ccs_status, 'other')

    def test_preg_to_lactating(self):
        case_id = uuid.uuid4().hex
        self._create_ccs_case(
            case_id=case_id,
            dob=date(1990, 1, 1),
            edd=date(2016, 2, 4),
            add=date(2016, 2, 15),
            date_opened=datetime(2015, 12, 10),
            date_modified=datetime(2016, 3, 12),
        )

        query = self._rebuild_table_get_query_object()
        self.assertEqual(query.count(), 7)

        row = query.all()[1]
        self.assertEqual(row.month, date(2016, 1, 1))
        self.assertEqual(row.pregnant, 1)
        self.assertEqual(row.lactating, 0)
        self.assertEqual(row.ccs_status, 'pregnant')

        row = query.all()[2]
        self.assertEqual(row.month, date(2016, 2, 1))
        self.assertEqual(row.pregnant, 0)
        self.assertEqual(row.lactating, 1)
        self.assertEqual(row.ccs_status, 'lactating')

        row = query.all()[3]
        self.assertEqual(row.month, date(2016, 3, 1))
        self.assertEqual(row.pregnant, 0)
        self.assertEqual(row.lactating, 1)
        self.assertEqual(row.ccs_status, 'lactating')

    def test_pre_preg(self):
        case_id = uuid.uuid4().hex
        self._create_ccs_case(
            case_id=case_id,
            dob=date(1990, 1, 1),
            edd=date(2016, 9, 6),
            date_opened=datetime(2016, 1, 4),
            date_modified=datetime(2016, 3, 12),
        )

        query = self._rebuild_table_get_query_object()
        self.assertEqual(query.count(), 7)

        # case is not open
        row = query.all()[0]
        self.assertEqual(row.month, date(2015, 12, 1))
        self.assertEqual(row.pregnant, 0)
        self.assertEqual(row.lactating, 0)
        self.assertEqual(row.ccs_status, 'other')

        row = query.all()[1]
        self.assertEqual(row.month, date(2016, 1, 1))
        self.assertEqual(row.pregnant, 1)
        self.assertEqual(row.lactating, 0)
        self.assertEqual(row.ccs_status, 'pregnant')

        row = query.all()[2]
        self.assertEqual(row.month, date(2016, 2, 1))
        self.assertEqual(row.pregnant, 1)
        self.assertEqual(row.lactating, 0)
        self.assertEqual(row.ccs_status, 'pregnant')

        row = query.all()[3]
        self.assertEqual(row.month, date(2016, 3, 1))
        self.assertEqual(row.pregnant, 1)
        self.assertEqual(row.lactating, 0)
        self.assertEqual(row.ccs_status, 'pregnant')

        row = query.all()[4]
        self.assertEqual(row.month, date(2016, 4, 1))
        self.assertEqual(row.pregnant, 1)
        self.assertEqual(row.lactating, 0)
        self.assertEqual(row.ccs_status, 'pregnant')

    def test_postnatal(self):
        case_id = uuid.uuid4().hex
        self._create_ccs_case(
            case_id=case_id,
            dob=date(1990, 1, 1),
            edd=date(2016, 2, 4),
            add=date(2016, 2, 15),
            date_opened=datetime(2015, 12, 10),
            date_modified=datetime(2016, 3, 12),
        )

        query = self._rebuild_table_get_query_object()
        self.assertEqual(query.count(), 7)

        row = query.all()[1]
        self.assertEqual(row.month, date(2016, 1, 1))
        self.assertEqual(row.postnatal, 0)

        row = query.all()[2]
        self.assertEqual(row.month, date(2016, 2, 1))
        self.assertEqual(row.postnatal, 1)

        row = query.all()[3]
        self.assertEqual(row.month, date(2016, 3, 1))
        self.assertEqual(row.postnatal, 1)

        row = query.all()[4]
        self.assertEqual(row.month, date(2016, 4, 1))
        self.assertEqual(row.postnatal, 0)

    def test_tt_complete_none(self):
        case_id = uuid.uuid4().hex
        self._create_ccs_case(
            case_id=case_id,
            dob=date(1990, 1, 1),
            edd=date(2016, 6, 4),
            date_opened=datetime(2015, 12, 10),
            date_modified=datetime(2016, 3, 12),
        )

        query = self._rebuild_table_get_query_object()
        self.assertEqual(query.count(), 7)

        row = query.all()[1]
        self.assertEqual(row.month, date(2016, 1, 1))
        self.assertEqual(row.tetanus_complete, 0)

        row = query.all()[2]
        self.assertEqual(row.month, date(2016, 2, 1))
        self.assertEqual(row.tetanus_complete, 0)

        row = query.all()[3]
        self.assertEqual(row.month, date(2016, 3, 1))
        self.assertEqual(row.tetanus_complete, 0)

    def test_tt_complete(self):
        case_id = uuid.uuid4().hex
        self._create_ccs_case(
            case_id=case_id,
            dob=date(1990, 1, 1),
            edd=date(2016, 6, 4),
            date_opened=datetime(2015, 12, 10),
            date_modified=datetime(2016, 3, 12),
            tt_complete_date=date(2016, 2, 7)
        )

        query = self._rebuild_table_get_query_object()
        self.assertEqual(query.count(), 7)

        row = query.all()[1]
        self.assertEqual(row.month, date(2016, 1, 1))
        self.assertEqual(row.tetanus_complete, 0)

        row = query.all()[2]
        self.assertEqual(row.month, date(2016, 2, 1))
        self.assertEqual(row.tetanus_complete, 1)

        row = query.all()[3]
        self.assertEqual(row.month, date(2016, 3, 1))
        self.assertEqual(row.tetanus_complete, 1)

    def test_delivered_in_month(self):
        case_id = uuid.uuid4().hex
        self._create_ccs_case(
            case_id=case_id,
            dob=date(1990, 1, 1),
            edd=date(2016, 2, 4),
            add=date(2016, 2, 15),
            date_opened=datetime(2015, 12, 10),
            date_modified=datetime(2016, 3, 12),
        )

        query = self._rebuild_table_get_query_object()
        self.assertEqual(query.count(), 7)

        row = query.all()[1]
        self.assertEqual(row.month, date(2016, 1, 1))
        self.assertEqual(row.delivered_in_month, 0)

        row = query.all()[2]
        self.assertEqual(row.month, date(2016, 2, 1))
        self.assertEqual(row.delivered_in_month, 1)

        row = query.all()[3]
        self.assertEqual(row.month, date(2016, 3, 1))
        self.assertEqual(row.delivered_in_month, 0)

    def test_trimester_1_2(self):
        case_id = uuid.uuid4().hex
        self._create_ccs_case(
            case_id=case_id,
            dob=date(1990, 1, 1),
            edd=date(2016, 9, 6),
            date_opened=datetime(2016, 2, 3),
            date_modified=datetime(2016, 3, 12),
        )

        query = self._rebuild_table_get_query_object()
        self.assertEqual(query.count(), 7)

        # case is not open
        row = query.all()[1]
        self.assertEqual(row.month, date(2016, 1, 1))
        self.assertEqual(row.trimester, None)
        self.assertEqual(row.trimester_2, 0)
        self.assertEqual(row.trimester_3, 0)

        row = query.all()[2]
        self.assertEqual(row.month, date(2016, 2, 1))
        self.assertEqual(row.trimester, 1)
        self.assertEqual(row.trimester_2, 0)
        self.assertEqual(row.trimester_3, 0)

        row = query.all()[3]
        self.assertEqual(row.month, date(2016, 3, 1))
        self.assertEqual(row.trimester, 2)
        self.assertEqual(row.trimester_2, 1)
        self.assertEqual(row.trimester_3, 0)

        row = query.all()[4]
        self.assertEqual(row.month, date(2016, 4, 1))
        self.assertEqual(row.trimester, 2)
        self.assertEqual(row.trimester_2, 1)
        self.assertEqual(row.trimester_3, 0)

    def test_trimester_3_none(self):
        case_id = uuid.uuid4().hex
        self._create_ccs_case(
            case_id=case_id,
            dob=date(1990, 1, 1),
            edd=date(2016, 2, 4),
            add=date(2016, 2, 15),
            date_opened=datetime(2015, 12, 10),
            date_modified=datetime(2016, 3, 12),
        )

        query = self._rebuild_table_get_query_object()
        self.assertEqual(query.count(), 7)

        row = query.all()[0]
        self.assertEqual(row.month, date(2015, 12, 1))
        self.assertEqual(row.trimester, 3)
        self.assertEqual(row.trimester_2, 0)
        self.assertEqual(row.trimester_3, 1)

        row = query.all()[1]
        self.assertEqual(row.month, date(2016, 1, 1))
        self.assertEqual(row.trimester, 3)
        self.assertEqual(row.trimester_2, 0)
        self.assertEqual(row.trimester_3, 1)

        row = query.all()[2]
        self.assertEqual(row.month, date(2016, 2, 1))
        self.assertEqual(row.trimester, None)
        self.assertEqual(row.trimester_2, 0)
        self.assertEqual(row.trimester_3, 0)

        row = query.all()[3]
        self.assertEqual(row.month, date(2016, 3, 1))
        self.assertEqual(row.trimester, None)
        self.assertEqual(row.trimester_2, 0)
        self.assertEqual(row.trimester_3, 0)

    def test_no_anc_at_delivery(self):
        case_id = uuid.uuid4().hex
        self._create_ccs_case(
            case_id=case_id,
            dob=date(1990, 1, 1),
            edd=date(2016, 2, 4),
            add=date(2016, 2, 15),
            date_opened=datetime(2015, 12, 10),
            date_modified=datetime(2016, 3, 12),
            num_anc_complete=0,
        )

        query = self._rebuild_table_get_query_object()
        self.assertEqual(query.count(), 7)

        row = query.all()[1]
        self.assertEqual(row.month, date(2016, 1, 1))
        self.assertEqual(row.anc1_received_at_delivery, 0)
        self.assertEqual(row.anc2_received_at_delivery, 0)
        self.assertEqual(row.anc3_received_at_delivery, 0)
        self.assertEqual(row.anc4_received_at_delivery, 0)

        row = query.all()[2]
        self.assertEqual(row.month, date(2016, 2, 1))
        self.assertEqual(row.anc1_received_at_delivery, 0)
        self.assertEqual(row.anc2_received_at_delivery, 0)
        self.assertEqual(row.anc3_received_at_delivery, 0)
        self.assertEqual(row.anc4_received_at_delivery, 0)

        row = query.all()[3]
        self.assertEqual(row.month, date(2016, 3, 1))
        self.assertEqual(row.anc1_received_at_delivery, 0)
        self.assertEqual(row.anc2_received_at_delivery, 0)
        self.assertEqual(row.anc3_received_at_delivery, 0)
        self.assertEqual(row.anc4_received_at_delivery, 0)

    def test_anc1_at_delivery(self):
        case_id = uuid.uuid4().hex
        self._create_ccs_case(
            case_id=case_id,
            dob=date(1990, 1, 1),
            edd=date(2016, 2, 4),
            add=date(2016, 2, 15),
            date_opened=datetime(2015, 12, 10),
            date_modified=datetime(2016, 3, 12),
            num_anc_complete=1,
        )

        query = self._rebuild_table_get_query_object()
        self.assertEqual(query.count(), 7)

        row = query.all()[1]
        self.assertEqual(row.month, date(2016, 1, 1))
        self.assertEqual(row.anc1_received_at_delivery, 0)
        self.assertEqual(row.anc2_received_at_delivery, 0)
        self.assertEqual(row.anc3_received_at_delivery, 0)
        self.assertEqual(row.anc4_received_at_delivery, 0)

        row = query.all()[2]
        self.assertEqual(row.month, date(2016, 2, 1))
        self.assertEqual(row.anc1_received_at_delivery, 1)
        self.assertEqual(row.anc2_received_at_delivery, 0)
        self.assertEqual(row.anc3_received_at_delivery, 0)
        self.assertEqual(row.anc4_received_at_delivery, 0)

        row = query.all()[3]
        self.assertEqual(row.month, date(2016, 3, 1))
        self.assertEqual(row.anc1_received_at_delivery, 0)
        self.assertEqual(row.anc2_received_at_delivery, 0)
        self.assertEqual(row.anc3_received_at_delivery, 0)
        self.assertEqual(row.anc4_received_at_delivery, 0)

    def test_anc2_at_delivery(self):
        case_id = uuid.uuid4().hex
        self._create_ccs_case(
            case_id=case_id,
            dob=date(1990, 1, 1),
            edd=date(2016, 2, 4),
            add=date(2016, 2, 15),
            date_opened=datetime(2015, 12, 10),
            date_modified=datetime(2016, 3, 12),
            num_anc_complete=2,
        )

        query = self._rebuild_table_get_query_object()
        self.assertEqual(query.count(), 7)

        row = query.all()[1]
        self.assertEqual(row.month, date(2016, 1, 1))
        self.assertEqual(row.anc1_received_at_delivery, 0)
        self.assertEqual(row.anc2_received_at_delivery, 0)
        self.assertEqual(row.anc3_received_at_delivery, 0)
        self.assertEqual(row.anc4_received_at_delivery, 0)

        row = query.all()[2]
        self.assertEqual(row.month, date(2016, 2, 1))
        self.assertEqual(row.anc1_received_at_delivery, 1)
        self.assertEqual(row.anc2_received_at_delivery, 1)
        self.assertEqual(row.anc3_received_at_delivery, 0)
        self.assertEqual(row.anc4_received_at_delivery, 0)

        row = query.all()[3]
        self.assertEqual(row.month, date(2016, 3, 1))
        self.assertEqual(row.anc1_received_at_delivery, 0)
        self.assertEqual(row.anc2_received_at_delivery, 0)
        self.assertEqual(row.anc3_received_at_delivery, 0)
        self.assertEqual(row.anc4_received_at_delivery, 0)

    def test_anc3_at_delivery(self):
        case_id = uuid.uuid4().hex
        self._create_ccs_case(
            case_id=case_id,
            dob=date(1990, 1, 1),
            edd=date(2016, 2, 4),
            add=date(2016, 2, 15),
            date_opened=datetime(2015, 12, 10),
            date_modified=datetime(2016, 3, 12),
            num_anc_complete=3,
        )

        query = self._rebuild_table_get_query_object()
        self.assertEqual(query.count(), 7)

        row = query.all()[1]
        self.assertEqual(row.month, date(2016, 1, 1))
        self.assertEqual(row.anc1_received_at_delivery, 0)
        self.assertEqual(row.anc2_received_at_delivery, 0)
        self.assertEqual(row.anc3_received_at_delivery, 0)
        self.assertEqual(row.anc4_received_at_delivery, 0)

        row = query.all()[2]
        self.assertEqual(row.month, date(2016, 2, 1))
        self.assertEqual(row.anc1_received_at_delivery, 1)
        self.assertEqual(row.anc2_received_at_delivery, 1)
        self.assertEqual(row.anc3_received_at_delivery, 1)
        self.assertEqual(row.anc4_received_at_delivery, 0)

        row = query.all()[3]
        self.assertEqual(row.month, date(2016, 3, 1))
        self.assertEqual(row.anc1_received_at_delivery, 0)
        self.assertEqual(row.anc2_received_at_delivery, 0)
        self.assertEqual(row.anc3_received_at_delivery, 0)
        self.assertEqual(row.anc4_received_at_delivery, 0)

    def test_anc4_at_delivery(self):
        case_id = uuid.uuid4().hex
        self._create_ccs_case(
            case_id=case_id,
            dob=date(1990, 1, 1),
            edd=date(2016, 2, 4),
            add=date(2016, 2, 15),
            date_opened=datetime(2015, 12, 10),
            date_modified=datetime(2016, 3, 12),
            num_anc_complete=4,
        )

        query = self._rebuild_table_get_query_object()
        self.assertEqual(query.count(), 7)

        row = query.all()[1]
        self.assertEqual(row.month, date(2016, 1, 1))
        self.assertEqual(row.anc1_received_at_delivery, 0)
        self.assertEqual(row.anc2_received_at_delivery, 0)
        self.assertEqual(row.anc3_received_at_delivery, 0)
        self.assertEqual(row.anc4_received_at_delivery, 0)

        row = query.all()[2]
        self.assertEqual(row.month, date(2016, 2, 1))
        self.assertEqual(row.anc1_received_at_delivery, 1)
        self.assertEqual(row.anc2_received_at_delivery, 1)
        self.assertEqual(row.anc3_received_at_delivery, 1)
        self.assertEqual(row.anc4_received_at_delivery, 1)

        row = query.all()[3]
        self.assertEqual(row.month, date(2016, 3, 1))
        self.assertEqual(row.anc1_received_at_delivery, 0)
        self.assertEqual(row.anc2_received_at_delivery, 0)
        self.assertEqual(row.anc3_received_at_delivery, 0)
        self.assertEqual(row.anc4_received_at_delivery, 0)

    def test_reg_trimester_3_at_delivery(self):
        case_id = uuid.uuid4().hex
        self._create_ccs_case(
            case_id=case_id,
            dob=date(1990, 1, 1),
            edd=date(2016, 2, 4),
            add=date(2016, 2, 15),
            date_opened=datetime(2015, 12, 10),
            date_modified=datetime(2016, 3, 12),
        )

        query = self._rebuild_table_get_query_object()
        self.assertEqual(query.count(), 7)

        row = query.all()[1]
        self.assertEqual(row.month, date(2016, 1, 1))
        self.assertEqual(row.registration_trimester_at_delivery, None)

        row = query.all()[2]
        self.assertEqual(row.month, date(2016, 2, 1))
        self.assertEqual(row.registration_trimester_at_delivery, 3)

        row = query.all()[3]
        self.assertEqual(row.month, date(2016, 3, 1))
        self.assertEqual(row.registration_trimester_at_delivery, None)

    def test_reg_trimester_2_at_delivery(self):
        case_id = uuid.uuid4().hex
        self._create_ccs_case(
            case_id=case_id,
            dob=date(1990, 1, 1),
            edd=date(2016, 4, 13),
            add=date(2016, 4, 15),
            date_opened=datetime(2015, 12, 10),
            date_modified=datetime(2016, 5, 12),
        )

        query = self._rebuild_table_get_query_object()
        self.assertEqual(query.count(), 7)

        row = query.all()[1]
        self.assertEqual(row.month, date(2016, 3, 1))
        self.assertEqual(row.registration_trimester_at_delivery, None)

        row = query.all()[2]
        self.assertEqual(row.month, date(2016, 4, 1))
        self.assertEqual(row.registration_trimester_at_delivery, 2)

        row = query.all()[3]
        self.assertEqual(row.month, date(2016, 5, 1))
        self.assertEqual(row.registration_trimester_at_delivery, None)

    def test_reg_trimester_1_at_delivery(self):
        case_id = uuid.uuid4().hex
        self._create_ccs_case(
            case_id=case_id,
            dob=date(1990, 1, 1),
            edd=date(2016, 8, 10),
            add=date(2016, 8, 8),
            date_opened=datetime(2015, 12, 10),
            date_modified=datetime(2016, 9, 12),
        )

        query = self._rebuild_table_get_query_object()
        self.assertEqual(query.count(), 7)

        row = query.all()[1]
        self.assertEqual(row.month, date(2016, 7, 1))
        self.assertEqual(row.registration_trimester_at_delivery, None)

        row = query.all()[2]
        self.assertEqual(row.month, date(2016, 8, 1))
        self.assertEqual(row.registration_trimester_at_delivery, 1)

        row = query.all()[3]
        self.assertEqual(row.month, date(2016, 9, 1))
        self.assertEqual(row.registration_trimester_at_delivery, None)

    def test_bp_in_month(self):
        case_id = uuid.uuid4().hex
        self._create_ccs_case(
            case_id=case_id,
            dob=date(1990, 1, 1),
            edd=date(2016, 9, 10),
            date_opened=datetime(2015, 12, 10),
            date_modified=datetime(2016, 3, 12),
        )

        self._submit_bp_form(
            form_date=datetime(2016, 2, 2),
            case_id=case_id
        )

        query = self._rebuild_table_get_query_object()
        self.assertEqual(query.count(), 7)

        row = query.all()[1]
        self.assertEqual(row.month, date(2016, 1, 1))
        self.assertEqual(row.bp_visited_in_month, 0)

        row = query.all()[2]
        self.assertEqual(row.month, date(2016, 2, 1))
        self.assertEqual(row.bp_visited_in_month, 1)

        row = query.all()[3]
        self.assertEqual(row.month, date(2016, 3, 1))
        self.assertEqual(row.bp_visited_in_month, 0)

    def test_pnc_in_month(self):
        case_id = uuid.uuid4().hex
        self._create_ccs_case(
            case_id=case_id,
            dob=date(1990, 1, 1),
            edd=date(2016, 2, 5),
            add=date(2016, 2, 2),
            date_opened=datetime(2015, 12, 10),
            date_modified=datetime(2016, 3, 12),
        )

        self._submit_pnc_form(
            form_date=datetime(2016, 2, 2),
            case_id=case_id
        )

        query = self._rebuild_table_get_query_object()
        self.assertEqual(query.count(), 7)

        row = query.all()[1]
        self.assertEqual(row.month, date(2016, 1, 1))
        self.assertEqual(row.pnc_visited_in_month, 0)

        row = query.all()[2]
        self.assertEqual(row.month, date(2016, 2, 1))
        self.assertEqual(row.pnc_visited_in_month, 1)

        row = query.all()[3]
        self.assertEqual(row.month, date(2016, 3, 1))
        self.assertEqual(row.pnc_visited_in_month, 0)

    def test_bp_last_submitted_form(self):
        case_id = uuid.uuid4().hex
        self._create_ccs_case(
            case_id=case_id,
            dob=date(1990, 1, 1),
            edd=date(2016, 5, 10),
            date_opened=datetime(2015, 12, 10),
            date_modified=datetime(2016, 3, 12),
        )

        self._submit_bp_form(
            form_date=datetime(2016, 1, 10),
            case_id=case_id,
            using_ifa='yes',
            num_ifa_consumed_last_seven_days=4,
            extra_meal='yes',
            resting_during_pregnancy='yes',
        )

        self._submit_bp_form(
            form_date=datetime(2016, 3, 8),
            case_id=case_id,
            using_ifa='no',
            num_ifa_consumed_last_seven_days=2,
            extra_meal='no',
            resting_during_pregnancy='no',
        )

        query = self._rebuild_table_get_query_object()
        self.assertEqual(query.count(), 7)

        row = query.all()[0]
        self.assertEqual(row.month, date(2015, 12, 1))
        self.assertEqual(row.using_ifa, 0)
        self.assertEqual(row.ifa_consumed_last_seven_days, 0)
        self.assertEqual(row.extra_meal, 0)
        self.assertEqual(row.resting_during_pregnancy, 0)

        row = query.all()[1]
        self.assertEqual(row.month, date(2016, 1, 1))
        self.assertEqual(row.using_ifa, 1)
        self.assertEqual(row.ifa_consumed_last_seven_days, 1)
        self.assertEqual(row.extra_meal, 1)
        self.assertEqual(row.resting_during_pregnancy, 1)

        row = query.all()[2]
        self.assertEqual(row.month, date(2016, 2, 1))
        self.assertEqual(row.using_ifa, 1)
        self.assertEqual(row.ifa_consumed_last_seven_days, 1)
        self.assertEqual(row.extra_meal, 1)
        self.assertEqual(row.resting_during_pregnancy, 1)

        row = query.all()[3]
        self.assertEqual(row.month, date(2016, 3, 1))
        self.assertEqual(row.using_ifa, 0)
        self.assertEqual(row.ifa_consumed_last_seven_days, 0)
        self.assertEqual(row.extra_meal, 0)
        self.assertEqual(row.resting_during_pregnancy, 0)

        row = query.all()[4]
        self.assertEqual(row.month, date(2016, 4, 1))
        self.assertEqual(row.using_ifa, 0)
        self.assertEqual(row.ifa_consumed_last_seven_days, 0)
        self.assertEqual(row.extra_meal, 0)
        self.assertEqual(row.resting_during_pregnancy, 0)

    def test_bp_any_submitted_form(self):
        case_id = uuid.uuid4().hex
        self._create_ccs_case(
            case_id=case_id,
            dob=date(1990, 1, 1),
            edd=date(2016, 4, 10),
            date_opened=datetime(2015, 12, 10),
            date_modified=datetime(2016, 3, 12),
        )

        self._submit_bp_form(
            form_date=datetime(2016, 1, 10),
            case_id=case_id,
            counsel_immediate_bf='no',
            counsel_bp_vid='no',
            counsel_preparation='no',
            counsel_fp_vid='no',
            counsel_immediate_conception='no',
            counsel_accessible_postpartum_fp='no'
        )

        self._submit_bp_form(
            form_date=datetime(2016, 3, 6),
            case_id=case_id,
            counsel_immediate_bf='yes',
            counsel_bp_vid='yes',
            counsel_preparation='yes',
            counsel_fp_vid='yes',
            counsel_immediate_conception='yes',
            counsel_accessible_postpartum_fp='yes'
        )

        self._submit_bp_form(
            form_date=datetime(2016, 3, 8),
            case_id=case_id,
            counsel_immediate_bf='no',
            counsel_bp_vid='no',
            counsel_preparation='no',
            counsel_fp_vid='no',
            counsel_immediate_conception='no',
            counsel_accessible_postpartum_fp='no'
        )

        query = self._rebuild_table_get_query_object()
        self.assertEqual(query.count(), 7)

        row = query.all()[0]
        self.assertEqual(row.month, date(2015, 12, 1))
        self.assertEqual(row.counsel_immediate_bf, 0)
        self.assertEqual(row.counsel_bp_vid, 0)
        self.assertEqual(row.counsel_preparation, 0)
        self.assertEqual(row.counsel_fp_vid, 0)
        self.assertEqual(row.counsel_immediate_conception, 0)
        self.assertEqual(row.counsel_accessible_postpartum_fp, 0)

        row = query.all()[1]
        self.assertEqual(row.month, date(2016, 1, 1))
        self.assertEqual(row.counsel_immediate_bf, 0)
        self.assertEqual(row.counsel_bp_vid, 0)
        self.assertEqual(row.counsel_preparation, 0)
        self.assertEqual(row.counsel_fp_vid, 0)
        self.assertEqual(row.counsel_immediate_conception, 0)
        self.assertEqual(row.counsel_accessible_postpartum_fp, 0)

        row = query.all()[2]
        self.assertEqual(row.month, date(2016, 2, 1))
        self.assertEqual(row.counsel_immediate_bf, 0)
        self.assertEqual(row.counsel_bp_vid, 0)
        self.assertEqual(row.counsel_preparation, 0)
        self.assertEqual(row.counsel_fp_vid, 0)
        self.assertEqual(row.counsel_immediate_conception, 0)
        self.assertEqual(row.counsel_accessible_postpartum_fp, 0)

        row = query.all()[3]
        self.assertEqual(row.month, date(2016, 3, 1))
        self.assertEqual(row.counsel_immediate_bf, 1)
        self.assertEqual(row.counsel_bp_vid, 1)
        self.assertEqual(row.counsel_preparation, 1)
        self.assertEqual(row.counsel_fp_vid, 1)
        self.assertEqual(row.counsel_immediate_conception, 1)
        self.assertEqual(row.counsel_accessible_postpartum_fp, 1)

        row = query.all()[4]
        self.assertEqual(row.month, date(2016, 4, 1))
        self.assertEqual(row.counsel_immediate_bf, 1)
        self.assertEqual(row.counsel_bp_vid, 1)
        self.assertEqual(row.counsel_preparation, 1)
        self.assertEqual(row.counsel_fp_vid, 1)
        self.assertEqual(row.counsel_immediate_conception, 1)
        self.assertEqual(row.counsel_accessible_postpartum_fp, 1)

    def test_anemic_unknown(self):
        case_id = uuid.uuid4().hex
        self._create_ccs_case(
            case_id=case_id,
            dob=date(1990, 1, 1),
            edd=date(2016, 5, 10),
            date_opened=datetime(2015, 12, 10),
            date_modified=datetime(2016, 3, 12),
        )

        query = self._rebuild_table_get_query_object()
        self.assertEqual(query.count(), 7)

        row = query.all()[1]
        self.assertEqual(row.month, date(2016, 1, 1))
        self.assertEqual(row.anemic_unknown, 1)
        self.assertEqual(row.anemic_normal, 0)
        self.assertEqual(row.anemic_moderate, 0)
        self.assertEqual(row.anemic_severe, 0)

        row = query.all()[2]
        self.assertEqual(row.month, date(2016, 2, 1))
        self.assertEqual(row.anemic_unknown, 1)
        self.assertEqual(row.anemic_normal, 0)
        self.assertEqual(row.anemic_moderate, 0)
        self.assertEqual(row.anemic_severe, 0)

    def test_anemia_normal(self):
        case_id = uuid.uuid4().hex
        self._create_ccs_case(
            case_id=case_id,
            dob=date(1990, 1, 1),
            edd=date(2016, 5, 10),
            date_opened=datetime(2015, 12, 10),
            date_modified=datetime(2016, 3, 12),
        )

        self._submit_bp_form(
            form_date=datetime(2016, 1, 9),
            case_id=case_id,
            anemia='severe',
        )

        self._submit_bp_form(
            form_date=datetime(2016, 1, 10),
            case_id=case_id,
            anemia='normal',
        )

        self._submit_bp_form(
            form_date=datetime(2016, 2, 10),
            case_id=case_id,
        )

        query = self._rebuild_table_get_query_object()
        self.assertEqual(query.count(), 7)

        row = query.all()[0]
        self.assertEqual(row.month, date(2015, 12, 1))
        self.assertEqual(row.anemic_unknown, 1)
        self.assertEqual(row.anemic_normal, 0)
        self.assertEqual(row.anemic_moderate, 0)
        self.assertEqual(row.anemic_severe, 0)

        row = query.all()[1]
        self.assertEqual(row.month, date(2016, 1, 1))
        self.assertEqual(row.anemic_unknown, 0)
        self.assertEqual(row.anemic_normal, 1)
        self.assertEqual(row.anemic_moderate, 0)
        self.assertEqual(row.anemic_severe, 0)

        row = query.all()[2]
        self.assertEqual(row.month, date(2016, 2, 1))
        self.assertEqual(row.anemic_unknown, 0)
        self.assertEqual(row.anemic_normal, 1)
        self.assertEqual(row.anemic_moderate, 0)
        self.assertEqual(row.anemic_severe, 0)

        row = query.all()[3]
        self.assertEqual(row.month, date(2016, 3, 1))
        self.assertEqual(row.anemic_unknown, 0)
        self.assertEqual(row.anemic_normal, 1)
        self.assertEqual(row.anemic_moderate, 0)
        self.assertEqual(row.anemic_severe, 0)

    def test_anemia_moderate(self):
        case_id = uuid.uuid4().hex
        self._create_ccs_case(
            case_id=case_id,
            dob=date(1990, 1, 1),
            edd=date(2016, 5, 10),
            date_opened=datetime(2015, 12, 10),
            date_modified=datetime(2016, 3, 12),
        )

        self._submit_bp_form(
            form_date=datetime(2016, 1, 9),
            case_id=case_id,
            anemia='severe',
        )

        self._submit_bp_form(
            form_date=datetime(2016, 1, 10),
            case_id=case_id,
            anemia='moderate',
        )

        self._submit_bp_form(
            form_date=datetime(2016, 2, 10),
            case_id=case_id,
        )

        query = self._rebuild_table_get_query_object()
        self.assertEqual(query.count(), 7)

        row = query.all()[0]
        self.assertEqual(row.month, date(2015, 12, 1))
        self.assertEqual(row.anemic_unknown, 1)
        self.assertEqual(row.anemic_normal, 0)
        self.assertEqual(row.anemic_moderate, 0)
        self.assertEqual(row.anemic_severe, 0)

        row = query.all()[1]
        self.assertEqual(row.month, date(2016, 1, 1))
        self.assertEqual(row.anemic_unknown, 0)
        self.assertEqual(row.anemic_normal, 0)
        self.assertEqual(row.anemic_moderate, 1)
        self.assertEqual(row.anemic_severe, 0)

        row = query.all()[2]
        self.assertEqual(row.month, date(2016, 2, 1))
        self.assertEqual(row.anemic_unknown, 0)
        self.assertEqual(row.anemic_normal, 0)
        self.assertEqual(row.anemic_moderate, 1)
        self.assertEqual(row.anemic_severe, 0)

        row = query.all()[3]
        self.assertEqual(row.month, date(2016, 3, 1))
        self.assertEqual(row.anemic_unknown, 0)
        self.assertEqual(row.anemic_normal, 0)
        self.assertEqual(row.anemic_moderate, 1)
        self.assertEqual(row.anemic_severe, 0)

    def test_anemia_severe(self):
        case_id = uuid.uuid4().hex
        self._create_ccs_case(
            case_id=case_id,
            dob=date(1990, 1, 1),
            edd=date(2016, 5, 10),
            date_opened=datetime(2015, 12, 10),
            date_modified=datetime(2016, 3, 12),
        )

        self._submit_bp_form(
            form_date=datetime(2016, 1, 9),
            case_id=case_id,
            anemia='normal',
        )

        self._submit_bp_form(
            form_date=datetime(2016, 1, 10),
            case_id=case_id,
            anemia='severe',
        )

        self._submit_bp_form(
            form_date=datetime(2016, 2, 10),
            case_id=case_id,
        )

        query = self._rebuild_table_get_query_object()
        self.assertEqual(query.count(), 7)

        row = query.all()[0]
        self.assertEqual(row.month, date(2015, 12, 1))
        self.assertEqual(row.anemic_unknown, 1)
        self.assertEqual(row.anemic_normal, 0)
        self.assertEqual(row.anemic_moderate, 0)
        self.assertEqual(row.anemic_severe, 0)

        row = query.all()[1]
        self.assertEqual(row.month, date(2016, 1, 1))
        self.assertEqual(row.anemic_unknown, 0)
        self.assertEqual(row.anemic_normal, 0)
        self.assertEqual(row.anemic_moderate, 0)
        self.assertEqual(row.anemic_severe, 1)

        row = query.all()[2]
        self.assertEqual(row.month, date(2016, 2, 1))
        self.assertEqual(row.anemic_unknown, 0)
        self.assertEqual(row.anemic_normal, 0)
        self.assertEqual(row.anemic_moderate, 0)
        self.assertEqual(row.anemic_severe, 1)

        row = query.all()[3]
        self.assertEqual(row.month, date(2016, 3, 1))
        self.assertEqual(row.anemic_unknown, 0)
        self.assertEqual(row.anemic_normal, 0)
        self.assertEqual(row.anemic_moderate, 0)
        self.assertEqual(row.anemic_severe, 1)

    def test_counsel_methods_pnc(self):
        case_id = uuid.uuid4().hex
        self._create_ccs_case(
            case_id=case_id,
            dob=date(1990, 1, 1),
            edd=date(2016, 3, 5),
            add=date(2016, 2, 25),
            date_opened=datetime(2015, 12, 10),
            date_modified=datetime(2016, 3, 12),
        )

        self._submit_pnc_form(
            form_date=datetime(2016, 2, 26),
            case_id=case_id,
            counsel_methods='no',
        )

        self._submit_pnc_form(
            form_date=datetime(2016, 3, 2),
            case_id=case_id,
            counsel_methods='yes',
        )

        query = self._rebuild_table_get_query_object()
        self.assertEqual(query.count(), 7)

        row = query.all()[1]
        self.assertEqual(row.month, date(2016, 1, 1))
        self.assertEqual(row.counsel_fp_methods, 0)

        row = query.all()[2]
        self.assertEqual(row.month, date(2016, 2, 1))
        self.assertEqual(row.counsel_fp_methods, 0)

        row = query.all()[3]
        self.assertEqual(row.month, date(2016, 3, 1))
        self.assertEqual(row.counsel_fp_methods, 1)

        row = query.all()[4]
        self.assertEqual(row.month, date(2016, 4, 1))
        self.assertEqual(row.counsel_fp_methods, 1)

    def test_counsel_methods_ebf(self):
        case_id = uuid.uuid4().hex
        self._create_ccs_case(
            case_id=case_id,
            dob=date(1990, 1, 1),
            edd=date(2016, 1, 5),
            add=date(2016, 1, 6),
            date_opened=datetime(2015, 12, 10),
            date_modified=datetime(2016, 3, 12),
        )

        self._submit_ebf_form(
            form_date=datetime(2016, 2, 26),
            case_id=case_id,
            counsel_methods='no',
        )

        self._submit_ebf_form(
            form_date=datetime(2016, 3, 2),
            case_id=case_id,
            counsel_methods='yes',
        )

        query = self._rebuild_table_get_query_object()
        self.assertEqual(query.count(), 7)

        row = query.all()[1]
        self.assertEqual(row.month, date(2016, 1, 1))
        self.assertEqual(row.counsel_fp_methods, 0)

        row = query.all()[2]
        self.assertEqual(row.month, date(2016, 2, 1))
        self.assertEqual(row.counsel_fp_methods, 0)

        row = query.all()[3]
        self.assertEqual(row.month, date(2016, 3, 1))
        self.assertEqual(row.counsel_fp_methods, 1)

        row = query.all()[4]
        self.assertEqual(row.month, date(2016, 4, 1))
        self.assertEqual(row.counsel_fp_methods, 1)

    def test_bp_pnc_complete(self):
        case_id = uuid.uuid4().hex
        self._create_ccs_case(
            case_id=case_id,
            dob=date(1990, 1, 1),
            edd=date(2016, 2, 5),
            add=date(2016, 2, 25),
            date_opened=datetime(2015, 12, 10),
            date_modified=datetime(2016, 3, 12),
            bp1_date=date(2015, 12, 13),
            bp2_date=date(2016, 1, 9),
            bp3_date=date(2016, 2, 10),
            pnc1_date=date(2016, 3, 18),
        )

        query = self._rebuild_table_get_query_object()
        self.assertEqual(query.count(), 7)

        row = query.all()[0]
        self.assertEqual(row.month, date(2015, 12, 1))
        self.assertEqual(row.bp1_complete, 1)
        self.assertEqual(row.bp2_complete, 0)
        self.assertEqual(row.bp3_complete, 0)
        self.assertEqual(row.pnc_complete, 0)

        row = query.all()[1]
        self.assertEqual(row.month, date(2016, 1, 1))
        self.assertEqual(row.bp1_complete, 1)
        self.assertEqual(row.bp2_complete, 1)
        self.assertEqual(row.bp3_complete, 0)
        self.assertEqual(row.pnc_complete, 0)

        row = query.all()[2]
        self.assertEqual(row.month, date(2016, 2, 1))
        self.assertEqual(row.bp1_complete, 1)
        self.assertEqual(row.bp2_complete, 1)
        self.assertEqual(row.bp3_complete, 1)
        self.assertEqual(row.pnc_complete, 0)

        row = query.all()[3]
        self.assertEqual(row.month, date(2016, 3, 1))
        self.assertEqual(row.bp1_complete, 1)
        self.assertEqual(row.bp2_complete, 1)
        self.assertEqual(row.bp3_complete, 1)
        self.assertEqual(row.pnc_complete, 1)
