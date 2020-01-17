from custom.inddex.utils import MultiTabularReport


class NutrientIntakesReportBase(MultiTabularReport):
    title = '2: Nutrient Intakes by Food and by Respondent'
    name = f'{title}s'
    slug = 'nutrient_intakes_by_food_and_by_respondent'
    export_only = False
    show_filters = True

    @property
    def report_context(self):
        context = super(NutrientIntakesReportBase, self).report_context
        context['export_only'] = self.export_only

        return context

    @property
    def fields(self):
        return super(NutrientIntakesReportBase, self).fields

    @property
    def report_config(self):
        return super(NutrientIntakesReportBase, self).report_config

    @property
    def data_providers(self):
        raise super(NutrientIntakesReportBase, self).data_providers
