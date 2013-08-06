from django.core.management.base import BaseCommand, CommandError
from corehq.apps.domain.models import Domain, DynamicReportSet, DynamicReportConfig


class Command(BaseCommand):
    args = '<domain> <section> <name> <mode> <type> <field>'
    help = 'Bootstrap pie charts for a given domain'

    def handle(self, *args, **options):
        if len(args) != 6:
            raise CommandError('Usage is copy_domain %s' % self.args)

        domain, section_title, mode, report_name, submission_type, field = args
        assert mode in ('case', 'form'), 'mode must be "case" or "form"'

        project = Domain.get_by_name(domain)

        # todo: move this to domain object
        def _get_dynamic_report_section(project, title):
            for report_set in project.dynamic_reports:
                if report_set.section_title == title:
                    return report_set
            return None

        # todo: move this to DynamicReportSet object
        def _get_dynamic_report(section, name):
            for report in section.reports:
                if report.name == name:
                    return report
                return None

        report_kwargs = {
            'mode': mode,
            'submission_type': submission_type,
            'field': field,
        }
        def _make_report():
            # closures!
            return DynamicReportConfig(
                report='corehq.apps.reports.standard.inspect.GenericPieChartReportTemplate',
                name=report_name,
                kwargs=report_kwargs,
            )

        report_section = _get_dynamic_report_section(project, section_title)
        if report_section:
            report = _get_dynamic_report(report_section, report_name)
            if report:
                report.kwargs = report_kwargs
            else:
                report = _make_report()
                report_section.reports.append(report)
            report_section.save()
        else:
            report_section = DynamicReportSet(
                section_title=section_title,
                reports=[
                    _make_report()
                ]
            )
            project.dynamic_reports.append(report_section)

        project.save()
