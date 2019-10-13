Data Warehouse
==============
See background [design document](https://docs.google.com/document/d/1sMTEAG-iZyo0nfp2S4sUaN2MgY31Z8B3kRDBqPFXvnI/edit#)
for an overview of design of our data warehouse. This doc mainly explains steps for developing warehouse models.

## Key Models

All the data required to filter and render a particular report is captured in that report's 'facts' data models.
CommCareHQ's raw data models are processed to extract report 'facts'.
This process can be thought of as an ETL.
The warehousing app consists of various data models, the ETL processing code and some additional
utilities such as [Airflow](https://github.com/dimagi/pipes/) to administer the ETL process.

Below describes data warehouse models and the process to load and clear the data for these models.

There are three kinds of warehouse data models:
* Fact
  * represent final report data
* Dimension
  * categorizes the fact data and allows filtering for reports
* Staging
  * temporary data read from CommCareHQ data models and used to derive the fact and dimension data

See [facts.py](models/facts.py), [dimensions.py](models/dimensions.py) and [staging.py](models/staging.py) for
the actual model classes.

## ETL
The process of filling the tables in the warehouse generally involves two steps:
* Extract data from CommCareHQ models into staging tables in the warehouse
* Run SQL queries in the warehouse DB to copy data from staging tables to the dimension and fact tables
  * restructure the data where necessary
  * link data to dimensions

This process is triggered and managed by [Airflow](https://github.com/dimagi/pipes/) which executes CommCareHQ
management commands for the various steps. The general workflow is as follows:

* initialize a 'batch' to indicate date range for the data
* for the batch date range, load raw data into staging tables
* process staging tables to insert data into dimension and fact tables
* update the batch to indicate completion

Example workflow:

```
# create a new batch with end date = '2018-06-05'. Start date will be taken from the previous batch
# or default to a minimum date.
# The command will output the ID of the batch created.
$ ./manage.py create_batch slug 2018-06-05
73

# Run the ETL for the application tables
$ ./manage.py commit_table application_staging 73
$ ./manage.py commit_table application_dim 73
$ ./manage.py mark_batch_complete 73
```

The full workflow can be seen in the Airflow UI or the [Airflow dag graphs](https://github.com/dimagi/pipes/blob/master/docs/warehouse/warehouse.md).

### Table loaders
The ETL for each 'table' is handled by a specific 'loader' class. These classes contain the logic necessary
to fill the warehouse table they are responsible for. There are two categories of loaders:

* staging loader
* fact / dimension loader

The only difference between the two is that the staging loader will clear any previous data as the first
step whereas the other one will not.

There are also 2 different loading strategies:

* loading data from CommCareHQ models into warehouse tables
  * this strategy is only used for staging tables
* executing SQL scripts to move data between tables in the warehouse
  * these loaders run [SQL scripts](transforms/sql) based on the loaders `slug`
