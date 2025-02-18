from corehq.apps.prototype.utils import fake_data
from corehq.util.quickcache import quickcache


@quickcache(['num_entries'])
def get_fake_tabular_data(num_entries):
    rows = []
    for row in range(0, num_entries):
        rows.append([
            "patient",
            f"{fake_data.get_first_name()} {fake_data.get_last_name()}",
            fake_data.get_color(),
            fake_data.get_big_cat(),
            fake_data.get_past_date(),
            fake_data.get_fake_app(),
            fake_data.get_past_date(months_away=[0, 1, 2, 3]),
            fake_data.get_owner(),
            fake_data.get_status(),
        ])
    return rows
