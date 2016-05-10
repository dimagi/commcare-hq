First, we build a data structure representing all of the things that could be exported from a form
This is called an `ExportDataSchema`.

```python
export_data_schema = ExportDataSchema(
    tables=[
        ExportableTableSchema(
            path=[]  # This would be non empty if this table represented a repeat group
            items=[
                ScalarItem(
                    path=["form", "q1"],
                    label="Question 1",
                ),
                MultipleChoiceQuestion(
                    path=["form", "q2"],
                    label="Question 2",
                    options=["yes", "no"]
                )
            ]
        )
    ]
)
```

Next, we build a default `ExportInstance`. The instance represents which questions and meta data
will be included in the export, what the names of the columns will be, what file format it will
be in, etc. If we were editing an existing export, we wouldn't use a default `ExportInstance`, we
would use the existing instance representing the export instead.

The default `ExportInstance` will look something like this:

```python
export_instance = ExportInstance(
    tables={
        export_data_schema.tables[0].path: TableConfiguration(
            name="Form",
            columns={
                 export_data_schema.tables[0].items[0]: ColumnConfiguration(
                    label=export_data_schema.tables[0].items[0].label
                 ),
                 export_data_schema.tables[0].items[1]: ColumnConfiguration(
                    label=export_data_schema.tables[0].items[1].label
                    expand_column=False
                 )
            }
        )
    }
)
```

I'm imagining this is built by calling something like `ExportItem.get_default_column()` or something like that
on each item in the `ExportDataSchema`.
 
Next we need to render the export configuration page. We merge the `ExportDataSchema`
and the `ExportInstance` first. The algorithm for doing so would look something like
this:

```python
def get_export_configuration_context(data_schema, export_instance):
    tables = []
    for table_schema in data_schema.tables:
        table = []
        export_instance_table = export_instance.tables[table_schema.path]
        for export_item in table_schema:
            item = {
                "checked": export_item in export_instance_table.columns
                "path": export_item.path
                "type": export_item.doc_type
                "display": 
                    export_instance_table.columns[export_item].label
                    if export_item in export_instance_table.columns
                    else export_item.label
            }
            table.append(item)
        tables.append(table)
    return tables
```

Once we've rendered the export configuration page, a user manipulates a form, and
then submits it. We update the `ExportInstance` based on the submitted form.
The `ExportDataSchema` remains unchanged, because the schema is purely dependent
on the shape of the forms in the application.
