from sqlagg.columns import SimpleColumn
from corehq.apps.reports.sqlreport import SqlData, DatabaseColumn
from custom.common import ALL_OPTION


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


def format_percent(x, y):
    y = _safeint(y)
    percent = (y or 0) * 100 / (x or 1)

    if percent < 33:
        color = 'red'
    elif 33 <= percent <= 67:
        color = 'orange'
    else:
        color = 'green'
    return "<span style='display: block; text-align:center; color:%s;'>%d<hr style='margin: 0;border-top: 0; border-color: black;'>%d%%</span>" % (color, y, percent)


def normal_format(value):
    if not value:
        value = 0
    return "<span style='display: block; text-align:center;'>%d<hr style='margin: 0;border-top: 0; border-color: black;'></span>" % value


class UserSqlData(SqlData):
    table_name = "fluff_OpmUserFluff"
    group_by = ['doc_id', 'awc', 'awc_code', 'gp', 'block']

    @property
    def filters(self):
        return []

    @property
    def columns(self):
        return [
            DatabaseColumn('doc_id', SimpleColumn('doc_id')),
            DatabaseColumn('awc', SimpleColumn('awc')),
            DatabaseColumn('awc_code', SimpleColumn('awc_code')),
            DatabaseColumn('gp', SimpleColumn('gp')),
            DatabaseColumn('block', SimpleColumn('block')),
        ]


def get_matching_users(awcs=None, gps=None, blocks=None):
    """
    Accepts a list of one or more of `awcs`, `gps`, and `blocks`,
    returns a list of users matching that selection
    each user is represented as a dict with the following keys:
    ['doc_id', 'awc', 'gp', 'block', 'awc_code']
    """
    non_null = filter(
        lambda (k, v): bool(v),
        [('awc', awcs), ('gp', gps), ('block', blocks)]
    )
    if not len(non_null) > 0:
        raise TypeError("You must pass at least one of awc, gp, or block")
    key, selected = non_null[0]  # get most specific selection
    return [
        user for user in UserSqlData().get_data()
        if user[key] in selected
    ]
