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
        self.marginTop = 30
        self.marginRight = 20
        self.marginBottom = 50
        self.marginLeft = 80
        self.showControls = True
        self.showLegend = True
        self.reduceXTicks = False
        self.rotateLabels = 0
        self.tooltips = True
        self.stacked = False
        self.translateLabelsX = 0
        self.translateLabelsY = 0
        self.staggerLabels = False
        self.groupSpacing = 0.3

    def add_dataset(self, key, values, color=None):
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
                    groupSpacing=self.groupSpacing)


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
