class DrilldownReportMixin(object):

    report_template_path = ""

    hide_filters = True
    filters = []
    flush_layout = True
    fields = []
    es_results=None

    @property
    def render_next(self):
        return None if self.rendered_as == "async" else self.rendered_as

    @classmethod
    def show_in_navigation(cls, *args, **kwargs):
        return False