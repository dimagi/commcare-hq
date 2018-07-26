from __future__ import absolute_import
from corehq.apps.reports.graph_models import PieChart


class WVPieChart(PieChart):

    def __init__(self, title, key, values, color=None):
        super(WVPieChart, self).__init__(title, key, values, color)
        self.data = values or []
