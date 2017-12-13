#from bhoma.apps.patient.signals import patient_updated
#
#def update_pregnancies(sender, patient_id, **kwargs):
#    """
#    Update pregnancies of a patient.
#    """
#    from bhoma.apps.reports.calc.pregnancy import extract_pregnancies
#    from bhoma.apps.reports.models import CPregnancy
#    from bhoma.apps.patient.models import CPatient
#
#    patient = CPatient.get(patient_id)
#    pregs = extract_pregnancies(patient)
#    # manually remove old pregnancies, since all pregnancy data is dynamically generated
#    for old_preg in CPregnancy.view("reports/pregnancies_for_patient", key=patient_id).all():
#        old_preg.delete()
#    for preg in pregs:
#        couch_pregnancy = preg.to_couch_object()
#        couch_pregnancy.save()
#    patient.save()
#
#patient_updated.connect(update_pregnancies)

from __future__ import absolute_import
from django.dispatch.dispatcher import receiver

from casexml.apps.case.signals import case_post_save
from corehq.apps.reports.analytics.esaccessors import get_case_types_for_domain_es
from corehq.form_processor.signals import sql_case_post_save


@receiver([case_post_save, sql_case_post_save])
def clear_case_type_cache(sender, case, **kwargs):
    case_types = get_case_types_for_domain_es.get_cached_value(case.domain)
    if case_types != Ellipsis and case.type not in case_types:
        get_case_types_for_domain_es.clear(case.domain)
