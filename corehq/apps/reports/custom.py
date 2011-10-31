from django.shortcuts import render_to_response
from django.template.context import RequestContext

class HQReport(object):
    name = ""
    slug = ""
    description = ""
    template_name = None
    report_partial = None
    title = None
    headers = None
    rows = None
    individual = None
    case_type = None
    group = None
    form = None,
    datespan = None
    show_time_notice = False

    def __init__(self, domain, request, base_context = {}):
        if not self.name or not self.slug:
            raise NotImplementedError
        self.domain = domain
        self.request = request
        self.rows = []
        self.context = base_context
        self.context.update(name = self.name,
                            slug = self.slug,
                            description = self.description,
                            template_name = self.template_name,
        )

    def get_report_context(self):
        # circular import
        from .util import report_context
        self.context.update(report_context(self.domain,
                                        report_partial = self.report_partial,
                                        title = self.title,
                                        headers = self.headers,
                                        rows = self.rows,
                                        individual = self.individual,
                                        case_type = self.case_type,
                                        group = self.group,
                                        form = self.form,
                                        datespan = self.datespan,
                                        show_time_notice = self.show_time_notice
                                      ))

    def calc(self):
        """
        Override this function with something that updates self.context.
        """
        pass

    def get_template(self):
        if self.template_name:
            return "%s" % self.template_name
        else:
            return "reports/generic_report.html"

    def as_view(self):
        self.get_report_context()
        self.calc()
        return render_to_response("reports/generic_report.html", self.context, context_instance=RequestContext(self.request))

class SampleHQReport(HQReport):
    name = "Sample Report"
    slug = "sample"
    description = "Sample report that just gets a list of users."

    def calc(self):
        from util import user_list
        users = user_list(self.domain)
        rows = [user.name for user in users]
        self.context['rows'] = rows





