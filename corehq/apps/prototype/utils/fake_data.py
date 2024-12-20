import datetime
import random
from corehq.apps.accounting.utils import months_from_date


def get_first_name():
    first_names = (
        'Arundhati', 'Karan', 'Salman', 'Aravind', 'Katherine', 'Ethan', 'Luna', 'Olivia', 'Stella', 'Aiden',
        'Santiago', 'Sophia', 'Parry', 'Vahan', 'Vaishnavi', 'Wambui', 'Trish', 'Prakash',
    )
    return random.choice(first_names)


def get_last_name():
    first_names = (
        'Rosalynne', 'Edwena', 'Karla', 'Zak', 'Eddy', 'Meg', 'Kelebogile', 'Monday', 'Coba', 'Zenzi', 'Rebecca',
        'Sindy', 'Earline', 'Joeri', 'Hartmann', 'Elicia', 'Marianna', 'Jonathon', 'Emilia', 'Srinivas',
    )
    return random.choice(first_names)


def get_planet():
    colors = ('mercury', 'venus', 'earth', 'mars', 'jupiter', 'saturn', 'uranus', 'neptune')
    return random.choice(colors)


def get_color():
    colors = ('blue', 'green', 'red', 'purple', 'salmon')
    return random.choice(colors)


def get_big_cat():
    big_cats = ('cheetah', 'lion', 'tiger', 'panther')
    return random.choice(big_cats)


def get_fake_app():
    apps = ('MCH V2', 'MCH V1', 'MCH V5')
    return random.choice(apps)


def get_owner():
    owners = ('worker1', 'worker2', 'worker3', 'worker4')
    return random.choice(owners)


def get_status():
    return random.choice(['open', 'closed'])


def get_past_date(months_away=None):
    months_away = months_away or [6, 12, 24, 48]
    today = datetime.datetime.today()
    return months_from_date(today, -1 * random.choice(months_away)).strftime("%Y-%m-%d")
