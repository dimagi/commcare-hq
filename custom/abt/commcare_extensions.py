from corehq.apps.userreports.extension_points import custom_ucr_expressions


@custom_ucr_expressions.extend()
def abt_ucr_expressions():
    return [
        ('abt_supervisor', 'custom.abt.reports.expressions.abt_supervisor_expression'),
        ('abt_supervisor_v2', 'custom.abt.reports.expressions.abt_supervisor_v2_expression'),
        ('abt_supervisor_v2019', 'custom.abt.reports.expressions.abt_supervisor_v2019_expression'),
    ]
