from __future__ import absolute_import
from datetime import date
from django.utils.dateparse import parse_date
from custom.enikshay.const import NIKSHAY_NEW_TOG_API_FROM_DATE


def _forward_via_v2_api(date_of_diagnosis):
    if not isinstance(date_of_diagnosis, date):
        date_of_diagnosis = parse_date(date_of_diagnosis)
    return date_of_diagnosis >= NIKSHAY_NEW_TOG_API_FROM_DATE


def forward_via_v2_api(episode_case):
    date_of_diagnosis = episode_case.get_case_property('date_of_diagnosis')
    if date_of_diagnosis:
        return _forward_via_v2_api(date_of_diagnosis)
    return False


def forward_via_legacy_api(episode_case):
    date_of_diagnosis = episode_case.get_case_property('date_of_diagnosis')
    if date_of_diagnosis:
        return _forward_via_v2_api(date_of_diagnosis)
    return False
