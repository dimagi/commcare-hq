from corehq.form_processor.models.cases import CommCareCase


def check_for_existing_abha_number(domain, abha_number):
    return bool(CommCareCase.objects.get_case_by_external_id(domain=domain, external_id=abha_number))
