from corehq.apps.reports.dispatcher import ReportDispatcher, ProjectReportDispatcher, datespan_default
from corehq.apps.fixtures.views import require_can_edit_fixtures
from django.utils.decorators import method_decorator


class FixtureInterfaceDispatcher(ProjectReportDispatcher):
	prefix = 'fixture_interface'
	map_name = 'FIXTURE_INTERFACES'

	@method_decorator(require_can_edit_fixtures)
	def dispatch(self, request, domain, *args, **kwargs):
		self.domain = domain
		return super(UploadItemLists, self).dispatch(request, *args, **kwargs)
