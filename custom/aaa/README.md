# Overview

This is a custom reporting dashboard for the AAA Convergence Pilot (sometimes known as REACH).
Its basically the same thing as CAS, but supporting a few more workflows by adding ASHA and ANM workers.

There's a combination of Django models and custom SQL insert/aggregation queries.
This combination has been chosen because there's already a decent amount of knowledge and workflow
around Django models and migrations, but it would be very difficult to perform large aggregation
queries in the ORM.

# Collection of Data

Collecting data from the application should be done via UCR data sources.
These are stored in ./ucr/data_sources.
When writing these care should be taken to ensure there are no (or few) extra queries.
Each data source only pulls information from directly from the case of form and an id to relate to another data source.

For example, the eligible_couple_forms data source listens for new submissions to the Eligible Couple Form.
We pull the person case id from the case update, so that we can join it to the relevant person case id during aggregation.

For properties that will (or should) stay the same during the lifetime of the case, we should pull these using a case data source.
Some examples of this are "dob", "sex", or "name".
It's technically possible for these to change in the app, but only in the event that the original value was incorrect.

For properties that can change throughout the lifetime of the case, these properties should be pulled from case updates inside forms.
The reason for this is because we do not store case history in any models.
An example of this is to determine if a woman is pregnant, we cannot use the "is_pregnant" case property.
We must use "opened_on" and "add" on the ccs_record to construct the times that the woman has been pregnant (and registered in our system) over her lifetime.

# Aggregation of Data

In general the workflow of our data model is:

UCR(s) --> Beneficiary Model(s) --> Location Aggregate Table

For example to generate the Child table we aggregate data from the following UCRs:

* reach-child_health_cases
* reach-person_cases
* reach-household_cases
* reach-awc_location
* reach-village_location


And to generate our AggAwc table we pull from the Child, Woman and CcsRecord models.

To profile the aggregation queries you can use `custom.aaa.utils.explain_aggregation_queries`

# Scaling Considerations

Currently our aggregations are not going to be performant at a full national scale.
They must go through our entire dataset to regenerate the beneficiary tables.
Eventually this aggregation workflow will need to change.
The most likely option here is to add support for sequential IDs in our UCR framework.
After this we will use an aggregation workflow as described by the
[Citus blog](https://www.citusdata.com/blog/2018/06/14/scalable-incremental-data-aggregation/).

Some more discussion on this point can be found in the original [GitHub PR](https://github.com/dimagi/commcare-hq/pull/23243).

There will also be a move to using the Citus postgres extension and distributing these tables over multiple shards.
With this it will mean that we will need a sharding key and as such we may need related document lookups in data sources to allow them to shard efficiently.

# Testing

To test the aggregation logic we have a set of CSV files in ./tests/data/ucr_tables.
These are copies of the UCR table definitions with some data representing cases.
Any additions to these should include names that represent the use case being tested.

The expected output of the aggregation tables are stored in ./tests/data/agg_tables.

A useful workflow for testing changes is:

1. Add a new case to UCR table file(s)
2. Modify the tables in the agg table files with what you expect to be the outcome.
3. Ensure that tests fail.
4. Update the aggregation queries to perform the aggregation you need.
5. Ensure the tests pass. If they fail figure out if you did step 2 or 4 incorrectly and adjust accordingly.

The agg tables should stay sorted (the way they're sorted are defined by `sort_key` in their automated test)

If there is a need to mass copy a table to a CSV file, you can use postgresql's \copy directive.

If you need to setup these tables outside of the automated tests,
then you can use the provided helper `_setup_ucr_table` to load the UCR data sources,
and run the aggregation in a Django shell.

To do large scale transformations on CSV files, the following tools are helpful:

[q](http://harelba.github.io/q/)
[csv.vim](https://github.com/chrisbra/csv.vim)

# References

[Reporting Indicator Specification](https://docs.google.com/spreadsheets/d/1fPFIVOaI0ZJkSqw8DJ-wmMyTefMbGXYGyhcB9UUxXnE/edit#gid=1200281692)
[Program Overview Specification](https://docs.google.com/document/d/1MY7KDvKPiqGOJ8IcZvJHJXfw--XM_AdADkQmvzQC_pw/edit#heading=h.wy4ie3jgt96i)
[Unified Beneficiary Specification](https://docs.google.com/document/d/1sPXnecPP2saBYgS3f-IGXm0U2S9TCwxUQUfbewLPRIE/edit#)
