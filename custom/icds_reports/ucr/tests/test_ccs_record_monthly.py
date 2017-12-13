from __future__ import absolute_import
import uuid
from datetime import datetime, date
from xml.etree import cElementTree as ElementTree
from django.test import override_settings
import mock
from casexml.apps.case.const import CASE_INDEX_CHILD
from casexml.apps.case.mock import CaseStructure, CaseIndex
from corehq.apps.userreports.const import UCR_SQL_BACKEND
from custom.icds_reports.ucr.tests.base_test import BaseICDSDatasourceTest, add_element, mget_query_fake

XMNLS_BP_FORM = 'http://openrosa.org/formdesigner/2864010F-B1B1-4711-8C59-D5B2B81D65DB'
XMLNS_THR_FORM = 'http://openrosa.org/formdesigner/F1B73934-8B70-4CEE-B462-3E4C81F80E4A'
XMLNS_PNC_FORM = 'http://openrosa.org/formdesigner/D4A7ABD2-A7B8-431B-A88B-38245173B0AE'
XMLNS_EBF_FORM = 'http://openrosa.org/formdesigner/89097FB1-6C08-48BA-95B2-67BCF0C5091D'


@override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
@override_settings(OVERRIDE_UCR_BACKEND=UCR_SQL_BACKEND)
@mock.patch('custom.icds_reports.ucr.expressions.mget_query', mget_query_fake)
class TestCCSRecordDataSource(BaseICDSDatasourceTest):
    datasource_filename = 'ccs_record_cases_monthly_tableau2'

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
        add_element(meta, 'timeEnd', form_date.isoformat())
        form.append(meta)

        case = ElementTree.Element('case')
        case.attrib['date_modified'] = form_date.isoformat()
        case.attrib['case_id'] = case_id
        case.attrib['xmlns'] = 'http://commcarehq.org/case/transaction/v2'
        form.append(case)

        add_element(form, 'play_family_planning_vid', counsel_fp_vid)
        add_element(form, 'conceive', counsel_immediate_conception)

        bp1 = ElementTree.Element('bp1')
        add_element(bp1, 'using_ifa', using_ifa)
        if using_ifa == 'yes':
            add_element(bp1, 'ifa_last_seven_days', num_ifa_consumed_last_seven_days)
        add_element(bp1, 'anemia', anemia)
        add_element(bp1, 'eating_extra', extra_meal)
        add_element(bp1, 'resting', resting_during_pregnancy)
        form.append(bp1)

        bp2 = ElementTree.Element('bp2')
        add_element(bp2, 'immediate_breastfeeding', counsel_immediate_bf)
        add_element(bp2, 'play_birth_preparedness_vid', counsel_bp_vid)
        add_element(bp2, 'counsel_preparation', counsel_preparation)
        form.append(bp2)

        fp_group = ElementTree.Element('family_planning_group')
        add_element(fp_group, 'counsel_accessible_ppfp', counsel_accessible_postpartum_fp)
        form.append(fp_group)

        self._submit_form(form)

    def _submit_thr_rations_form(
            self, form_date, case_id, thr_given_mother='0', rations_distributed=0):

        form = ElementTree.Element('data')
        form.attrib['xmlns'] = XMLNS_THR_FORM
        form.attrib['xmlns:jrm'] = 'http://openrosa.org/jr/xforms'

        meta = ElementTree.Element('meta')
        add_element(meta, 'timeEnd', form_date.isoformat())
        form.append(meta)

        case = ElementTree.Element('case')
        case.attrib['date_modified'] = form_date.isoformat()
        case.attrib['case_id'] = case_id
        case.attrib['xmlns'] = 'http://commcarehq.org/case/transaction/v2'
        form.append(case)

        add_element(form, 'thr_given_mother', thr_given_mother)

        if thr_given_mother == '1':
            mother_thr = ElementTree.Element('mother_thr')
            add_element(mother_thr, 'days_ration_given_mother', rations_distributed)
            form.append(mother_thr)

        self._submit_form(form)

    def _submit_pnc_form(self, form_date, case_id, counsel_methods='no'):

        form = ElementTree.Element('data')
        form.attrib['xmlns'] = XMLNS_PNC_FORM
        form.attrib['xmlns:jrm'] = 'http://openrosa.org/jr/xforms'

        meta = ElementTree.Element('meta')
        add_element(meta, 'timeEnd', form_date.isoformat())
        form.append(meta)

        case = ElementTree.Element('case')
        case.attrib['date_modified'] = form_date.isoformat()
        case.attrib['case_id'] = case_id
        case.attrib['xmlns'] = 'http://commcarehq.org/case/transaction/v2'
        form.append(case)

        add_element(form, 'counsel_methods', counsel_methods)

        self._submit_form(form)

    def _submit_ebf_form(self, form_date, case_id, counsel_methods='no'):

        form = ElementTree.Element('data')
        form.attrib['xmlns'] = XMLNS_EBF_FORM
        form.attrib['xmlns:jrm'] = 'http://openrosa.org/jr/xforms'

        meta = ElementTree.Element('meta')
        add_element(meta, 'timeEnd', form_date.isoformat())
        form.append(meta)

        case = ElementTree.Element('case')
        case.attrib['date_modified'] = form_date.isoformat()
        case.attrib['case_id'] = case_id
        case.attrib['xmlns'] = 'http://commcarehq.org/case/transaction/v2'
        form.append(case)

        add_element(form, 'counsel_methods', counsel_methods)

        self._submit_form(form)

    def test_open_in_month(self):
        case_id = uuid.uuid4().hex
        self._create_ccs_case(
            case_id=case_id,
            dob=date(1990, 1, 1),
            edd=date(2016, 6, 2),
            date_opened=datetime(2016, 3, 10),
            date_modified=datetime(2016, 3, 12),
            closed=True,
        )

        cases = [
            (0, [('open_in_month', 0)]),
            (1, [('open_in_month', 1)]),
        ]
        self._run_iterative_monthly_test(case_id=case_id, cases=cases)

    def test_closed(self):
        case_id = uuid.uuid4().hex
        self._create_ccs_case(
            case_id=case_id,
            dob=date(1990, 1, 1),
            edd=date(2016, 6, 2),
            date_opened=datetime(2016, 1, 10),
            date_modified=datetime(2016, 1, 12),
            closed=True,
        )

        cases = []
        self._run_iterative_monthly_test(case_id=case_id, cases=cases)

    def test_alive_in_month(self):
        case_id = uuid.uuid4().hex
        self._create_ccs_case(
            case_id=case_id,
            dob=date(1990, 1, 1),
            edd=date(2016, 6, 2),
            date_opened=datetime(2016, 1, 10),
            date_modified=datetime(2016, 3, 12),
            date_death=date(2016, 3, 2),
        )

        cases = [
            (0, [('alive_in_month', 1)]),
            (1, [('alive_in_month', 1)]),
            (2, [('alive_in_month', 0)]),
        ]
        self._run_iterative_monthly_test(case_id=case_id, cases=cases)

    def test_demographic_data(self):
        case_id = uuid.uuid4().hex
        self._create_ccs_case(
            case_id=case_id,
            caste='sc',
            minority='yes',
            resident='yes',
            disabled='yes',
            dob=date(1990, 1, 1),
            edd=date(2016, 8, 10),
            date_opened=datetime(2016, 1, 10),
            date_modified=datetime(2016, 3, 12),
        )

        cases = [
            (0, [
                ('caste', 'sc'),
                ('disabled', 'yes'),
                ('minority', 'yes'),
                ('resident', 'yes'),
            ]),
            (1, [
                ('caste', 'sc'),
                ('disabled', 'yes'),
                ('minority', 'yes'),
                ('resident', 'yes'),
            ]),
            (2, [
                ('caste', 'sc'),
                ('disabled', 'yes'),
                ('minority', 'yes'),
                ('resident', 'yes'),
            ]),
        ]
        self._run_iterative_monthly_test(case_id=case_id, cases=cases)

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

        cases = [
            (0, [('num_rations_distributed', 11), ('rations_21_plus_distributed', 0)]),
            (1, [('num_rations_distributed', 21), ('rations_21_plus_distributed', 1)]),
            (2, [('num_rations_distributed', 0), ('rations_21_plus_distributed', 0)]),
        ]
        self._run_iterative_monthly_test(case_id=case_id, cases=cases)

    def test_lactating_post(self):
        case_id = uuid.uuid4().hex
        self._create_ccs_case(
            case_id=case_id,
            dob=date(1990, 1, 1),
            edd=date(2015, 9, 10),
            add=date(2015, 9, 12),
            date_opened=datetime(2015, 12, 10),
            date_modified=datetime(2016, 3, 12),
        )

        # no rows where ccs_status = other
        cases = [
            (0, [('pregnant', 0), ('lactating', 1), ('ccs_status', 'lactating')]),
            (1, [('pregnant', 0), ('lactating', 1), ('ccs_status', 'lactating')]),
        ]
        self._run_iterative_monthly_test(case_id=case_id, cases=cases)

    def test_preg_to_lactating(self):
        case_id = uuid.uuid4().hex
        self._create_ccs_case(
            case_id=case_id,
            dob=date(1990, 1, 1),
            edd=date(2016, 3, 4),
            add=date(2016, 3, 15),
            date_opened=datetime(2015, 12, 10),
            date_modified=datetime(2016, 3, 12),
        )

        cases = [
            (0, [('pregnant', 1), ('lactating', 0), ('ccs_status', 'pregnant')]),
            (1, [('pregnant', 0), ('lactating', 1), ('ccs_status', 'lactating')]),
            (2, [('pregnant', 0), ('lactating', 1), ('ccs_status', 'lactating')]),
        ]
        self._run_iterative_monthly_test(case_id=case_id, cases=cases)

    def test_pre_preg(self):
        case_id = uuid.uuid4().hex
        self._create_ccs_case(
            case_id=case_id,
            dob=date(1990, 1, 1),
            edd=date(2016, 9, 6),
            date_opened=datetime(2016, 3, 4),
            date_modified=datetime(2016, 3, 12),
        )

        cases = [
            (0, [('pregnant', 0), ('lactating', 0), ('ccs_status', 'other')]),
            (1, [('pregnant', 1), ('lactating', 0), ('ccs_status', 'pregnant')]),
            (2, [('pregnant', 1), ('lactating', 0), ('ccs_status', 'pregnant')]),
        ]
        self._run_iterative_monthly_test(case_id=case_id, cases=cases)

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

        cases = [
            (0, [('postnatal', 1)]),
            (1, [('postnatal', 1)]),
            (2, [('postnatal', 0)]),
        ]
        self._run_iterative_monthly_test(case_id=case_id, cases=cases)

    def test_tt_complete_none(self):
        case_id = uuid.uuid4().hex
        self._create_ccs_case(
            case_id=case_id,
            dob=date(1990, 1, 1),
            edd=date(2016, 6, 4),
            date_opened=datetime(2015, 12, 10),
            date_modified=datetime(2016, 3, 12),
        )

        cases = [
            (0, [('tetanus_complete', 0)]),
            (1, [('tetanus_complete', 0)]),
            (2, [('tetanus_complete', 0)]),
        ]
        self._run_iterative_monthly_test(case_id=case_id, cases=cases)

    def test_tt_complete(self):
        case_id = uuid.uuid4().hex
        self._create_ccs_case(
            case_id=case_id,
            dob=date(1990, 1, 1),
            edd=date(2016, 6, 4),
            date_opened=datetime(2015, 12, 10),
            date_modified=datetime(2016, 3, 12),
            tt_complete_date=date(2016, 3, 7)
        )

        cases = [
            (0, [('tetanus_complete', 0)]),
            (1, [('tetanus_complete', 1)]),
            (2, [('tetanus_complete', 1)]),
        ]
        self._run_iterative_monthly_test(case_id=case_id, cases=cases)

    def test_delivered_in_month(self):
        case_id = uuid.uuid4().hex
        self._create_ccs_case(
            case_id=case_id,
            dob=date(1990, 1, 1),
            edd=date(2016, 3, 4),
            add=date(2016, 3, 15),
            date_opened=datetime(2015, 12, 10),
            date_modified=datetime(2016, 3, 12),
        )

        cases = [
            (0, [('delivered_in_month', 0)]),
            (1, [('delivered_in_month', 1)]),
            (2, [('delivered_in_month', 0)]),
        ]
        self._run_iterative_monthly_test(case_id=case_id, cases=cases)

    def test_trimester_not_open(self):
        case_id = uuid.uuid4().hex
        self._create_ccs_case(
            case_id=case_id,
            dob=date(1990, 1, 1),
            edd=date(2016, 9, 6),
            date_opened=datetime(2016, 3, 3),
            date_modified=datetime(2016, 3, 12),
        )

        cases = [
            (0, [('trimester', None), ('trimester_2', 0), ('trimester_3', 0)]),
            (1, [('trimester', 2), ('trimester_2', 1), ('trimester_3', 0)]),
            (2, [('trimester', 2), ('trimester_2', 1), ('trimester_3', 0)]),
        ]
        self._run_iterative_monthly_test(case_id=case_id, cases=cases)

    def test_trimester_1_2(self):
        case_id = uuid.uuid4().hex
        self._create_ccs_case(
            case_id=case_id,
            dob=date(1990, 1, 1),
            edd=date(2016, 9, 6),
            date_opened=datetime(2016, 2, 3),
            date_modified=datetime(2016, 3, 12),
        )

        cases = [
            (0, [('trimester', 1), ('trimester_2', 0), ('trimester_3', 0)]),
            (1, [('trimester', 2), ('trimester_2', 1), ('trimester_3', 0)]),
            (2, [('trimester', 2), ('trimester_2', 1), ('trimester_3', 0)]),
        ]
        self._run_iterative_monthly_test(case_id=case_id, cases=cases)

    def test_trimester_3_none(self):
        case_id = uuid.uuid4().hex
        self._create_ccs_case(
            case_id=case_id,
            dob=date(1990, 1, 1),
            edd=date(2016, 3, 4),
            add=date(2016, 3, 15),
            date_opened=datetime(2015, 12, 10),
            date_modified=datetime(2016, 3, 12),
        )

        cases = [
            (0, [('trimester', 3), ('trimester_2', 0), ('trimester_3', 1)]),
            (1, [('trimester', None), ('trimester_2', 0), ('trimester_3', 0)]),
            (2, [('trimester', None), ('trimester_2', 0), ('trimester_3', 0)]),
        ]
        self._run_iterative_monthly_test(case_id=case_id, cases=cases)

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

        cases = [
            (0, [('anc1_received_at_delivery', 0),
                 ('anc2_received_at_delivery', 0),
                 ('anc3_received_at_delivery', 0),
                 ('anc4_received_at_delivery', 0)]),
            (1, [('anc1_received_at_delivery', 0),
                 ('anc2_received_at_delivery', 0),
                 ('anc3_received_at_delivery', 0),
                 ('anc4_received_at_delivery', 0)]),
            (2, [('anc1_received_at_delivery', 0),
                 ('anc2_received_at_delivery', 0),
                 ('anc3_received_at_delivery', 0),
                 ('anc4_received_at_delivery', 0)]),
        ]
        self._run_iterative_monthly_test(case_id=case_id, cases=cases)

    def test_anc1_at_delivery(self):
        case_id = uuid.uuid4().hex
        self._create_ccs_case(
            case_id=case_id,
            dob=date(1990, 1, 1),
            edd=date(2016, 3, 4),
            add=date(2016, 3, 15),
            date_opened=datetime(2015, 12, 10),
            date_modified=datetime(2016, 3, 12),
            num_anc_complete=1,
        )

        cases = [
            (0, [('anc1_received_at_delivery', 0),
                 ('anc2_received_at_delivery', 0),
                 ('anc3_received_at_delivery', 0),
                 ('anc4_received_at_delivery', 0)]),
            (1, [('anc1_received_at_delivery', 1),
                 ('anc2_received_at_delivery', 0),
                 ('anc3_received_at_delivery', 0),
                 ('anc4_received_at_delivery', 0)]),
            (2, [('anc1_received_at_delivery', 0),
                 ('anc2_received_at_delivery', 0),
                 ('anc3_received_at_delivery', 0),
                 ('anc4_received_at_delivery', 0)]),
        ]
        self._run_iterative_monthly_test(case_id=case_id, cases=cases)

    def test_anc2_at_delivery(self):
        case_id = uuid.uuid4().hex
        self._create_ccs_case(
            case_id=case_id,
            dob=date(1990, 1, 1),
            edd=date(2016, 3, 4),
            add=date(2016, 3, 15),
            date_opened=datetime(2015, 12, 10),
            date_modified=datetime(2016, 3, 12),
            num_anc_complete=2,
        )

        cases = [
            (0, [('anc1_received_at_delivery', 0),
                 ('anc2_received_at_delivery', 0),
                 ('anc3_received_at_delivery', 0),
                 ('anc4_received_at_delivery', 0)]),
            (1, [('anc1_received_at_delivery', 1),
                 ('anc2_received_at_delivery', 1),
                 ('anc3_received_at_delivery', 0),
                 ('anc4_received_at_delivery', 0)]),
            (2, [('anc1_received_at_delivery', 0),
                 ('anc2_received_at_delivery', 0),
                 ('anc3_received_at_delivery', 0),
                 ('anc4_received_at_delivery', 0)]),
        ]
        self._run_iterative_monthly_test(case_id=case_id, cases=cases)

    def test_anc3_at_delivery(self):
        case_id = uuid.uuid4().hex
        self._create_ccs_case(
            case_id=case_id,
            dob=date(1990, 1, 1),
            edd=date(2016, 3, 4),
            add=date(2016, 3, 15),
            date_opened=datetime(2015, 12, 10),
            date_modified=datetime(2016, 3, 12),
            num_anc_complete=3,
        )

        cases = [
            (0, [('anc1_received_at_delivery', 0),
                 ('anc2_received_at_delivery', 0),
                 ('anc3_received_at_delivery', 0),
                 ('anc4_received_at_delivery', 0)]),
            (1, [('anc1_received_at_delivery', 1),
                 ('anc2_received_at_delivery', 1),
                 ('anc3_received_at_delivery', 1),
                 ('anc4_received_at_delivery', 0)]),
            (2, [('anc1_received_at_delivery', 0),
                 ('anc2_received_at_delivery', 0),
                 ('anc3_received_at_delivery', 0),
                 ('anc4_received_at_delivery', 0)]),
        ]
        self._run_iterative_monthly_test(case_id=case_id, cases=cases)

    def test_anc4_at_delivery(self):
        case_id = uuid.uuid4().hex
        self._create_ccs_case(
            case_id=case_id,
            dob=date(1990, 1, 1),
            edd=date(2016, 3, 4),
            add=date(2016, 3, 15),
            date_opened=datetime(2015, 12, 10),
            date_modified=datetime(2016, 3, 12),
            num_anc_complete=4,
        )

        cases = [
            (0, [('anc1_received_at_delivery', 0),
                 ('anc2_received_at_delivery', 0),
                 ('anc3_received_at_delivery', 0),
                 ('anc4_received_at_delivery', 0)]),
            (1, [('anc1_received_at_delivery', 1),
                 ('anc2_received_at_delivery', 1),
                 ('anc3_received_at_delivery', 1),
                 ('anc4_received_at_delivery', 1)]),
            (2, [('anc1_received_at_delivery', 0),
                 ('anc2_received_at_delivery', 0),
                 ('anc3_received_at_delivery', 0),
                 ('anc4_received_at_delivery', 0)]),
        ]
        self._run_iterative_monthly_test(case_id=case_id, cases=cases)

    def test_reg_trimester_3_at_delivery(self):
        case_id = uuid.uuid4().hex
        self._create_ccs_case(
            case_id=case_id,
            dob=date(1990, 1, 1),
            edd=date(2016, 3, 4),
            add=date(2016, 3, 15),
            date_opened=datetime(2016, 2, 10),
            date_modified=datetime(2016, 3, 12),
        )

        cases = [
            (0, [('registration_trimester_at_delivery', None)]),
            (1, [('registration_trimester_at_delivery', 3)]),
            (2, [('registration_trimester_at_delivery', None)]),
        ]
        self._run_iterative_monthly_test(case_id=case_id, cases=cases)

    def test_reg_trimester_2_at_delivery(self):
        case_id = uuid.uuid4().hex
        self._create_ccs_case(
            case_id=case_id,
            dob=date(1990, 1, 1),
            edd=date(2016, 3, 13),
            add=date(2016, 3, 15),
            date_opened=datetime(2015, 10, 10),
            date_modified=datetime(2016, 3, 12),
        )

        cases = [
            (0, [('registration_trimester_at_delivery', None)]),
            (1, [('registration_trimester_at_delivery', 2)]),
            (2, [('registration_trimester_at_delivery', None)]),
        ]
        self._run_iterative_monthly_test(case_id=case_id, cases=cases)

    def test_reg_trimester_1_at_delivery(self):
        case_id = uuid.uuid4().hex
        self._create_ccs_case(
            case_id=case_id,
            dob=date(1990, 1, 1),
            edd=date(2016, 3, 10),
            add=date(2016, 3, 8),
            date_opened=datetime(2015, 8, 10),
            date_modified=datetime(2016, 3, 12),
        )

        cases = [
            (0, [('registration_trimester_at_delivery', None)]),
            (1, [('registration_trimester_at_delivery', 1)]),
            (2, [('registration_trimester_at_delivery', None)]),
        ]
        self._run_iterative_monthly_test(case_id=case_id, cases=cases)

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
            form_date=datetime(2016, 3, 2),
            case_id=case_id
        )

        cases = [
            (0, [('bp_visited_in_month', 0)]),
            (1, [('bp_visited_in_month', 1)]),
            (2, [('bp_visited_in_month', 0)]),
        ]
        self._run_iterative_monthly_test(case_id=case_id, cases=cases)

    def test_pnc_in_month(self):
        case_id = uuid.uuid4().hex
        self._create_ccs_case(
            case_id=case_id,
            dob=date(1990, 1, 1),
            edd=date(2016, 2, 5),
            add=date(2016, 2, 24),
            date_opened=datetime(2015, 12, 10),
            date_modified=datetime(2016, 3, 12),
        )

        self._submit_pnc_form(
            form_date=datetime(2016, 3, 2),
            case_id=case_id
        )

        cases = [
            (0, [('pnc_visited_in_month', 0)]),
            (1, [('pnc_visited_in_month', 1)]),
            (2, [('pnc_visited_in_month', 0)]),
        ]
        self._run_iterative_monthly_test(case_id=case_id, cases=cases)

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

        cases = [
            (0, [('using_ifa', 1),
                 ('ifa_consumed_last_seven_days', 1),
                 ('extra_meal', 1),
                 ('resting_during_pregnancy', 1)]),
            (1, [('using_ifa', 0),
                 ('ifa_consumed_last_seven_days', 0),
                 ('extra_meal', 0),
                 ('resting_during_pregnancy', 0)]),
            (2, [('using_ifa', 0),
                 ('ifa_consumed_last_seven_days', 0),
                 ('extra_meal', 0),
                 ('resting_during_pregnancy', 0)]),
        ]
        self._run_iterative_monthly_test(case_id=case_id, cases=cases)

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

        cases = [
            (0, [('counsel_immediate_bf', 0),
                 ('counsel_bp_vid', 0),
                 ('counsel_preparation', 0),
                 ('counsel_fp_vid', 0),
                 ('counsel_immediate_conception', 0),
                 ('counsel_accessible_postpartum_fp', 0)]),
            (1, [('counsel_immediate_bf', 1),
                 ('counsel_bp_vid', 1),
                 ('counsel_preparation', 1),
                 ('counsel_fp_vid', 1),
                 ('counsel_immediate_conception', 1),
                 ('counsel_accessible_postpartum_fp', 1)]),
            (2, [('counsel_immediate_bf', 1),
                 ('counsel_bp_vid', 1),
                 ('counsel_preparation', 1),
                 ('counsel_fp_vid', 1),
                 ('counsel_immediate_conception', 1),
                 ('counsel_accessible_postpartum_fp', 1)]),
        ]
        self._run_iterative_monthly_test(case_id=case_id, cases=cases)

    def test_anemic_unknown(self):
        case_id = uuid.uuid4().hex
        self._create_ccs_case(
            case_id=case_id,
            dob=date(1990, 1, 1),
            edd=date(2016, 5, 10),
            date_opened=datetime(2015, 12, 10),
            date_modified=datetime(2016, 3, 12),
        )

        cases = [
            (0, [('anemic_unknown', 1),
                 ('anemic_normal', 0),
                 ('anemic_moderate', 0),
                 ('anemic_severe', 0)]),
            (1, [('anemic_unknown', 1),
                 ('anemic_normal', 0),
                 ('anemic_moderate', 0),
                 ('anemic_severe', 0)]),
            (2, [('anemic_unknown', 1),
                 ('anemic_normal', 0),
                 ('anemic_moderate', 0),
                 ('anemic_severe', 0)]),
        ]
        self._run_iterative_monthly_test(case_id=case_id, cases=cases)

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
            form_date=datetime(2016, 3, 9),
            case_id=case_id,
            anemia='severe',
        )
        self._submit_bp_form(
            form_date=datetime(2016, 3, 10),
            case_id=case_id,
            anemia='normal',
        )
        self._submit_bp_form(
            form_date=datetime(2016, 3, 14),
            case_id=case_id,
        )

        cases = [
            (0, [('anemic_unknown', 1),
                 ('anemic_normal', 0),
                 ('anemic_moderate', 0),
                 ('anemic_severe', 0)]),
            (1, [('anemic_unknown', 0),
                 ('anemic_normal', 1),
                 ('anemic_moderate', 0),
                 ('anemic_severe', 0)]),
            (2, [('anemic_unknown', 0),
                 ('anemic_normal', 1),
                 ('anemic_moderate', 0),
                 ('anemic_severe', 0)]),
        ]
        self._run_iterative_monthly_test(case_id=case_id, cases=cases)

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
            form_date=datetime(2016, 3, 9),
            case_id=case_id,
            anemia='severe',
        )
        self._submit_bp_form(
            form_date=datetime(2016, 3, 10),
            case_id=case_id,
            anemia='moderate',
        )
        self._submit_bp_form(
            form_date=datetime(2016, 3, 14),
            case_id=case_id,
        )

        cases = [
            (0, [('anemic_unknown', 1),
                 ('anemic_normal', 0),
                 ('anemic_moderate', 0),
                 ('anemic_severe', 0)]),
            (1, [('anemic_unknown', 0),
                 ('anemic_normal', 0),
                 ('anemic_moderate', 1),
                 ('anemic_severe', 0)]),
            (2, [('anemic_unknown', 0),
                 ('anemic_normal', 0),
                 ('anemic_moderate', 1),
                 ('anemic_severe', 0)]),
        ]
        self._run_iterative_monthly_test(case_id=case_id, cases=cases)

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
            form_date=datetime(2016, 3, 9),
            case_id=case_id,
            anemia='normal',
        )
        self._submit_bp_form(
            form_date=datetime(2016, 3, 10),
            case_id=case_id,
            anemia='severe',
        )
        self._submit_bp_form(
            form_date=datetime(2016, 3, 15),
            case_id=case_id,
        )

        cases = [
            (0, [('anemic_unknown', 1),
                 ('anemic_normal', 0),
                 ('anemic_moderate', 0),
                 ('anemic_severe', 0)]),
            (1, [('anemic_unknown', 0),
                 ('anemic_normal', 0),
                 ('anemic_moderate', 0),
                 ('anemic_severe', 1)]),
            (2, [('anemic_unknown', 0),
                 ('anemic_normal', 0),
                 ('anemic_moderate', 0),
                 ('anemic_severe', 1)]),
        ]
        self._run_iterative_monthly_test(case_id=case_id, cases=cases)

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

        cases = [
            (0, [('counsel_fp_methods', 0)]),
            (1, [('counsel_fp_methods', 1)]),
            (2, [('counsel_fp_methods', 1)]),
        ]
        self._run_iterative_monthly_test(case_id=case_id, cases=cases)

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

        cases = [
            (0, [('counsel_fp_methods', 0)]),
            (1, [('counsel_fp_methods', 1)]),
            (2, [('counsel_fp_methods', 1)]),
        ]
        self._run_iterative_monthly_test(case_id=case_id, cases=cases)

    def test_bp_complete(self):
        case_id = uuid.uuid4().hex
        self._create_ccs_case(
            case_id=case_id,
            dob=date(1990, 1, 1),
            edd=date(2016, 2, 5),
            add=date(2016, 5, 2),
            date_opened=datetime(2015, 12, 10),
            date_modified=datetime(2016, 3, 12),
            bp1_date=date(2015, 2, 13),
            bp2_date=date(2016, 3, 9),
            bp3_date=date(2016, 4, 10),
        )

        cases = [
            (0, [('bp1_complete', 1),
                 ('bp2_complete', 0),
                 ('bp3_complete', 0),
                 ('pnc_complete', 0)]),
            (1, [('bp1_complete', 1),
                 ('bp2_complete', 1),
                 ('bp3_complete', 0),
                 ('pnc_complete', 0)]),
            (2, [('bp1_complete', 1),
                 ('bp2_complete', 1),
                 ('bp3_complete', 1),
                 ('pnc_complete', 0)]),
        ]
        self._run_iterative_monthly_test(case_id=case_id, cases=cases)

    def test_pnc_complete(self):
        case_id = uuid.uuid4().hex
        self._create_ccs_case(
            case_id=case_id,
            dob=date(1990, 1, 1),
            edd=date(2016, 2, 5),
            add=date(2016, 3, 2),
            date_opened=datetime(2015, 12, 10),
            date_modified=datetime(2016, 3, 12),
            bp1_date=date(2015, 12, 13),
            bp2_date=date(2016, 1, 9),
            bp3_date=date(2016, 2, 10),
            pnc1_date=date(2016, 3, 18),
        )

        cases = [
            (0, [('bp1_complete', 1),
                 ('bp2_complete', 1),
                 ('bp3_complete', 1),
                 ('pnc_complete', 0)]),
            (1, [('bp1_complete', 0),
                 ('bp2_complete', 0),
                 ('bp3_complete', 0),
                 ('pnc_complete', 1)]),
            (2, [('bp1_complete', 0),
                 ('bp2_complete', 0),
                 ('bp3_complete', 0),
                 ('pnc_complete', 0)]),
        ]
        self._run_iterative_monthly_test(case_id=case_id, cases=cases)
