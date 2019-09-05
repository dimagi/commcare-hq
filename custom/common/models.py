from corehq.apps.reports.graph_models import Chart


class LineChart(Chart):
    """
    :param title: The chart title
    "param x_axis: Instance of corehq.apps.reports.graph_models.Axis
    "param y_axis: Instance of corehq.apps.reports.graph_models.Axis

    Class fields:
        data: see add_dataset function
        marginTop: Top Margin in pixels
        marginLeft: Left Margin in pixels
        marginRight: Right Margin in pixels
        marginBottom: Bottom Margin in pixels

    """
    template_partial = 'custom/common/templates/common/line_chart.html'

    def __init__(self, title, x_axis, y_axis):
        self.title = title

        self.x_axis = x_axis
        self.y_axis = y_axis
        self.data = []
        self.marginTop = 30
        self.marginRight = 20
        self.marginBottom = 50
        self.marginLeft = 100
        self.tooltips = True
        self.showLegend = True
        # this determines whether or not the data should get formatted client side
        self.data_needs_formatting = False
        # using the data formatting helpers in nvd3_charts_helper.js
        # determines whether or not we should use a date format for the xaxis
        self.x_axis_uses_dates = False

    def add_dataset(self, key, values, color=None):
        """
        :param key: dataset name
        :param values: List of dictionaries containing x and y values i.e. [{x=1, y=2}, ...]
        :param color: HTML color value
        """
        d = dict(key=key, values=values)
        if color:
            d['color'] = color
        self.data.append(d)

    def config_dict(self):
        return dict(margin={'top': self.marginTop,
                            'right': self.marginRight,
                            'bottom': self.marginBottom,
                            'left': self.marginLeft},
                    showLegend=self.showLegend,
                    tooltips=self.tooltips)
