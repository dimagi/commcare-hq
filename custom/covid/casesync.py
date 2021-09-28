from corehq.form_processor.interfaces.dbaccessors import CaseAccessors


def get_ush_extension_cases_to_close(domain, cases):
    # When closing 'patient' type cases
    #   dont include 'contact' type extension cases
    #   in the chain, and further don't include the
    #   extensions of those contact cases as well
    PATIENT_CASE_TYPE = 'patient'
    CONTACT_CASE_TYPE = 'contact'
    patient_case_ids = [case.case_id for case in cases if case.closed and case.type == PATIENT_CASE_TYPE]
    patient_extensions = CaseAccessors(domain).get_extension_chain(
        patient_case_ids,
        include_closed=False,
        exclude_for_case_type=CONTACT_CASE_TYPE  # exclude extensions of CONTACT_CASE_TYPE from the chain
    )
    valid_extensions = {
        case.case_id
        for case in CaseAccessors(domain).get_cases(list(patient_extensions))
        # exclude CONTACT_CASE_TYPE extensions of the PATIENT_CASE_TYPE
        if case.type != CONTACT_CASE_TYPE
    }
    other_case_ids = [case.case_id for case in cases if case.closed and case.type != PATIENT_CASE_TYPE]
    return valid_extensions.union(CaseAccessors(domain).get_extension_chain(other_case_ids, include_closed=False))
