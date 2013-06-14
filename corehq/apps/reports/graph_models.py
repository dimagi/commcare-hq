class Axis(object):
    def __init__(self, label=None, format=None):
        self.label = label
        self.format = format


class Chart(object):
    template_partial = ''
    height = 320
    title = ''


class MultiBarChart(Chart):
    template_partial = 'reports/partials/graphs/multibar_chart.html'

    def __init__(self, title, x_axis, y_axis):
        self.title = title
        self.x_axis = x_axis
        self.y_axis = y_axis
        self.data = []
        self.margin = {'top': 30, 'right': 20, 'bottom': 50, 'left': 80}
        self.showControls = True
        self.showLegend = True
        self.reduceXTicks = True
        self.rotateLabels = 0
        self.tooltips = True
        self.stacked = False

    def add_dataset(self, key, values, color=None):
        d = dict(key=key, values=values)
        if color:
            d['color'] = color
        self.data.append(d)

    def config_dict(self):
        return dict(margin=self.margin,
                    showControls=self.showControls,
                    showLegend=self.showLegend,
                    reduceXTicks=self.reduceXTicks,
                    rotateLabels=self.rotateLabels,
                    tooltips=self.tooltips,
                    stacked=self.stacked)


class PieChart(Chart):
    template_partial = 'reports/partials/graphs/pie_chart.html'

    def __init__(self, title, data):
        self.title = title
        self.data = data
        self.margin = {'top': 30, 'right': 20, 'bottom': 50, 'left': 80}
        self.showLabels = True
        self.donut = False
        self.tooltips = True

    def config_dict(self):
        return dict(margin=self.margin,
                    showLabels=self.showLabels,
                    tooltips=self.tooltips,
                    donut=self.donut)
