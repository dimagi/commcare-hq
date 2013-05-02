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
            version: <int>, // the version number
            value: '', // result from from get_clean_value()
            multi_value: <bool>, // true if value contains a dict, false otherwise
            type: '', // doc_type of the Indicator Definition used to create this
            updated: <date> // date of last document update for this indicator
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

Dynamic Indicators are computed 'on-the-fly' when the report referencing that indicator is rendered (or cached data is
retrieved). Existing examples of such reports can be found in the `mvp-reports` submodule: `mvp.reports.mvis` and
'mvp.reports.chw`.

There are essentially two types of Dynamic Indicators.

### Couch-Based Indicators

The simplest form is `CouchIndicatorDef`. It uses couch views that emit lines in the following format:

```
emit(["all", doc.domain, <indicator_key>, <year>, <month>, <day>, <optional_suffix>], 1 or <something>);
emit(["user", doc.domain, user_id, <indicator_key>, <year>, <month>, <day>, <optional_suffix>], 1 or <something>);
```

The value of what is emitted is used for computing different flavors of the Couch-Based Indicators. The simplest type,
however, just returns the reduced value of the view for whatever indicator key + date range you specify.

#### Essentials for Couch-Based Indicators

- `couch_view` - The name of the couch_view that contains the indicator key that you are interested in.
- `indicator_key` - The value in the emit string above where `<indicator_key>` is present.

Optional date shifts:
- `startdate_shift` - Shift the startdate of the datespan by n days. (+n is forward -n is backwards, as you expect)
- `enddate_shift` - Shift the enddate of the datespan by n days.
- `fixed_datespan_days` - Starddate of the datespan is completely discarded and a new startdate of `enddate - fixed_datespan_days` is used.
- `fixed_datespan_months` - Same functionality as above, except instead of days, it's months.

#### Other types of Couch-Based Indicators

##### `CountUniqueCouchIndicatorDef`

This counts the number of unique emitted entries. Example usage: Form indicators emit a case_id. This counts the # of unique case_ids at the end.

##### `MedianCouchIndicatorDef`

Takes the median of the emitted values.

##### `SumLastEmittedCouchIndicatorDef`

The emitted value looks something like:

```javascript
{
    _id: "", // unique ID string
    value: <int>
}
```

This will take all the values of the last emit with a unique id and sum those values.

#### Example Usage

Couch views for Couch-Based Indicators can be found in the `submodules/mvp/mvp_apps` couchapp.

Visit [http://www.commcarehq.org/a/mvp-potou/indicators/](http://www.commcarehq.org/a/mvp-potou/indicators/) for example
indicator definitions.


### Combined Indicators

For the indicators that require ratios between two existing indicators (always referenced by their slugs), use
`CombinedCouchViewIndicatorDefinition` and specify the `numerator_slug` and `denominator_slug`.

