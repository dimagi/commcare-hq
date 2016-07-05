from corehq.apps.reports.generic import GenericTabularReport, GetParamsMixin
from corehq.apps.reports.standard import CustomProjectReport
from corehq.apps.style.decorators import use_nvd3_v3
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
            cbt_name=self.request.GET.get('cbt_name', ''),
            gender=self.request.GET.get('gender', ''),
            group_leadership=self.request.GET.get('group_leadership', ''),
            schedule=self.request.GET.getlist('farmer_social_category', []),
            none=0,
            some=1,
            all=2,
            test='test',
            duplicate='duplicate',
            real_or_test=self.request.GET.get('real_or_test', '')
        )
        hierarchy_config = get_domain_configuration(self.domain).geography_hierarchy
        for k, v in sorted(hierarchy_config.iteritems(), reverse=True):
            req_prop = 'geography_%s' % v['prop']
            if self.request.GET.getlist(req_prop, []) not in [[], ['0']]:
                config.update({k: tuple(self.request.GET.getlist(req_prop, []))})
                break
        return config


class CareBaseReport(GetParamsMixin, GenericTabularReport, CustomProjectReport, CareReportMixin):

    base_template_filters = 'care_pathways/filters.html'

    @use_nvd3_v3
    def decorator_dispatcher(self, request, *args, **kwargs):
        super(CareBaseReport, self).decorator_dispatcher(request, *args, **kwargs)

    @classmethod
    def show_in_navigation(cls, domain=None, project=None, user=None):
        return True

    def update_filter_context(self):
        self.context.update({
            'report_filters': [
                dict(field=f.render(), slug=f.slug, filter_css_class=f.filter_css_class)
                for f in self.filter_classes
            ],
        })
