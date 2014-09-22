from corehq.apps.reports.generic import GenericTabularReport, GetParamsMixin
from corehq.apps.reports.standard import CustomProjectReport
from corehq.toggles import PATHWAYS_PREVIEW
from custom.care_pathways.utils import get_domain_configuration


class CareReportMixin(object):
    @property
    def report_config(self):
        config = dict(
            domain=self.domain,
            ppt_year=self.request.GET.get('year', ''),
            value_chain=self.request.GET.get('type_value_chain', ''),
            domains=tuple(self.request.GET.getlist('type_domain', [])),
            practices=tuple(self.request.GET.getlist('type_practice', [])),
            owner_id=self.request.GET.get('cbt_name', ''),
            gender=self.request.GET.get('gender', ''),
            group_leadership=self.request.GET.get('group_leadership', ''),
            schedule=self.request.GET.get('farmer_social_category', ''),
            none=0,
            some=1,
            all=2
        )
        hierarchy_config = get_domain_configuration(self.domain).geography_hierarchy
        for k, v in sorted(hierarchy_config.iteritems(), reverse=True):
            req_prop = 'geography_%s' % v['prop']
            if self.request.GET.getlist(req_prop, []):
                config.update({k: tuple(self.request.GET.getlist(req_prop, []))})
                break
        return config


class CareBaseReport(GetParamsMixin, GenericTabularReport, CustomProjectReport, CareReportMixin):

    @classmethod
    def show_in_navigation(cls, domain=None, project=None, user=None):
        if domain and project and user is None:
            return True
        if user and PATHWAYS_PREVIEW.enabled(user.username):
            return True
        return False
