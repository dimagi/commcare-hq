from corehq.extensions import extension_point, ResultFormat


@extension_point(result_format=ResultFormat.FIRST)
def get_submission_post_form_processor_class():
    """A sub class of FormXmlProcessor class to be
    used to form processing

    Returns:
        A class to be instantiated, or None
    """
