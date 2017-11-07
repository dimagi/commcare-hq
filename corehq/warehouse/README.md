Data Warehouse
==============
See background [design document](https://docs.google.com/document/d/1sMTEAG-iZyo0nfp2S4sUaN2MgY31Z8B3kRDBqPFXvnI/edit#heading=h.h2zk9svh5s9) for an overview of design of our data warehouse. This doc mainly explains steps for developing warehouse models.

## Key Models

All the data required to filter and render a particular report is captured in that report's 'facts' data models. CommCareHQ's raw data models are process to extract report 'facts'. This process can be thought of as an ETL. The warehousing app consists of various data models, the ETL processing code and some additional utilities such as Airflow to administer the ETL process.

Below describes data warehouse models and the process to load and clear the data for these models.

There are three kinds of warehouse data models. Fact, Dimension and Staging models. Generally, fact models represent final report data, dimension models represent the 'dimensions' under which report data can be filtered and staging models represent raw data read from CommCareHQ's raw data models before they are inserted into a dimension or fact table. See facts.py, dimensions.py and staging.py for examples. Each data model has a `dependencies` attribute that specify what other data model data does it depend on.

ETL involves running commands to
- initialize a 'batch' to indicate date range for the data
- for the batch date range, load raw data into staging tables, and then 
- process staging tables to insert data into dimension and fact tables. 

Most of ETL business logic lives in raw SQL queries. See corehq/warehouse/transforms/sql/.

## Commands

Use `create_batch` to create a batch. This just creates a new batch record.

```
./manage.py create_batch 222617b9-8cf0-40a2-8462-7f872e1f1344 -s 2012-05-05 -e 2018-06-05
```

Use `commit_table <data_model_slug> <batch_id>` to load data of data_model along with any of its dependencies' data for duration specified by the batch_id. For e.g.

```
./manage.py commit_table user_staging 222617b9-8cf0-40a2-8462-7f872e1f1344
```


To flush staging data of a particular batch use `./manage.py clear_staging_records`. During the development, you could use `DROP TABLE` (or `./manage.py migrate warehouse zero`) sql commands to clear fact/dimension data.

