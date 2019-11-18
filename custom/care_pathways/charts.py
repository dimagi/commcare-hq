from corehq.apps.reports.graph_models import MultiBarChart


class PathwaysMultiBarChart(MultiBarChart):
    template_partial = 'care_pathways/partials/multi_bar_chart.html'
