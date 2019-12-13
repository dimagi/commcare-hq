import datetime

from corehq.apps.reports.standard import DatespanMixin
from custom.inddex.filters import GapDescriptionFilter, FoodTypeFilter, AgeRangeFilter, GenderFilter, \
    SettlementAreaFilter, BreastFeedingFilter, PregnancyFilter, RecallStatusFilter, GapTypeFilter, DateRangeFilter


class ReportMixin(DatespanMixin):
    request = domain = None

    @property
    def fields(self):
        return [DateRangeFilter]

    @property
    def report_config(self):
        return {
            'domain': self.domain,
            'startdate': self.start_date,
            'enddate': self.end_date
        }

    @property
    def start_date(self):
        start_date = self.request.GET.get('startdate')

        return start_date if start_date else str(datetime.datetime.now().date())

    @property
    def end_date(self):
        end_date = self.request.GET.get('end_date')

        return end_date if end_date else str(datetime.datetime.now().date())


class BaseMixin:
    request = None

    @staticmethod
    def get_base_fields():
        raise NotImplementedError('\'get_base_fields\' must be implemented')

    @staticmethod
    def get_base_report_config(obj):
        raise NotImplementedError('\'get_report_config\' must be implemented')


class GapsSummaryFoodTypeBaseMixin(BaseMixin):
    request = None

    @staticmethod
    def get_base_fields():
        return [
            GapTypeFilter,
            RecallStatusFilter
        ]

    @staticmethod
    def get_base_report_config(obj):
        return {
            'recall_status': obj.recall_status
        }

    @property
    def recall_status(self):
        return self.request.GET.get('recall_status') or ''


class ReportBaseMixin(BaseMixin):

    @staticmethod
    def get_base_fields():
        return [
            GenderFilter,
            AgeRangeFilter,
            PregnancyFilter,
            BreastFeedingFilter,
            SettlementAreaFilter,
            RecallStatusFilter
        ]

    @staticmethod
    def get_base_report_config(obj):
        return {
            'gender': obj.gender,
            'age_range': obj.age_range,
            'pregnant': obj.pregnant,
            'breastfeeding': obj.breastfeeding,
            'urban_rural': obj.urban_rural,
            'supplements': obj.supplements,
            'recall_status': obj.recall_status
        }

    @property
    def age_range(self):
        return self.request.GET.get('age_range') or ''

    @property
    def gender(self):
        return self.request.GET.get('gender') or ''

    @property
    def urban_rural(self):
        return self.request.GET.get('urban_rural') or ''

    @property
    def breastfeeding(self):
        return self.request.GET.get('breastfeeding') or ''

    @property
    def pregnant(self):
        return self.request.GET.get('pregnant') or ''

    @property
    def supplements(self):
        return self.request.GET.get('supplements') or ''

    @property
    def recall_status(self):
        return self.request.GET.get('recall_status') or ''


class NutrientIntakesBaseMixin(ReportBaseMixin):

    @staticmethod
    def get_base_fields():
        # todo add who/gift filter
        return ReportBaseMixin.get_base_fields()

    @staticmethod
    def get_base_report_config(obj):
        # todo add who/gift value
        return ReportBaseMixin.get_base_report_config(obj)
