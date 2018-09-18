from __future__ import absolute_import
from __future__ import unicode_literals
from datetime import datetime, date
import uuid
from xml.etree import cElementTree as ElementTree

from dateutil.relativedelta import relativedelta
from django.test import override_settings
import mock

from casexml.apps.case.const import CASE_INDEX_CHILD
from casexml.apps.case.mock import CaseStructure, CaseIndex
from custom.icds_reports.ucr.tests.base_test import BaseICDSDatasourceTest, add_element, mget_query_fake

XMLNS_DELIVERY_FORM = 'http://openrosa.org/formdesigner/376FA2E1-6FD1-4C9E-ACB4-E046038CD5E2'
XMLNS_GMP_FORM = 'http://openrosa.org/formdesigner/b183124a25f2a0ceab266e4564d3526199ac4d75'

NUTRITION_STATUS_NORMAL = "green"
NUTRITION_STATUS_MODERATE = "yellow"
NUTRITION_STATUS_SEVERE = "red"


@override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
@mock.patch('custom.icds_reports.ucr.expressions.mget_query', mget_query_fake)
class TestChildHealthDataSource(BaseICDSDatasourceTest):
    datasource_filename = 'child_health_cases_monthly_tableau2'

    def _create_case(
            self, case_id, dob,
            caste='st', minority='no', resident='yes', disabled='no',
            sex='F', date_death=None, breastfed_within_first=None, immun_one_year_date=None,
            low_birth_weight=None,
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

        mother_case = CaseStructure(
            case_id='m-' + case_id,
            attrs={
                'case_type': 'person',
                'create': True,
                'close': closed,
                'date_opened': date_opened - relativedelta(years=20),
                'date_modified': date_modified,
                'update': dict(
                    resident=resident,
                    sex=sex,
                    disabled=disabled,
                    dob=dob - relativedelta(years=20),
                )
            },
            indices=[CaseIndex(
                household_case,
                identifier='parent',
                relationship=CASE_INDEX_CHILD,
                related_type=household_case.attrs['case_type'],
            )],
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
                )
            },
            indices=[
                CaseIndex(
                    household_case,
                    identifier='parent',
                    relationship=CASE_INDEX_CHILD,
                    related_type=household_case.attrs['case_type'],
                ),
                CaseIndex(
                    mother_case,
                    identifier='mother',
                    relationship=CASE_INDEX_CHILD,
                    related_type=mother_case.attrs['case_type'],
                ),
            ],
        )

        child_health_case = CaseStructure(
            case_id=case_id,
            attrs={
                'case_type': 'child_health',
                'create': True,
                'close': closed,
                'date_opened': date_opened,
                'date_modified': date_modified,
                'update': dict(
                    breastfed_within_first=breastfed_within_first,
                    low_birth_weight=low_birth_weight,
                )
            },
            indices=[CaseIndex(
                person_case,
                identifier='parent',
                relationship=CASE_INDEX_CHILD,
                related_type=person_case.attrs['case_type'],
            )],
        )

        child_task_case = CaseStructure(
            case_id='t-' + case_id,
            attrs={
                'case_type': 'tasks',
                'create': True,
                'close': closed,
                'date_opened': date_opened,
                'date_modified': date_modified,
                'update': dict(
                    immun_one_year_date=immun_one_year_date,
                    tasks_type='child',
                )
            },
            indices=[CaseIndex(
                child_health_case,
                identifier='parent',
                relationship=CASE_INDEX_CHILD,
                related_type=child_health_case.attrs['case_type'],
            )],
        )

        self.casefactory.create_or_update_cases([child_task_case])

    def _submit_gmp_form(
            self, form_date, case_id, nutrition_status=None):

        form = ElementTree.Element('data')
        form.attrib['xmlns'] = XMLNS_GMP_FORM
        form.attrib['xmlns:jrm'] = 'http://openrosa.org/jr/xforms'

        meta = ElementTree.Element('meta')
        add_element(meta, 'timeEnd', form_date.isoformat())
        form.append(meta)

        case = ElementTree.Element('case')
        case.attrib['date_modified'] = form_date.isoformat()
        case.attrib['case_id'] = case_id
        case.attrib['xmlns'] = 'http://commcarehq.org/case/transaction/v2'
        if nutrition_status is not None:
            case_update = ElementTree.Element('update')
            add_element(case_update, 'zscore_grading_wfa', nutrition_status)
            case.append(case_update)
        form.append(case)
        add_element(form, 'zscore_grading_wfa', nutrition_status)

        self._submit_form(form)

    def _submit_delivery_form(
            self, form_date, case_id, nutrition_status=None, case_id_2=None):

        form = ElementTree.Element('data')
        form.attrib['xmlns'] = XMLNS_DELIVERY_FORM
        form.attrib['xmlns:jrm'] = 'http://openrosa.org/jr/xforms'

        meta = ElementTree.Element('meta')
        add_element(meta, 'timeEnd', form_date.isoformat())
        form.append(meta)

        child_repeat1 = ElementTree.Element('child')
        child_open_child_health_repeat1 = ElementTree.Element('case_open_child_health_3')
        case_repeat1 = ElementTree.Element('case')
        case_repeat1.attrib['date_modified'] = form_date.isoformat()
        case_repeat1.attrib['case_id'] = case_id
        case_repeat1.attrib['xmlns'] = 'http://commcarehq.org/case/transaction/v2'
        if nutrition_status is not None:
            case_update_repeat1 = ElementTree.Element('update')
            add_element(case_update_repeat1, 'zscore_grading_wfa', nutrition_status)
            case_repeat1.append(case_update_repeat1)
        child_open_child_health_repeat1.append(case_repeat1)
        child_repeat1.append(child_open_child_health_repeat1)
        add_element(child_repeat1, 'zscore_grading_wfa', nutrition_status)
        form.append(child_repeat1)

        if case_id_2 is not None:
            child_repeat2 = ElementTree.Element('child')
            child_open_child_health_repeat2 = ElementTree.Element('case_open_child_health_3')
            case_repeat2 = ElementTree.Element('case')
            case_repeat2.attrib['date_modified'] = form_date.isoformat()
            case_repeat2.attrib['case_id'] = case_id_2
            case_repeat2.attrib['xmlns'] = 'http://commcarehq.org/case/transaction/v2'
            case_update_repeat2 = ElementTree.Element('update')
            add_element(case_update_repeat2, 'zscore_grading_wfa', nutrition_status)
            case_repeat2.append(case_update_repeat2)
            child_open_child_health_repeat2.append(case_repeat2)
            child_repeat2.append(child_open_child_health_repeat2)
            add_element(child_repeat2, 'zscore_grading_wfa', NUTRITION_STATUS_SEVERE)
            form.append(child_repeat2)

        self._submit_form(form)

    def test_demographic_data(self):
        case_id = uuid.uuid4().hex
        self._create_case(
            case_id=case_id,
            caste='sc',
            minority='yes',
            resident='yes',
            disabled='yes',
            dob=date(1990, 1, 1),
            sex='M',
            date_opened=datetime(2015, 1, 10),
            date_modified=datetime(2016, 3, 12),
        )

        cases = [
            (0, [
                ('caste', 'sc'),
                ('disabled', 'yes'),
                ('minority', 'yes'),
                ('resident', 'yes'),
                ('sex', 'M'),
            ]),
            (1, [
                ('caste', 'sc'),
                ('disabled', 'yes'),
                ('minority', 'yes'),
                ('resident', 'yes'),
                ('sex', 'M'),
            ]),
            (2, [
                ('caste', 'sc'),
                ('disabled', 'yes'),
                ('minority', 'yes'),
                ('resident', 'yes'),
                ('sex', 'M'),
            ]),
        ]
        self._run_iterative_monthly_test(case_id=case_id, cases=cases)

    def test_open_in_month(self):
        case_id = uuid.uuid4().hex
        self._create_case(
            case_id=case_id,
            dob=date(2014, 1, 1),
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
        self._create_case(
            case_id=case_id,
            dob=date(2014, 1, 1),
            date_opened=datetime(2016, 1, 10),
            date_modified=datetime(2016, 1, 12),
            closed=True,
        )

        cases = []
        self._run_iterative_monthly_test(case_id=case_id, cases=cases)

    def test_alive_in_month(self):
        case_id = uuid.uuid4().hex
        self._create_case(
            case_id=case_id,
            dob=date(2014, 1, 1),
            date_opened=datetime(2016, 1, 10),
            date_modified=datetime(2016, 3, 12),
            date_death=date(2016, 3, 10),
        )

        cases = [
            (0, [('alive_in_month', 1)]),
            (1, [('alive_in_month', 1)]),
            (2, [('alive_in_month', 0)]),
        ]
        self._run_iterative_monthly_test(case_id=case_id, cases=cases)

    def test_valid_in_month(self):
        case_id = uuid.uuid4().hex
        self._create_case(
            case_id=case_id,
            dob=date(2014, 1, 15),
            date_opened=datetime(2014, 1, 15),
            date_modified=datetime(2016, 3, 12),
            date_death=date(2016, 3, 10),
        )

        cases = [
            (0, [('valid_in_month', 1)]),
            (1, [('valid_in_month', 1)]),
            (2, [('valid_in_month', 0)]),
        ]
        self._run_iterative_monthly_test(case_id=case_id, cases=cases)

    def test_age_in_months(self):
        case_id = uuid.uuid4().hex
        self._create_case(
            case_id=case_id,
            dob=date(2012, 1, 15),
            date_opened=datetime(2012, 1, 15),
            date_modified=datetime(2016, 3, 12),
        )

        cases = [
            (0, [('age_in_months', 49)]),
            (1, [('age_in_months', 50)]),
            (2, [('age_in_months', 51)]),
        ]
        self._run_iterative_monthly_test(case_id=case_id, cases=cases)

    def test_age_tranche_0_to_6(self):
        case_id = uuid.uuid4().hex
        self._create_case(
            case_id=case_id,
            dob=date(2016, 2, 15),
            date_opened=datetime(2015, 2, 15),
            date_modified=datetime(2016, 3, 12),
        )

        cases = [
            (0, [('age_tranche', 0)]),
            (1, [('age_tranche', 6)]),
            (2, [('age_tranche', 6)]),
        ]
        self._run_iterative_monthly_test(case_id=case_id, cases=cases)

    def test_age_tranche_6_to_12(self):
        case_id = uuid.uuid4().hex
        self._create_case(
            case_id=case_id,
            dob=date(2015, 8, 12),
            date_opened=datetime(2015, 8, 12),
            date_modified=datetime(2016, 3, 12),
        )

        cases = [
            (0, [('age_tranche', 6)]),
            (1, [('age_tranche', 12)]),
            (2, [('age_tranche', 12)]),
        ]
        self._run_iterative_monthly_test(case_id=case_id, cases=cases)

    def test_age_tranche_12_to_24(self):
        case_id = uuid.uuid4().hex
        self._create_case(
            case_id=case_id,
            dob=date(2015, 2, 12),
            date_opened=datetime(2015, 2, 12),
            date_modified=datetime(2016, 3, 12),
        )

        cases = [
            (0, [('age_tranche', 12)]),
            (1, [('age_tranche', 24)]),
            (2, [('age_tranche', 24)]),
        ]
        self._run_iterative_monthly_test(case_id=case_id, cases=cases)

    def test_age_tranche_24_to_36(self):
        case_id = uuid.uuid4().hex
        self._create_case(
            case_id=case_id,
            dob=date(2014, 2, 12),
            date_opened=datetime(2014, 2, 12),
            date_modified=datetime(2016, 3, 12),
        )

        cases = [
            (0, [('age_tranche', 24)]),
            (1, [('age_tranche', 36)]),
            (2, [('age_tranche', 36)]),
        ]
        self._run_iterative_monthly_test(case_id=case_id, cases=cases)

    def test_age_tranche_36_to_48(self):
        case_id = uuid.uuid4().hex
        self._create_case(
            case_id=case_id,
            dob=date(2013, 2, 12),
            date_opened=datetime(2013, 2, 12),
            date_modified=datetime(2016, 3, 12),
        )

        cases = [
            (0, [('age_tranche', 36)]),
            (1, [('age_tranche', 48)]),
            (2, [('age_tranche', 48)]),
        ]
        self._run_iterative_monthly_test(case_id=case_id, cases=cases)

    def test_age_tranche_48_to_60(self):
        case_id = uuid.uuid4().hex
        self._create_case(
            case_id=case_id,
            dob=date(2012, 2, 12),
            date_opened=datetime(2012, 2, 12),
            date_modified=datetime(2016, 3, 12),
        )

        cases = [
            (0, [('age_tranche', 48)]),
            (1, [('age_tranche', 60)]),
            (2, [('age_tranche', 60)]),
        ]
        self._run_iterative_monthly_test(case_id=case_id, cases=cases)

    def test_age_tranche_60_to_72(self):
        case_id = uuid.uuid4().hex
        self._create_case(
            case_id=case_id,
            dob=date(2011, 2, 12),
            date_opened=datetime(2011, 2, 12),
            date_modified=datetime(2016, 3, 12),
        )

        cases = [
            (0, [('age_tranche', 60)]),
            (1, [('age_tranche', 72)]),
            (2, [('age_tranche', 72)]),
        ]
        self._run_iterative_monthly_test(case_id=case_id, cases=cases)

    def test_age_tranche_72_to_null(self):
        case_id = uuid.uuid4().hex
        self._create_case(
            case_id=case_id,
            dob=date(2010, 2, 12),
            date_opened=datetime(2010, 2, 12),
            date_modified=datetime(2016, 3, 12),
        )

        cases = [
            (0, [('age_tranche', 72)]),
            (1, [('age_tranche', None)]),
            (2, [('age_tranche', None)]),
        ]
        self._run_iterative_monthly_test(case_id=case_id, cases=cases)

    def test_wer_eligible(self):
        case_id = uuid.uuid4().hex
        self._create_case(
            case_id=case_id,
            dob=date(2011, 3, 12),
            date_opened=datetime(2011, 3, 14),
            date_modified=datetime(2016, 3, 12),
        )

        # Not eligible after 5 years old
        cases = [
            (0, [('wer_eligible', 1)]),
            (1, [('wer_eligible', 1)]),
            (2, [('wer_eligible', 0)]),
        ]
        self._run_iterative_monthly_test(case_id=case_id, cases=cases)

    def test_thr_eligible_6mo(self):
        case_id = uuid.uuid4().hex
        self._create_case(
            case_id=case_id,
            dob=date(2015, 9, 12),
            date_opened=datetime(2015, 9, 1),
            date_modified=datetime(2016, 3, 12),
        )

        # Not eligible before 6 months old
        cases = [
            (0, [('thr_eligible', 0)]),
            (1, [('thr_eligible', 1)]),
            (2, [('thr_eligible', 1)]),
        ]
        self._run_iterative_monthly_test(case_id=case_id, cases=cases)

    def test_thr_eligible_36mo(self):
        case_id = uuid.uuid4().hex
        self._create_case(
            case_id=case_id,
            dob=date(2013, 3, 12),
            date_opened=datetime(2013, 3, 14),
            date_modified=datetime(2016, 3, 12),
        )

        # Not eligible after 36 months old
        cases = [
            (0, [('thr_eligible', 1)]),
            (1, [('thr_eligible', 1)]),
            (2, [('thr_eligible', 0)]),
        ]
        self._run_iterative_monthly_test(case_id=case_id, cases=cases)

    def test_ebf_eligible(self):
        case_id = uuid.uuid4().hex
        self._create_case(
            case_id=case_id,
            dob=date(2015, 9, 12),
            date_opened=datetime(2015, 9, 1),
            date_modified=datetime(2016, 3, 12),
        )

        # Only eligible before 6 months old
        cases = [
            (0, [('ebf_eligible', 1)]),
            (1, [('ebf_eligible', 1)]),
            (2, [('ebf_eligible', 0)]),
        ]
        self._run_iterative_monthly_test(case_id=case_id, cases=cases)

    def test_cf_eligible_6mo(self):
        case_id = uuid.uuid4().hex
        self._create_case(
            case_id=case_id,
            dob=date(2015, 9, 12),
            date_opened=datetime(2015, 9, 1),
            date_modified=datetime(2016, 3, 12),
        )

        # Only eligible after 6 months old
        cases = [
            (0, [('cf_eligible', 0)]),
            (1, [('cf_eligible', 1)]),
            (2, [('cf_eligible', 1)]),
        ]
        self._run_iterative_monthly_test(case_id=case_id, cases=cases)

    def test_cf_eligible_24mo(self):
        case_id = uuid.uuid4().hex
        self._create_case(
            case_id=case_id,
            dob=date(2014, 2, 12),
            date_opened=datetime(2013, 2, 14),
            date_modified=datetime(2016, 3, 12),
        )

        # Only eligible before 24 months old
        cases = [
            (0, [('cf_eligible', 1)]),
            (1, [('cf_eligible', 0)]),
            (2, [('cf_eligible', 0)]),
        ]
        self._run_iterative_monthly_test(case_id=case_id, cases=cases)

    def test_pse_eligible_36mo(self):
        case_id = uuid.uuid4().hex
        self._create_case(
            case_id=case_id,
            dob=date(2013, 3, 12),
            date_opened=datetime(2013, 3, 14),
            date_modified=datetime(2016, 3, 12),
        )

        # Only eligible after 36 months old
        cases = [
            (0, [('pse_eligible', 0)]),
            (1, [('pse_eligible', 1)]),
            (2, [('pse_eligible', 1)]),
        ]
        self._run_iterative_monthly_test(case_id=case_id, cases=cases)

    def test_pse_eligible_72mo(self):
        case_id = uuid.uuid4().hex
        self._create_case(
            case_id=case_id,
            dob=date(2010, 3, 12),
            date_opened=datetime(2010, 3, 12),
            date_modified=datetime(2016, 3, 12),
        )

        # Only eligible before 72 months old
        cases = [
            (0, [('pse_eligible', 1)]),
            (1, [('pse_eligible', 1)]),
            (2, [('pse_eligible', 0)]),
        ]
        self._run_iterative_monthly_test(case_id=case_id, cases=cases)

    def test_nutrition_status_delivery(self):
        case_id = uuid.uuid4().hex
        case_id_2 = uuid.uuid4().hex
        self._create_case(
            case_id=case_id,
            dob=date(2016, 1, 1),
            date_opened=datetime(2016, 1, 10),
            date_modified=datetime(2016, 3, 12),
        )
        self._create_case(
            case_id=case_id_2,
            dob=date(2016, 1, 1),
            date_opened=datetime(2016, 1, 10),
            date_modified=datetime(2016, 3, 12),
        )

        self._submit_delivery_form(
            form_date=datetime(2016, 1, 10),
            case_id=case_id,
            nutrition_status=NUTRITION_STATUS_MODERATE,
            case_id_2=case_id_2,
        ),
        self._submit_gmp_form(
            form_date=datetime(2016, 3, 4),
            case_id=case_id,
            nutrition_status=NUTRITION_STATUS_SEVERE
        )

        cases = [
            (0, [('nutrition_status_last_recorded', "moderately_underweight"),
                 ('current_month_nutrition_status', "unweighed"),
                 ('nutrition_status_severely_underweight', 0),
                 ('nutrition_status_moderately_underweight', 1),
                 ('nutrition_status_normal', 0),
                 ('nutrition_status_weighed', 0),
                 ('nutrition_status_unweighed', 1)],
             ),
            (1, [('nutrition_status_last_recorded', "severely_underweight"),
                 ('current_month_nutrition_status', "severely_underweight"),
                 ('nutrition_status_severely_underweight', 1),
                 ('nutrition_status_moderately_underweight', 0),
                 ('nutrition_status_normal', 0),
                 ('nutrition_status_weighed', 1),
                 ('nutrition_status_unweighed', 0)],
             ),
            (2, [('nutrition_status_last_recorded', "severely_underweight"),
                 ('current_month_nutrition_status', "unweighed"),
                 ('nutrition_status_severely_underweight', 1),
                 ('nutrition_status_moderately_underweight', 0),
                 ('nutrition_status_normal', 0),
                 ('nutrition_status_weighed', 0),
                 ('nutrition_status_unweighed', 1)],
             ),
        ]
        self._run_iterative_monthly_test(case_id=case_id, cases=cases)

    def test_nutrition_status_gmp(self):
        case_id = uuid.uuid4().hex
        self._create_case(
            case_id=case_id,
            dob=date(2015, 1, 1),
            date_opened=datetime(2015, 1, 10),
            date_modified=datetime(2016, 3, 12),
        )

        self._submit_gmp_form(
            form_date=datetime(2016, 1, 5),
            case_id=case_id,
            nutrition_status=NUTRITION_STATUS_NORMAL
        )
        self._submit_gmp_form(
            form_date=datetime(2016, 1, 10),
            case_id=case_id,
            nutrition_status=NUTRITION_STATUS_MODERATE
        )
        self._submit_gmp_form(
            form_date=datetime(2016, 2, 4),
            case_id=case_id,
            nutrition_status=NUTRITION_STATUS_NORMAL
        )
        self._submit_gmp_form(
            form_date=datetime(2016, 3, 4),
            case_id=case_id,
            nutrition_status=NUTRITION_STATUS_SEVERE
        )

        cases = [
            (0, [('nutrition_status_last_recorded', "normal"),
                 ('current_month_nutrition_status', "normal"),
                 ('nutrition_status_severely_underweight', 0),
                 ('nutrition_status_moderately_underweight', 0),
                 ('nutrition_status_normal', 1),
                 ('nutrition_status_weighed', 1),
                 ('nutrition_status_unweighed', 0)],
             ),
            (1, [('nutrition_status_last_recorded', "severely_underweight"),
                 ('current_month_nutrition_status', "severely_underweight"),
                 ('nutrition_status_severely_underweight', 1),
                 ('nutrition_status_moderately_underweight', 0),
                 ('nutrition_status_normal', 0),
                 ('nutrition_status_weighed', 1),
                 ('nutrition_status_unweighed', 0)],
             ),
            (2, [('nutrition_status_last_recorded', "severely_underweight"),
                 ('current_month_nutrition_status', "unweighed"),
                 ('nutrition_status_severely_underweight', 1),
                 ('nutrition_status_moderately_underweight', 0),
                 ('nutrition_status_normal', 0),
                 ('nutrition_status_weighed', 0),
                 ('nutrition_status_unweighed', 1)],
             ),
        ]
        self._run_iterative_monthly_test(case_id=case_id, cases=cases)

    def test_born_in_month_positive(self):
        case_id = uuid.uuid4().hex
        self._create_case(
            case_id=case_id,
            dob=date(2016, 3, 10),
            date_opened=datetime(2016, 3, 14),
            date_modified=datetime(2016, 3, 14),
            breastfed_within_first='yes',
            low_birth_weight='yes'
        )

        cases = [
            (0, [('born_in_month', 0),
                 ('low_birth_weight_born_in_month', 0),
                 ('bf_at_birth_born_in_month', 0)],
             ),
            (1, [('born_in_month', 1),
                 ('low_birth_weight_born_in_month', 1),
                 ('bf_at_birth_born_in_month', 1)],
             ),
            (2, [('born_in_month', 0),
                 ('low_birth_weight_born_in_month', 0),
                 ('bf_at_birth_born_in_month', 0)],
             ),
        ]
        self._run_iterative_monthly_test(case_id=case_id, cases=cases)

    def test_born_in_month_negative(self):
        case_id = uuid.uuid4().hex
        self._create_case(
            case_id=case_id,
            dob=date(2016, 3, 10),
            date_opened=datetime(2016, 3, 14),
            date_modified=datetime(2016, 3, 14),
        )

        cases = [
            (0, [('born_in_month', 0),
                 ('low_birth_weight_born_in_month', 0),
                 ('bf_at_birth_born_in_month', 0)],
             ),
            (1, [('born_in_month', 1),
                 ('low_birth_weight_born_in_month', 0),
                 ('bf_at_birth_born_in_month', 0)],
             ),
            (2, [('born_in_month', 0),
                 ('low_birth_weight_born_in_month', 0),
                 ('bf_at_birth_born_in_month', 0)],
             ),
        ]
        self._run_iterative_monthly_test(case_id=case_id, cases=cases)

    def test_fully_immunized_eligible(self):
        case_id = uuid.uuid4().hex
        self._create_case(
            case_id=case_id,
            dob=date(2015, 3, 10),
            date_opened=datetime(2015, 3, 10),
            date_modified=datetime(2016, 3, 12),
        )

        cases = [
            (0, [('fully_immunized_eligible', 0)]),
            (1, [('fully_immunized_eligible', 1)]),
            (2, [('fully_immunized_eligible', 1)]),
        ]
        self._run_iterative_monthly_test(case_id=case_id, cases=cases)

    def test_fully_immunized_on_time(self):
        case_id = uuid.uuid4().hex
        self._create_case(
            case_id=case_id,
            dob=date(2015, 3, 10),
            date_opened=datetime(2015, 3, 12),
            date_modified=datetime(2016, 3, 12),
            immun_one_year_date=date(2016, 2, 2),
        )

        cases = [
            (0, [('fully_immunized_on_time', 0),
                 ('fully_immunized_late', 0), ]
             ),
            (1, [('fully_immunized_on_time', 1),
                 ('fully_immunized_late', 0), ]
             ),
            (2, [('fully_immunized_on_time', 1),
                 ('fully_immunized_late', 0), ]
             ),
        ]
        self._run_iterative_monthly_test(case_id=case_id, cases=cases)

    def test_fully_immunized_late(self):
        case_id = uuid.uuid4().hex
        self._create_case(
            case_id=case_id,
            dob=date(2015, 1, 12),
            date_opened=datetime(2015, 2, 20),
            date_modified=datetime(2016, 3, 12),
            immun_one_year_date=date(2016, 3, 10),
        )

        cases = [
            (0, [('fully_immunized_on_time', 0),
                 ('fully_immunized_late', 0), ]
             ),
            (1, [('fully_immunized_on_time', 0),
                 ('fully_immunized_late', 1), ]
             ),
            (2, [('fully_immunized_on_time', 0),
                 ('fully_immunized_late', 1), ]
             ),
        ]
        self._run_iterative_monthly_test(case_id=case_id, cases=cases)
