import random

from corehq.apps.prototype.utils.fake_case_data import (
    dates,
    issues,
    names,
)
from corehq.apps.prototype.utils.fake_case_data.dates import get_recent_date, get_edd, format_date
from corehq.apps.prototype.utils.fake_case_data.system import get_case_system_info


def get_language_code():
    return random.choice(('en', 'nl', 'es'))


def get_language(lang):
    return {
        'en': lambda: random.choice((
            "en", "eglish", "english", "inglés", "inglesa", "ingels", "engels",
        )),
        'es': lambda: random.choice((
            "spanish", "esp", "español", "espanol", "epanol", "sp", "es",
        )),
        'nl': lambda: random.choice((
            "nl", "ned", "dutch", "nederlands", "holandesa", "holandés", "holand",
            "holandes",
        )),
    }[lang]()


def get_mother_name(lang):
    name_fn = {
        'nl': names.get_dutch_name,
        'en': names.get_english_name,
        'es': names.get_spanish_name,
    }[lang]
    first, last = name_fn()
    # add whitespace issues
    num_spaces = random.choices(
        [1, 2],
        weights=[0.8, 0.2]
    )[0]
    space = " " * num_spaces
    if issues.is_mostly_false():
        space = space + '\n'
    return f"{first}{space}{last}"


def get_height():
    return random.choice(range(149, 178))


def get_pregnant_status():
    return random.choice((
        "pregnant", "recently_delivered",
    ))


def get_time_of_day():
    is_new_data = bool(random.getrandbits(1))
    if is_new_data:
        return random.choice((
            'daytime', 'nighttime',
        ))
    return random.choice((
        'morning', 'afternoon', 'evening', 'night',
    ))


def get_location():
    return random.choice((
        'hospital', 'facility', 'home',
    ))


def get_conducted_delivery(location):
    return {
        'hospital': lambda: random.choice((
            'skilled_attendant', 'doctor', 'nurse', None,
        )),
        'facility': lambda: random.choice((
            'skilled_attendant', 'nurse', 'relative', None,
        )),
        'home': lambda: random.choice((
            'skilled_attendant', 'midwife', 'relative', None,
        )),
    }[location]()


def get_pregnancy_data(date_last_modified):
    status = get_pregnant_status()
    data = {
        'mother_status': status,
        'date_of_delivery': '',
        'delivery_location': '',
        'conducted_delivery': '',
        'time_of_day': '',
        'lmp': '',
        'edd': '',
    }
    recent_date = get_recent_date(date_last_modified)
    if status == 'pregnant':
        data['lmp'] = format_date(recent_date)
        data['edd'] = format_date(get_edd(recent_date))
        if issues.is_mostly_false():
            data['conducted_delivery'] = None
    else:
        data['date_of_delivery'] = format_date(recent_date)
        data['delivery_location'] = get_location()
        data['conducted_delivery'] = get_conducted_delivery(data['delivery_location'])
        data['time_of_day'] = get_time_of_day()
    return data


def get_case_data_with_issues():
    """
    Returns the following:
        - name
        - conducted_delivery
        - date_of_delivery
        - delivery_location
        - dob
        - edd
        - hight
        - height
        - lmp
        - spoken_language
        - time_of_day
        - woman_status
    System:
        - owner_name
        - opened_date
        - opened_by
        - last_modified_date
        - last_modified_by_user_username
        - closed / status
        - closed_date
        - closed_by_username
    """
    date_last_modified, system_properties = get_case_system_info()
    lang = get_language_code()
    language = get_language(lang)
    name = get_mother_name(lang)
    pregnancy_data = get_pregnancy_data(date_last_modified)
    if pregnancy_data['mother_status'] == 'pregnant':
        system_properties['closed'] = False
        system_properties['closed_date'] = None
        system_properties['closed_by_username'] = None
    return {
        "name": issues.simulate_free_input_issues(name, is_missing=False),
        "spoken_language": issues.simulate_free_input_issues(language),
        "dob": format_date(dates.get_dob()),
        "status": "closed" if system_properties["closed"] else "open",
        **issues.get_renamed_field_data('hight', 'height', get_height()),
        **pregnancy_data,
        **system_properties,
    }
