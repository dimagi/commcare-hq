import random


def is_mostly_false():
    return bool(random.choices(
        [0, 1],
        weights=[0.8, 0.2]
    )[0])


def get_random_spaces():
    num_spaces = random.choices(
        [0, 1, 2, 3],
        weights=[0.5, 0.2, 0.2, 0.1]
    )[0]
    return ' ' * num_spaces


def simulate_capitalization_issues(value):
    trigger = random.choices(
        [0, 1, 2, 3],
        weights=[0.7, 0.1, 0.1, 0.1]
    )[0]
    transform_fn = [
        lambda x: x,
        lambda x: x.upper(),
        lambda x: x.capitalize(),
        lambda x: x.lower(),
    ][trigger]
    return transform_fn(value)


def simulate_whitespace_issues(value):
    value = get_random_spaces() + value + get_random_spaces()
    if is_mostly_false():
        value = value + "\n"
    if is_mostly_false():
        value = "\t" + value
    return value


def simulate_missing_value_issues(value):
    trigger = random.choices(
        [0, 1, 2],
        weights=[0.7, 0.2, 0.1]
    )[0]
    return [value, "", None][trigger]


def simulate_free_input_issues(value, is_missing=True, whitespace=True, caps=True):
    if caps:
        value = simulate_capitalization_issues(value)
    if whitespace:
        value = simulate_whitespace_issues(value)
    if is_missing:
        value = simulate_missing_value_issues(value)
    return value


def get_renamed_field_data(old_name, new_name, value):
    if is_mostly_false():
        old_value = value
        new_value = None
    else:
        old_value = None
        new_value = value
    return {
        old_name: old_value,
        new_name: new_value,
    }
