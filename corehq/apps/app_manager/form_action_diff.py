

def merge_case_mappings(diff, form_actions):
    """Apply open/update case diffs to form actions

    :param diff: dict
    :param form_actions: FormActions object, will be mutated.
    :raises: KeyError if the diff contained unknown top-level keys. This
        should not happen unless there is a bug in the code or a request
        had an unexpected format (user modified?).
    """
    unknowns = diff.keys() - {'open_case', 'update_case'}
    if unknowns:
        raise KeyError(f"unknown diff keys: {unknowns}")
