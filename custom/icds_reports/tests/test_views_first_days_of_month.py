from __future__ import absolute_import

from __future__ import unicode_literals
from django.test.testcases import TestCase
from django.test.client import RequestFactory
from django.urls import reverse

import json
import mock
import datetime

from custom.icds_reports.views import PrevalenceOfUndernutritionView, AwcReportsView, \
    PrevalenceOfSevereView, PrevalenceOfStuntingView, NewbornsWithLowBirthWeightView, \
    EarlyInitiationBreastfeeding, ExclusiveBreastfeedingView, ChildrenInitiatedView, InstitutionalDeliveriesView, \
    ImmunizationCoverageView, AWCsCoveredView, RegisteredHouseholdView, EnrolledChildrenView, \
    EnrolledWomenView, LactatingEnrolledWomenView, AdolescentGirlsView, AdhaarBeneficiariesView, CleanWaterView, \
    FunctionalToiletView, MedicineKitView, InfantsWeightScaleView, AdultWeightScaleView
from corehq.apps.users.models import WebUser
from corehq.apps.domain.models import Domain


class LastDayOfJune(datetime.datetime):
    @classmethod
    def utcnow(cls):
        return datetime.datetime(2017, 5, 31)


class FirstDayOfJuly(datetime.datetime):
    @classmethod
    def utcnow(cls):
        return datetime.datetime(2017, 6, 1)


class SecondDayOfJuly(datetime.datetime):
    @classmethod
    def utcnow(cls):
        return datetime.datetime(2017, 6, 2)


class ThirdDayOfJuly(datetime.datetime):
    @classmethod
    def utcnow(cls):
        return datetime.datetime(2017, 6, 3)


class Base(TestCase):

    def setUp(self):
        self.factory = None
        self.user = None
        self.view = None
        self.url = None
        self.run_july_third_test = False

    def test_map_first_day_of_month(self):
        if self.factory is None:
            return
        working_reverse = reverse(self.url, kwargs={'domain': 'icds-test', 'step': 'map'})
        request = self.factory.get(working_reverse)
        request.user = self.user
        with mock.patch('custom.icds_reports.views.datetime', LastDayOfJune):
            response_june = self.view(request, step='map', domain='icds-test')
        with mock.patch('custom.icds_reports.views.datetime', FirstDayOfJuly):
            response_first_of_july = self.view(request, step='map', domain='icds-test')

        self.assertDictEqual(json.loads(response_june.content), json.loads(response_first_of_july.content))

    def test_chart_first_day_of_month(self):
        if self.factory is None:
            return
        working_reverse = reverse(self.url, kwargs={'domain': 'icds-test', 'step': 'map'})
        request = self.factory.get(working_reverse)
        request.user = self.user
        with mock.patch('custom.icds_reports.views.datetime', LastDayOfJune):
            response_june = self.view(request, step='chart', domain='icds-test')
        with mock.patch('custom.icds_reports.views.datetime', FirstDayOfJuly):
            response_first_of_july = self.view(request, step='chart', domain='icds-test')

        self.assertDictEqual(json.loads(response_june.content), json.loads(response_first_of_july.content))

    def test_sector_first_day_of_month(self):
        if self.factory is None:
            return
        working_reverse = reverse(self.url, kwargs={'domain': 'icds-test', 'step': 'map'})
        request = self.factory.get(working_reverse)
        request.user = self.user
        with mock.patch('custom.icds_reports.views.datetime', LastDayOfJune):
            response_june = self.view(request, step='chart', domain='icds-test', location_id='b1')
        with mock.patch('custom.icds_reports.views.datetime', FirstDayOfJuly):
            response_first_of_july = self.view(request, step='chart', domain='icds-test', location_id='b1')

        self.assertDictEqual(json.loads(response_june.content), json.loads(response_first_of_july.content))

    def test_map_second_day_of_month(self):
        if self.factory is None:
            return
        working_reverse = reverse(self.url, kwargs={'domain': 'icds-test', 'step': 'map'})
        request = self.factory.get(working_reverse)
        request.user = self.user
        with mock.patch('custom.icds_reports.views.datetime', LastDayOfJune):
            response_june = self.view(request, step='map', domain='icds-test')
        with mock.patch('custom.icds_reports.views.datetime', SecondDayOfJuly):
            response_first_of_july = self.view(request, step='map', domain='icds-test')

        self.assertDictEqual(json.loads(response_june.content), json.loads(response_first_of_july.content))

    def test_chart_second_day_of_month(self):
        if self.factory is None:
            return
        working_reverse = reverse(self.url, kwargs={'domain': 'icds-test', 'step': 'map'})
        request = self.factory.get(working_reverse)
        request.user = self.user
        with mock.patch('custom.icds_reports.views.datetime', LastDayOfJune):
            response_june = self.view(request, step='chart', domain='icds-test')
        with mock.patch('custom.icds_reports.views.datetime', SecondDayOfJuly):
            response_first_of_july = self.view(request, step='chart', domain='icds-test')

        self.assertDictEqual(json.loads(response_june.content), json.loads(response_first_of_july.content))

    def test_sector_second_day_of_month(self):
        if self.factory is None:
            return
        working_reverse = reverse(self.url, kwargs={'domain': 'icds-test', 'step': 'map'})
        request = self.factory.get(working_reverse)
        request.user = self.user
        with mock.patch('custom.icds_reports.views.datetime', LastDayOfJune):
            response_june = self.view(request, step='chart', domain='icds-test', location_id='b1')
        with mock.patch('custom.icds_reports.views.datetime', SecondDayOfJuly):
            response_first_of_july = self.view(request, step='chart', domain='icds-test', location_id='b1')

        self.assertDictEqual(json.loads(response_june.content), json.loads(response_first_of_july.content))

    def test_map_third_day_of_month(self):
        if self.factory is None:
            return
        if not self.run_july_third_test:
            return
        working_reverse = reverse(self.url, kwargs={'domain': 'icds-test', 'step': 'map'})
        request = self.factory.get(working_reverse)
        request.user = self.user
        with mock.patch('custom.icds_reports.views.datetime', LastDayOfJune):
            response_june = self.view(request, step='map', domain='icds-test')
        with mock.patch('custom.icds_reports.views.datetime', ThirdDayOfJuly):
            response_first_of_july = self.view(request, step='map', domain='icds-test')

        self.assertNotEqual(response_june.content, response_first_of_july.content)

    def test_chart_third_day_of_month(self):
        if self.factory is None:
            return
        if not self.run_july_third_test:
            return
        working_reverse = reverse(self.url, kwargs={'domain': 'icds-test', 'step': 'map'})
        request = self.factory.get(working_reverse)
        request.user = self.user
        with mock.patch('custom.icds_reports.views.datetime', LastDayOfJune):
            response_june = self.view(request, step='chart', domain='icds-test')
        with mock.patch('custom.icds_reports.views.datetime', ThirdDayOfJuly):
            response_first_of_july = self.view(request, step='chart', domain='icds-test')

        self.assertNotEqual(response_june.content, response_first_of_july.content)

    def test_sector_third_day_of_month(self):
        if self.factory is None:
            return
        if not self.run_july_third_test:
            return
        working_reverse = reverse(self.url, kwargs={'domain': 'icds-test', 'step': 'map'})
        request = self.factory.get(working_reverse)
        request.user = self.user
        with mock.patch('custom.icds_reports.views.datetime', LastDayOfJune):
            response_june = self.view(request, step='chart', domain='icds-test', location_id='b1')
        with mock.patch('custom.icds_reports.views.datetime', ThirdDayOfJuly):
            response_first_of_july = self.view(request, step='chart', domain='icds-test', location_id='b1')

        self.assertNotEqual(response_june.content, response_first_of_july.content)

    def tearDown(self):
        if self.user:
            self.user.delete()


class TestPrevalenceOfUndernutritionView(Base):

    def setUp(self):
        self.run_july_third_test = True
        self.factory = RequestFactory()
        domain = Domain.get_or_create_with_name('icds-test')
        domain.is_active = True
        domain.save()
        user = WebUser.all().first()
        if not user:
            user = WebUser.create('icds-test', 'test', 'passwordtest')
        user.is_authenticated = True
        user.is_superuser = True
        user.is_authenticated = True
        user.is_active = True
        self.user = user
        self.view = PrevalenceOfUndernutritionView.as_view()
        self.url = 'underweight_children'


class TestAwcReportsView(Base):

    def setUp(self):
        self.run_july_third_test = False
        self.factory = RequestFactory()
        domain = Domain.get_or_create_with_name('icds-test')
        domain.is_active = True
        domain.save()
        user = WebUser.all().first()
        if not user:
            user = WebUser.create('icds-test', 'test', 'passwordtest')
        user.is_authenticated = True
        user.is_superuser = True
        user.is_authenticated = True
        user.is_active = True
        self.user = user
        self.view = AwcReportsView.as_view()
        self.url = 'awc_reports'


class TestPrevalenceOfSevereView(Base):

    def setUp(self):
        self.run_july_third_test = True
        self.factory = RequestFactory()
        domain = Domain.get_or_create_with_name('icds-test')
        domain.is_active = True
        domain.save()
        user = WebUser.all().first()
        if not user:
            user = WebUser.create('icds-test', 'test', 'passwordtest')
        user.is_authenticated = True
        user.is_superuser = True
        user.is_authenticated = True
        user.is_active = True
        self.user = user
        self.view = PrevalenceOfSevereView.as_view()
        self.url = 'prevalence_of_severe'


class TestPrevalenceOfStuntingView(Base):

    def setUp(self):
        self.run_july_third_test = True
        self.factory = RequestFactory()
        domain = Domain.get_or_create_with_name('icds-test')
        domain.is_active = True
        domain.save()
        user = WebUser.all().first()
        if not user:
            user = WebUser.create('icds-test', 'test', 'passwordtest')
        user.is_authenticated = True
        user.is_superuser = True
        user.is_authenticated = True
        user.is_active = True
        self.user = user
        self.view = PrevalenceOfStuntingView.as_view()
        self.url = 'prevalence_of_stunting'


class TestNewbornsWithLowBirthWeightView(Base):

    def setUp(self):
        self.run_july_third_test = True
        self.factory = RequestFactory()
        domain = Domain.get_or_create_with_name('icds-test')
        domain.is_active = True
        domain.save()
        user = WebUser.all().first()
        if not user:
            user = WebUser.create('icds-test', 'test', 'passwordtest')
        user.is_authenticated = True
        user.is_superuser = True
        user.is_authenticated = True
        user.is_active = True
        self.user = user
        self.view = NewbornsWithLowBirthWeightView.as_view()
        self.url = 'low_birth'


class TestEarlyInitiationBreastfeeding(Base):

    def setUp(self):
        self.run_july_third_test = True
        self.factory = RequestFactory()
        domain = Domain.get_or_create_with_name('icds-test')
        domain.is_active = True
        domain.save()
        user = WebUser.all().first()
        if not user:
            user = WebUser.create('icds-test', 'test', 'passwordtest')
        user.is_authenticated = True
        user.is_superuser = True
        user.is_authenticated = True
        user.is_active = True
        self.user = user
        self.view = EarlyInitiationBreastfeeding.as_view()
        self.url = 'early_initiation'


class TestExclusiveBreastfeedingView(Base):

    def setUp(self):
        self.run_july_third_test = True
        self.factory = RequestFactory()
        domain = Domain.get_or_create_with_name('icds-test')
        domain.is_active = True
        domain.save()
        user = WebUser.all().first()
        if not user:
            user = WebUser.create('icds-test', 'test', 'passwordtest')
        user.is_authenticated = True
        user.is_superuser = True
        user.is_authenticated = True
        user.is_active = True
        self.user = user
        self.view = ExclusiveBreastfeedingView.as_view()
        self.url = 'exclusive-breastfeeding'


class TestChildrenInitiatedView(Base):

    def setUp(self):
        self.run_july_third_test = True
        self.factory = RequestFactory()
        domain = Domain.get_or_create_with_name('icds-test')
        domain.is_active = True
        domain.save()
        user = WebUser.all().first()
        if not user:
            user = WebUser.create('icds-test', 'test', 'passwordtest')
        user.is_authenticated = True
        user.is_superuser = True
        user.is_authenticated = True
        user.is_active = True
        self.user = user
        self.view = ChildrenInitiatedView.as_view()
        self.url = 'children_initiated'


class TestInstitutionalDeliveriesView(Base):

    def setUp(self):
        self.run_july_third_test = True
        self.factory = RequestFactory()
        domain = Domain.get_or_create_with_name('icds-test')
        domain.is_active = True
        domain.save()
        user = WebUser.all().first()
        if not user:
            user = WebUser.create('icds-test', 'test', 'passwordtest')
        user.is_authenticated = True
        user.is_superuser = True
        user.is_authenticated = True
        user.is_active = True
        self.user = user
        self.view = InstitutionalDeliveriesView.as_view()
        self.url = 'institutional_deliveries'


class TestImmunizationCoverageView(Base):

    def setUp(self):
        self.run_july_third_test = True
        self.factory = RequestFactory()
        domain = Domain.get_or_create_with_name('icds-test')
        domain.is_active = True
        domain.save()
        user = WebUser.all().first()
        if not user:
            user = WebUser.create('icds-test', 'test', 'passwordtest')
        user.is_authenticated = True
        user.is_superuser = True
        user.is_authenticated = True
        user.is_active = True
        self.user = user
        self.view = ImmunizationCoverageView.as_view()
        self.url = 'immunization_coverage'


class TestAWCsCoveredView(Base):

    def setUp(self):
        self.run_july_third_test = True
        self.factory = RequestFactory()
        domain = Domain.get_or_create_with_name('icds-test')
        domain.is_active = True
        domain.save()
        user = WebUser.all().first()
        if not user:
            user = WebUser.create('icds-test', 'test', 'passwordtest')
        user.is_authenticated = True
        user.is_superuser = True
        user.is_authenticated = True
        user.is_active = True
        self.user = user
        self.view = AWCsCoveredView.as_view()
        self.url = 'awcs_covered'


class TestRegisteredHouseholdView(Base):

    def setUp(self):
        self.run_july_third_test = True
        self.factory = RequestFactory()
        domain = Domain.get_or_create_with_name('icds-test')
        domain.is_active = True
        domain.save()
        user = WebUser.all().first()
        if not user:
            user = WebUser.create('icds-test', 'test', 'passwordtest')
        user.is_authenticated = True
        user.is_superuser = True
        user.is_authenticated = True
        user.is_active = True
        self.user = user
        self.view = RegisteredHouseholdView.as_view()
        self.url = 'registered_household'


class TestEnrolledChildrenView(Base):

    def setUp(self):
        self.run_july_third_test = True
        self.factory = RequestFactory()
        domain = Domain.get_or_create_with_name('icds-test')
        domain.is_active = True
        domain.save()
        user = WebUser.all().first()
        if not user:
            user = WebUser.create('icds-test', 'test', 'passwordtest')
        user.is_authenticated = True
        user.is_superuser = True
        user.is_authenticated = True
        user.is_active = True
        self.user = user
        self.view = EnrolledChildrenView.as_view()
        self.url = 'enrolled_children'


class TestEnrolledWomenView(Base):

    def setUp(self):
        self.run_july_third_test = True
        self.factory = RequestFactory()
        domain = Domain.get_or_create_with_name('icds-test')
        domain.is_active = True
        domain.save()
        user = WebUser.all().first()
        if not user:
            user = WebUser.create('icds-test', 'test', 'passwordtest')
        user.is_authenticated = True
        user.is_superuser = True
        user.is_authenticated = True
        user.is_active = True
        self.user = user
        self.view = EnrolledWomenView.as_view()
        self.url = 'enrolled_women'


class TestLactatingEnrolledWomenView(Base):

    def setUp(self):
        self.run_july_third_test = True
        self.factory = RequestFactory()
        domain = Domain.get_or_create_with_name('icds-test')
        domain.is_active = True
        domain.save()
        user = WebUser.all().first()
        if not user:
            user = WebUser.create('icds-test', 'test', 'passwordtest')
        user.is_authenticated = True
        user.is_superuser = True
        user.is_authenticated = True
        user.is_active = True
        self.user = user
        self.view = LactatingEnrolledWomenView.as_view()
        self.url = 'lactating_enrolled_women'


class TestAdolescentGirlsView(Base):

    def setUp(self):
        self.run_july_third_test = True
        self.factory = RequestFactory()
        domain = Domain.get_or_create_with_name('icds-test')
        domain.is_active = True
        domain.save()
        user = WebUser.all().first()
        if not user:
            user = WebUser.create('icds-test', 'test', 'passwordtest')
        user.is_authenticated = True
        user.is_superuser = True
        user.is_authenticated = True
        user.is_active = True
        self.user = user
        self.view = AdolescentGirlsView.as_view()
        self.url = 'adolescent_girls'


class TestAdhaarBeneficiariesView(Base):

    def setUp(self):
        self.run_july_third_test = True
        self.factory = RequestFactory()
        domain = Domain.get_or_create_with_name('icds-test')
        domain.is_active = True
        domain.save()
        user = WebUser.all().first()
        if not user:
            user = WebUser.create('icds-test', 'test', 'passwordtest')
        user.is_authenticated = True
        user.is_superuser = True
        user.is_authenticated = True
        user.is_active = True
        self.user = user
        self.view = AdhaarBeneficiariesView.as_view()
        self.url = 'adhaar'


class TestCleanWaterView(Base):

    def setUp(self):
        self.run_july_third_test = True
        self.factory = RequestFactory()
        domain = Domain.get_or_create_with_name('icds-test')
        domain.is_active = True
        domain.save()
        user = WebUser.all().first()
        if not user:
            user = WebUser.create('icds-test', 'test', 'passwordtest')
        user.is_authenticated = True
        user.is_superuser = True
        user.is_authenticated = True
        user.is_active = True
        self.user = user
        self.view = CleanWaterView.as_view()
        self.url = 'clean_water'


class TestFunctionalToiletView(Base):

    def setUp(self):
        self.run_july_third_test = True
        self.factory = RequestFactory()
        domain = Domain.get_or_create_with_name('icds-test')
        domain.is_active = True
        domain.save()
        user = WebUser.all().first()
        if not user:
            user = WebUser.create('icds-test', 'test', 'passwordtest')
        user.is_authenticated = True
        user.is_superuser = True
        user.is_authenticated = True
        user.is_active = True
        self.user = user
        self.view = FunctionalToiletView.as_view()
        self.url = 'functional_toilet'


class TestMedicineKitView(Base):

    def setUp(self):
        self.run_july_third_test = True
        self.factory = RequestFactory()
        domain = Domain.get_or_create_with_name('icds-test')
        domain.is_active = True
        domain.save()
        user = WebUser.all().first()
        if not user:
            user = WebUser.create('icds-test', 'test', 'passwordtest')
        user.is_authenticated = True
        user.is_superuser = True
        user.is_authenticated = True
        user.is_active = True
        self.user = user
        self.view = MedicineKitView.as_view()
        self.url = 'medicine_kit'


class TestInfantsWeightScaleView(Base):

    def setUp(self):
        self.run_july_third_test = True
        self.factory = RequestFactory()
        domain = Domain.get_or_create_with_name('icds-test')
        domain.is_active = True
        domain.save()
        user = WebUser.all().first()
        if not user:
            user = WebUser.create('icds-test', 'test', 'passwordtest')
        user.is_authenticated = True
        user.is_superuser = True
        user.is_authenticated = True
        user.is_active = True
        self.user = user
        self.view = InfantsWeightScaleView.as_view()
        self.url = 'infants_weight_scale'


class TestAdultWeightScaleView(Base):

    def setUp(self):
        self.run_july_third_test = True
        self.factory = RequestFactory()
        domain = Domain.get_or_create_with_name('icds-test')
        domain.is_active = True
        domain.save()
        user = WebUser.all().first()
        if not user:
            user = WebUser.create('icds-test', 'test', 'passwordtest')
        user.is_authenticated = True
        user.is_superuser = True
        user.is_authenticated = True
        user.is_active = True
        self.user = user
        self.view = AdultWeightScaleView.as_view()
        self.url = 'adult_weight_scale'
