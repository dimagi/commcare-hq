from corehq.apps.prototype.utils import fake_data
from corehq.util.quickcache import quickcache


@quickcache(['num_entries'])
def generate_example_pagination_data(num_entries):
    """
    This function just generates some fake data made to look somewhat like a CommCare Case.
    """
    rows = []
    for row in range(0, num_entries):
        rows.append({
            "name": f"{fake_data.get_first_name()} {fake_data.get_last_name()}",
            "color": fake_data.get_color(),
            "big_cat": fake_data.get_big_cat(),
            "dob": fake_data.get_past_date(),
            "app": fake_data.get_fake_app(),
            "status": fake_data.get_status(),
            "owner": fake_data.get_owner(),
            "date_opened": fake_data.get_past_date(months_away=[0, 1, 2, 3]),
        })
    return rows
