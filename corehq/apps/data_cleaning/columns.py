from django_tables2.columns import TemplateColumn


class DataCleaningHtmxColumn(TemplateColumn):
    template_name = "data_cleaning/columns/column_main.html"

    def __init__(self, column_spec, *args, **kwargs):
        """
        Defines the django2_template compatible column object
        for the bulk data cleaning feature.

        :param column_spec: BulkEditColumn
        """
        super().__init__(
            template_name=self.template_name,
            accessor=column_spec.prop_id,
            verbose_name=column_spec.label,
            *args, **kwargs
        )
        self.column_spec = column_spec
