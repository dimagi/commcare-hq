from corehq.extensions import extension_point, ResultFormat


@extension_point(result_format=ResultFormat.FIRST)
def get_form_pre_processor():
    """Custom form pre-processor to run before processing the form received

    Returns:
        a function that accepts the form passed as an argument and returns
        processed form
    """
