from dimagi.utils.parsing import string_to_boolean

def are_you_sure(prompt="Are you sure you want to proceed? (yes or no): "):
    """
    Ask a user if they are sure before doing something.  Return
    whether or not they are sure
    """
    should_proceed = raw_input(prompt)
    try:
        return string_to_boolean(should_proceed)
    except Exception:
        return False

