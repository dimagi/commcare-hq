from corehq.motech.repeaters.models import Repeater


def repair_repeaters_with_whitelist_bug():
    """
    Used in 0014_fix_whitelist_bug_repeaters.py
    The whitelist bug resulted in the white_listed_form_xmlns key in a
    repeater's option field storing '[]' as a form id it would whitelist.
    :return: list of repeater ids that were fixed
    """
    # ignores deleted repeaters
    all_repeaters = Repeater.objects.all()
    broken_repeaters = [r for r in all_repeaters if
                        'white_listed_form_xmlns' in r.options and r.options[
                            'white_listed_form_xmlns'] == ['[]']]

    fixed_repeaters = []
    for repeater in broken_repeaters:
        # reset back to an empty list
        repeater.options['white_listed_form_xmlns'] = []
        repeater.save()
        fixed_repeaters.append(repeater.repeater_id)

    return fixed_repeaters
