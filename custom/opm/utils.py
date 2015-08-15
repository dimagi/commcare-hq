from sqlagg.columns import SimpleColumn
from corehq.apps.reports.sqlreport import SqlData, DatabaseColumn
from custom.common import ALL_OPTION
from dimagi.utils.decorators.memoized import memoized


EMPTY_FIELD = "---"


class BaseMixin(object):

    @property
    def blocks(self):
        hierarchy_block = self.request.GET.getlist('hierarchy_block', [])
        return [] if hierarchy_block and hierarchy_block[0] == ALL_OPTION else hierarchy_block

    @property
    def awcs(self):
        hierarchy_awc = self.request.GET.getlist('hierarchy_awc', [])
        return [] if hierarchy_awc and hierarchy_awc[0] == ALL_OPTION else hierarchy_awc

    @property
    def gp(self):
        hierarchy_gp = self.request.GET.getlist('hierarchy_gp', [])
        return [] if hierarchy_gp and hierarchy_gp[0] == ALL_OPTION else hierarchy_gp


def _safeint(value):
    try:
        return int(value)
    except (ValueError, TypeError):
        return 0


class UserSqlData(SqlData):
    table_name = "fluff_OpmUserFluff"
    group_by = ['doc_id', 'name', 'awc', 'awc_code', 'bank_name',
                'ifs_code', 'account_number', 'gp', 'block', 'village', 'gps']

    @property
    def filters(self):
        return []

    @property
    def columns(self):
        return [
            DatabaseColumn('doc_id', SimpleColumn('doc_id')),
            DatabaseColumn('name', SimpleColumn('name')),
            DatabaseColumn('awc', SimpleColumn('awc')),
            DatabaseColumn('awc_code', SimpleColumn('awc_code')),
            DatabaseColumn('bank_name', SimpleColumn('bank_name')),
            DatabaseColumn('ifs_code', SimpleColumn('ifs_code')),
            DatabaseColumn('account_number', SimpleColumn('account_number')),
            DatabaseColumn('gp', SimpleColumn('gp')),
            DatabaseColumn('block', SimpleColumn('block')),
            DatabaseColumn('village', SimpleColumn('village')),
            DatabaseColumn('gps', SimpleColumn('gps'))
        ]

    def transformed_data(self):
        data = []
        for user in self.get_data():
            transformed_user = user
            transformed_user['awc_with_code'] = "{} - ({})".format(user['awc'], user['awc_code'])
            data.append(transformed_user)
        return data

    def data_as_hierarchy(self):
        """
        Creates a location hierarchy structured as follows:
        hierarchy = {"Atri": {
                        "Sahora": {
                            "Sohran Bigha (34)": None}}}
        """
        hierarchy = {}
        for location in self.transformed_data():
            block = location['block']
            gp = location['gp']
            awc_name_with_code = location['awc_with_code']
            if not (awc_name_with_code and gp and block):
                continue
            hierarchy[block] = hierarchy.get(block, {})
            hierarchy[block][gp] = hierarchy[block].get(gp, {})
            hierarchy[block][gp][awc_name_with_code] = None
        return hierarchy

    @property
    @memoized
    def data_by_doc_id(self):
        return {user['doc_id']: (user['awc_code'], user['gp']) for user in self.get_data()}


@memoized
def user_sql_data():
    return UserSqlData()


def get_matching_users(awcs=None, gps=None, blocks=None):
    """
    Accepts a list of one or more of `awcs`, `gps`, and `blocks`,
    returns a list of users matching that selection
    each user is represented as a dict with the following keys:
    ['doc_id', 'awc', 'gp', 'block', 'awc_code']
    """
    non_null = filter(
        lambda (k, v): bool(v),
        [('awc_with_code', awcs), ('gp', gps), ('block', blocks)]
    )
    if not len(non_null) > 0:
        raise TypeError("You must pass at least one of awc, gp, or block")
    key, selected = non_null[0]  # get most specific selection
    return [
        user for user in user_sql_data().transformed_data()
        if user[key] in selected
    ]


def numeric_fn(val):
    try:
        sort_val = int(val)
    except ValueError:
        sort_val = -1
    except TypeError:
        sort_val = -1
    return {'sort_key': sort_val, 'html': val}


def format_bool(bool_or_none):
    if bool_or_none is None:
        return EMPTY_FIELD
    elif bool_or_none:
        return 'Yes'
    elif not bool_or_none:
        return 'No'
