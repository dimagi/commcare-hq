from corehq.apps.reports.standard import StandardHQReport

class PathIndiaKrantiReport(StandardHQReport):
    name = "Kranti Report"
    fields = ['corehq.apps.reports.fields.FilterUsersField',
              'corehq.apps.reports.fields.DatespanField']