
def form_requires_input(form):
    """
    Returns True if the form has at least one question that requires input
    """
    for question in form.get_questions([]):
        if question["tag"] not in ("trigger", "label", "hidden"):
            return True

    return False


