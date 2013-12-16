from corehq.apps.reports.dispatcher import ReportDispatcher, ProjectReportDispatcher, datespan_default

class FixtureInterfaceDispatcher(ProjectReportDispatcher):
	prefix = 'fixture_interface'
	map_name = 'FIXTURE_INTERFACES'