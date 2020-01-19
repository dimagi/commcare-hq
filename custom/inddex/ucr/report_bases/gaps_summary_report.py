from custom.inddex.utils import MultiTabularReport


class GapsSummaryByFoodTypeBase(MultiTabularReport):
    # TODO: Processed Data Exports ???
    title = '1a: Gaps Report Summary by Food Type'
    name = f'{title}s'
    slug = 'gaps_report_summary_by_food_type'
    export_only = False
    show_filters = True

    @property
    def report_context(self):
        context = super(GapsSummaryByFoodTypeBase, self).report_context
        context['export_only'] = self.export_only

        return context

    @property
    def fields(self):
        return super(GapsSummaryByFoodTypeBase, self).fields

    @property
    def report_config(self):
        return super(GapsSummaryByFoodTypeBase, self).report_config

    @property
    def data_providers(self):
        raise super(GapsSummaryByFoodTypeBase, self).data_providers
