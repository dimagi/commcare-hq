TODO:
in incentive.py, figure out last_month_total
Cron job to finalize reports at the end of each month.  (when, exactly?)
Show only data from the current report period

    from corehq.apps.fixtures.models import FixtureDataItem
    fixtures = [f.to_json().get('fields') for f in FixtureDataItem.by_domain('opm').all()]
    prices = dict([f.values() for f in fixtures])


# raw = [f.to_json().get('fields') for f in FixtureDataItem.by_domain('opm').all()]
# >>> ftype = FixtureDataType.by_domain_tag('opm', 'child_followup').one()
# >>> fixtures = FixtureDataItem.by_data_type('opm', ftype)
# fixtures = FixtureDataItem.by_data_tag('opm', 'child_followup')
# fixtures2 = FixtureDataItem.by_data_tag('opm', 'child_followup', queryable=True)
# fixtures2 = {
#     'fixture_name': {'Form Property': 'fixture_name', 'Amount': 200}
# }


### Extracting data from the db:

from corehq.apps.users.models import CommCareUser, CommCareCase
from dimagi.utils.couch.database import get_db

domain_id = db.view('domain/domains', key="opm", reduce=False).one()['id']
cases = CommCareCase.get_all_cases('opm') # json
cases = CommCareCase.get_all_cases('opm', include_docs=True) # python
users = CommCareUser.by_domain('opm') # python
forms = []
for c in cases:
    forms += c.get_forms() # python
