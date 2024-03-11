import datetime
import random

from corehq.apps.accounting.utils import months_from_date
from corehq.util.quickcache import quickcache


@quickcache(['num_entries'])
def get_fake_tabular_data(num_entries):
    case_owners = ('worker1', 'worker2', 'worker3', 'worker4')
    status = ('open', 'closed')
    first_names = (
        'Arundhati', 'Karan', 'Salman', 'Aravind', 'Katherine', 'Ethan', 'Luna', 'Olivia', 'Stella', 'Aiden',
        'Santiago', 'Sophia', 'Parry', 'Vahan', 'Vaishnavi', 'Wambui', 'Trish', 'Prakash',
    )
    last_names = (
        'Rosalynne', 'Edwena', 'Karla', 'Zak', 'Eddy', 'Meg', 'Kelebogile', 'Monday', 'Coba', 'Zenzi', 'Rebecca',
        'Sindy', 'Earline', 'Joeri', 'Hartmann', 'Elicia', 'Marianna', 'Jonathon', 'Emilia', 'Srinivas',
    )
    colors = ('blue', 'green', 'red', 'purple', 'salmon')
    big_cats = ('cheetah', 'lion', 'tiger', 'panther')
    apps = ('MCH V2', 'MCH V1', 'MCH V5')
    today = datetime.datetime.today()
    rows = []
    for row in range(0, num_entries):
        rows.append(
            ["patient", random.choice(first_names) + " " + random.choice(last_names),
             random.choice(colors),
             random.choice(big_cats),
             months_from_date(today, -1 * random.choice([6, 12, 24, 48])).strftime("%Y-%m-%d"),
             random.choice(apps),
             months_from_date(today, -1 * random.choice([0, 1, 2, 3])).strftime("%Y-%m-%d"),
             random.choice(case_owners), random.choice(status)]
        )
    return rows
