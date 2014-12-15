class BaseMixin(object):

    @property
    def blocks(self):
        hierarchy_block = self.request.GET.getlist('hierarchy_block', [])
        return [] if hierarchy_block and hierarchy_block[0] == '0' else hierarchy_block

    @property
    def awcs(self):
        hierarchy_awc = self.request.GET.getlist('hierarchy_awc', [])
        return [] if hierarchy_awc and hierarchy_awc[0] == '0' else hierarchy_awc

    @property
    def gp(self):
        hierarchy_gp = self.request.GET.getlist('hierarchy_gp', [])
        return [] if hierarchy_gp and hierarchy_gp[0] == '0' else hierarchy_gp


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
