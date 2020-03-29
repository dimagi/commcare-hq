import datetime

from django.test import TestCase

from custom.icds_reports.models.views import PMOAPIView
from datetime import date


class PMOAPITest(TestCase):

    def test_view_content(self):
        data = PMOAPIView.objects.filter(
            month=date(2017, 5, 1)
        ).values(
            "state_id",
            "state_name",
            "state_site_code",
            "district_id",
            "district_name",
            "district_site_code",
            "aggregation_level",
            "month",
            "cbe_conducted",
            "vhnd_conducted",
            "num_launched_awcs",
            "wer_weighed",
            "wer_eligible",
            "bf_at_birth",
            "born_in_month",
            "cf_initiation_eligible",
            "cf_initiation_in_month"
        )
        first_result = data[0]
        self.assertDictEqual(
            {
                "state_id": "st1", "state_name": "st1", "state_site_code": "st1",
                "district_id": "d1", "district_name": "d1", "district_site_code": "d1",
                "aggregation_level": 2, "month": datetime.date(2017, 5, 1), "cbe_conducted": 1,
                "vhnd_conducted": 3, "num_launched_awcs": 10, "wer_weighed": 317, "wer_eligible": 475,
                "bf_at_birth": 1, "born_in_month": 2, "cf_initiation_eligible": 17, "cf_initiation_in_month": 14
             },
            first_result
        )
