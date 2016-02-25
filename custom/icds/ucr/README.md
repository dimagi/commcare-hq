## Custom UCR expressions for ICDS reports

### Reports background
ICDS Tableau reporting uses UCR data-sources as the base data. The UCR datasources are mainly case data and they are configured to calculate indicators as on a snapshot duration (for e.g. a child case as a year ago) (this is done via stock UCR using `base_item_expression`). Most of these indicators need form lookups which can't be done in stock UCR. Following custom UCR expressions are made available to make such form lookup calculations possible in ICDS reports.

### Custom UCR expressions
Each case-type has a custom UCR expression type, these expression take three arguments, `indicator_name`, `start_date` and `end_date`. `start_date` and `end_date` specify the duration to snapshot the case in and can be any valid date expressions or valid date strings. `indicator_name` is the name of the indicator that needs custom form lookup calculation. The list of supported indicators are listed in the ICDS reports spec for each case-type. Following is an example of custom expression for `child_health` case-type

####'child_health_indicator' expression

This can be used for custom indicators of `child_health` case-type. The list of supported indicators are listed [here](https://docs.google.com/spreadsheets/d/10sL0Iwdh6CGiSh49KfWoeG9F7t5qiixFmBAjEaLgKPo/edit#gid=0)

```json
'expression': {
    'type': 'child_health_indicator',
    'indicator_name': 'age_in_months',
    'start_date': {
        'type': 'named',
        'name': 'iteration_start_date'
    },
    'end_date': {
        'type': 'named',
        'name': 'iteration_end_date'
    }
}
```
