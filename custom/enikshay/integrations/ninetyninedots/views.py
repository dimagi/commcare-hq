from __future__ import absolute_import
from __future__ import unicode_literals
import pytz
from django.utils.dateparse import parse_datetime

from corehq.motech.repeaters.views import AddCaseRepeaterView
from custom.enikshay.integrations.ninetyninedots.exceptions import NinetyNineDotsException
import six


class RegisterPatientRepeaterView(AddCaseRepeaterView):
    urlname = 'register_99dots_patient'
    page_title = "Register 99DOTS Patients"
    page_name = "Register 99DOTS Patients"


class UpdatePatientRepeaterView(AddCaseRepeaterView):
    urlname = 'update_99dots_patient'
    page_title = "Update 99DOTS Patients"
    page_name = "Update 99DOTS Patients"


class UpdateAdherenceRepeaterView(AddCaseRepeaterView):
    urlname = 'update_99dots_adherence'
    page_title = "Update 99DOTS Adherence"
    page_name = "Update 99DOTS Adherence"


class UpdateTreatmentOutcomeRepeaterView(AddCaseRepeaterView):
    urlname = 'update_99dots_treatment_outcome'
    page_title = "Update 99DOTS Treatment Outcome"
    page_name = "Update 99DOTS Treatment Outcome"


class UnenrollPatientRepeaterView(AddCaseRepeaterView):
    urlname = 'unenroll_99dots_patient'
    page_title = "Unenroll 99DOTS Patients"
    page_name = "Unenroll 99DOTS Patients"


def validate_beneficiary_id(beneficiary_id):
    if beneficiary_id is None:
        raise NinetyNineDotsException("Beneficiary ID is null")
    if not isinstance(beneficiary_id, six.string_types):
        raise NinetyNineDotsException("Beneficiary ID should be a string")


def validate_dates(start_date, end_date):
    if start_date is None:
        raise NinetyNineDotsException("start_date is null")
    if end_date is None:
        raise NinetyNineDotsException("end_date is null")
    try:
        parse_datetime(start_date).astimezone(pytz.UTC)
        parse_datetime(end_date).astimezone(pytz.UTC)
    except:
        raise NinetyNineDotsException("Malformed Date")


def validate_adherence_values(adherence_values):
    if adherence_values is None or not isinstance(adherence_values, list):
        raise NinetyNineDotsException("Adherences invalid")


def validate_confidence_level(confidence_level):
    valid_confidence_levels = ['low', 'medium', 'high']
    if confidence_level not in valid_confidence_levels:
        raise NinetyNineDotsException(
            message="New confidence level invalid. Should be one of {}".format(
                valid_confidence_levels
            )
        )
