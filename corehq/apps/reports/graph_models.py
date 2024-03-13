

class Axis(object):
    """
    :param label: Name of the Axis
    :param format: d3.js axis format
    :param dateFormat: Modify values to JS Date objects and set d3.time.format
                       refer to https://github.com/mbostock/d3/wiki/Time-Formatting
    """

    def __init__(self, label=None, format=None, dateFormat=None):
        self.label = label
        self.format = format
        self.dateFormat = dateFormat

    def to_json(self):
        return {'label': self.label,
                'format': self.format,
                'dateFormat': self.dateFormat,
                }


class Chart(object):
    template_partial = ''
    height = 320
    title = ''


class MultiBarChart(Chart):
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
        showControls: True to show controls
        showLegend: True to show legend
        reduceXTicks: True to reduce the number of X ticks
        rotateLabels: Degrees to rotate X-Axis labels e.g. -45
        tooltips: True to show tooltips
        tooltipFormat: Seperator text bw x,y values in tooltipContent
                       e.g." in ", " on  "
        stacked: True to make default view stacked, False for grouped
        staggerLabels: True to stagger the X-Axis labels.
        groupSpacing: Used to adjust amount of space between X-Axis
                      groups. Value between 0 and 1.
        forceY: Used to force values into the Y scale domain. Useful to
                ensure max / min scales. Must be list of numbers
        translateLabelsX: Pixels to move X-Axis labels in X direction
        translateLabelsY: Pixels to move X-Axis labels in Y direction

    """
    template_partial = 'reports/partials/graphs/multibar_chart.html'

    def __init__(self, title, x_axis, y_axis):
        self.title = title

        self.x_axis = x_axis
        self.y_axis = y_axis
        self.data = []
        self.marginTop = 30
        self.marginRight = 20
        self.marginBottom = 50
        self.marginLeft = 100
        self.showControls = True
        self.showLegend = True
        self.reduceXTicks = False
        self.rotateLabels = 0
        self.tooltips = True
        self.tooltipFormat = ""
        self.stacked = False
        self.translateLabelsX = 0
        self.translateLabelsY = 0
        self.staggerLabels = False
        self.groupSpacing = 0.3
        self.forceY = [0, 1]

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
        if self.rotateLabels and not self.translateLabelsX:
            self.translateLabelsX = -10
        return dict(margin={'top': self.marginTop,
                            'right': self.marginRight,
                            'bottom': self.marginBottom,
                            'left': self.marginLeft},
                    showControls=self.showControls,
                    showLegend=self.showLegend,
                    reduceXTicks=self.reduceXTicks,
                    rotateLabels=self.rotateLabels,
                    tooltips=self.tooltips,
                    stacked=self.stacked,
                    translateLabelsX=self.translateLabelsX,
                    translateLabelsY=self.translateLabelsY,
                    staggerLabels=self.staggerLabels,
                    forceY=self.forceY,
                    groupSpacing=self.groupSpacing)


class PieChart(Chart):
    """
    :param title: The chart title
    :param key: The name of the dataset
    :param values: List of dicts each with 'label' and 'value' keys
                   e.g. [{'label': 'One', 'value': 1}, ...]

    Class fields:
        marginTop: Top Margin in pixels
        marginLeft: Left Margin in pixels
        marginRight: Right Margin in pixels
        marginBottom: Bottom Margin in pixels
        showLabels: True to show labels
        donut: Draw chart as a donut.
        tooltips: True to show tooltips
    """

    template_partial = 'reports/partials/graphs/pie_chart.html'

    def __init__(self, title, key, values, color=None):
        if not color:
            color = []
        self.title = title
        self.data = [dict(key=key, values=values)]
        self.marginTop = 30
        self.marginRight = 20
        self.marginBottom = 50
        self.marginLeft = 80
        self.showLabels = True
        self.donut = False
        self.tooltips = True
        self.color = color

    def config_dict(self):
        return dict(margin={'top': self.marginTop,
                            'right': self.marginRight,
                            'bottom': self.marginBottom,
                            'left': self.marginLeft},
                    showLabels=self.showLabels,
                    tooltips=self.tooltips,
                    donut=self.donut,
                    color=self.color)
