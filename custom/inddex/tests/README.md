### About the Tests

A quick overview on how the tests are setup:

The tests code includes realistic example data in the example_data directory. This is used by the populate_inddex_test_domain management command to bootstrap a local environment. This same dataset is also used for tests.

The case data is in foodrecall_cases.csv and food_cases.csv (the former is where age_years_calculated is initially supplied). The master report is based primarily on the food_consumption_indicators.json data source, which has a row for each food case, but includes information from the parent case. The master report also relies on the fixtures set up by example_data. When updating the reports or the base data set, you can update the expected reports directly with how the output should change. Alternatively, once you're sure the output is correct, you can also temporarily uncomment the _overwrite_report lines in the tests to write the output to disk.
