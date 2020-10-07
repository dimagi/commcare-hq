from corehq.apps.userreports.extension_points import custom_ucr_expressions


@custom_ucr_expressions.extend()
def eqa_ucr_expressions():
    return [
        ('eqa_expression', 'custom.eqa.expressions.eqa_expression'),
        ('cqi_action_item', 'custom.eqa.expressions.cqi_action_item'),
        ('eqa_percent_expression', 'custom.eqa.expressions.eqa_percent_expression'),
    ]
