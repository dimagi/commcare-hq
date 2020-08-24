from corehq.extensions import extension_point, ResultFormat


@extension_point(result_format=ResultFormat.FIRST)
def get_form_submission_context_class():
    """docs"""
