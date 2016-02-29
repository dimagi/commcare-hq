## Custom UCR expressions for ICDS reports

### Reports background
ICDS Tableau reporting uses UCR data-sources as the base data. The UCR datasources are mainly case data and they are configured to calculate indicators as on a snapshot duration (for e.g. a child case as a year ago) (this is done via stock UCR using `base_item_expression`). Most of these indicators need form lookups which can't be done in stock UCR. Following custom UCR expressions are made available to make such form lookup calculations possible in ICDS reports.

### Custom UCR expression
All custom case-type indicators can be calculated via ICDS custom ucr expression. The expression takes four arguments, `case_type`, `indicator_name`, `start_date` and `end_date`. `case_type` can be any supported case-type. `indicator_name` is the name of the indicator that needs custom form lookup calculation. The list of supported case-types and indicators are listed in the ICDS reports spec. `start_date` and `end_date` specify the duration to snapshot the case in and can be any valid date expressions or valid date strings.

#### 'icds_indicator_expression' examples

##### Example 1

To get `age_in_months` indicator in `child_health` UCR

```json
"expression": {
    "type": "icds_indicator_expression",
    "case_type": "child_health"
    "indicator_name": "age_in_months",
    "start_date": {
        "type": "named",
        "name": "iteration_start_date"
    },
    "end_date": {
        "type": "named",
        "name": "iteration_end_date"
    }
}
```

##### Example 2

To get `age_in_years` indicator in `ccs_record` UCR

```json
"expression": {
    "type": "icds_indicator_expression",
    "case_type": "ccs_record"
    "indicator_name": "age_in_years",
    "start_date": {
        "type": "named",
        "name": "iteration_start_date"
    },
    "end_date": {
        "type": "named",
        "name": "iteration_end_date"
    }
}
```

#### List of supported case-types and indicators

Following are supported list of case-types and corresponding indicators are in the [spec-sheet](https://docs.google.com/spreadsheets/d/10sL0Iwdh6CGiSh49KfWoeG9F7t5qiixFmBAjEaLgKPo/edit#gid=267403337). Each sheet here corresponds to a case-type, and row in each sheet corresponsd to a supported indicator