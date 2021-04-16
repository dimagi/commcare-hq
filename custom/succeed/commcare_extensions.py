from corehq.apps.userreports.extension_points import custom_ucr_expressions


@custom_ucr_expressions.extend()
def succeed_ucr_expressions():
    return [
        ('succeed_referenced_id', 'custom.succeed.expressions.succeed_referenced_id'),
    ]
