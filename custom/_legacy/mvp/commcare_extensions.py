from corehq.apps.userreports.extension_points import custom_ucr_expressions


@custom_ucr_expressions.extend()
def mvp_ucr_expressions():
    return [
        ('mvp_medical_cause', 'mvp.ucr.reports.expressions.medical_cause_expression'),
        ('mvp_no_treatment_reason', 'mvp.ucr.reports.expressions.no_treatment_reason_expression'),
        ('mvp_treatment_provider_name', 'mvp.ucr.reports.expressions.treatment_provider_name_expression'),
        ('mvp_treatment_place_name', 'mvp.ucr.reports.expressions.treatment_place_name_expression'),
        ('mvp_death_place', 'mvp.ucr.reports.expressions.death_place_expression'),
    ]
