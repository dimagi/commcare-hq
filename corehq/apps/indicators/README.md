# CommCare HQ Indicators

## Overview

You can split the indicators into two categories:

- Document Indicators
- Dynamic Indicators

## Document Indicators

Document Indicators are precomputed and stored inside of the `computed_` property of an `XFormInstance` or
`CommCareCase`. Each indicator is namespaced, and the result that's stored inside the document looks something like:

```javascript
computed_: {
    namepspace: {
        indicator_slug: {
            version: <int>, \\ the version number
            value: '', \\ result from from get_clean_value()
            multi_value: <bool>, \\ true if value contains a dict, false otherwise
            type: '', \\ doc_type of the Indicator Definition used to create this
            updated: <date> \\ date of last document update for this indicator
        }
    }
}
```

### Versioning

Version numbers are used if when indicator definition changes and you want to update the indicators set in documents
that have already been processed. This comes from `update_computed_namespace`.

### How are indicators updated?

#### Pillowtop

As `XFormInstance` or `CommCareCase` documents are created or updated (by processes not related to indicator updates)
they will get picked up in the changes feed by the `FormIndicatorPillow` or `CaseIndicatorPillow`, respectively.

#### Retrospectively with `mvp_force_update`

Right now there is a management command that lives inside the `mvp-reports` submodule. This management command grabs
all of the related documents by `xmlns` and `domain` (for `XFormInstance`) and `case_type` and `domain`
(for `CommCareCase`). It checks to see whether the indicator inside each document exists with the version number
specified by the indicator definition. If it doesn't exist, the indicator is added and the document is saved.

Because some domains have quite a few documents, this management command is throttled to update only 100 documents at
a time, and runs `prime_views` in between each set of 100 documents. It's a work in progress, and we should definitely
find a better solution for this process in the future.

## Dynamic Indicators

Dynamic indicators
