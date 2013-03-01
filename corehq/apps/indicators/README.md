# CommCare HQ Indicators

## Overview

You can split the indicators into two categories:

- Document Indicators
- Dynamic Indicators

## Document Indicators

Document Indicators are stored inside of the `computed_` property of an `XFormInstance` or `CommCareCase`. Each
indicator is namespaced, and the result looks something like:

`
computed_: {
    namepspace: {
        indicator_slug: {
            version: <version #>,
            value: <result from get_clean_value()>,
            multi_value: <True if value contains a dict, False otherwise>,
            type: <doc_type of Indicator Definition>,
            updated: <date of last document update for this indicator>
        }
    }
}
`

### Versioning

Version numbers are used if when indicator definition changes and you want to update the indicators set in documents
that have already been processed. This comes from `update_computed_namespace`.

## Dynamic Indicators


