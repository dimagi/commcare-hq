# Commcare Reporting

A basic report:

```python
class MyBasicReport(GenericTabularReport, CustomProjectReport, DatespanMixin):
    name = "My Basic Report"
    slug = "my_basic_report"
    fields = (DatespanMixin.datespan_field)

    @property
    def headers(self):
        return DataTablesHeader(DataTablesColumn("Col A"),
                                DataTablesColumnGroup("Goup 1", DataTablesColumn("Col B"),
                                                      DataTablesColumn("Col C")),
                                DataTablesColumn("Col D"))

    @property
    def rows(self):
        return [
            ['Row 1', 2, 3, 4],
            ['Row 2', 3, 2, 1]
        ]

## Custom reporting
### Terms:
* indicator grain - individual records that contribute to an indicator total e.g. 1 birth at clinicA on 2013-02-01
* Fluff - python processors that calculate indicators in real time (as the data is changing)
* CTable - python library for writing indicators to SQL

### Brief overview:
* Custom CouchDB views emit indicator grains based on cases / forms.
* CTable periodically reads the indicator grains from the custom views and writes them to SQL (configurable by read
schedule as well as query filters).

* Fluff pillows calculate indicator grains in real time and update IndicatorDocuments in CouchDB.
* Fluff view emits indicator grains from IndicatorDocuments.
* Fluff also notifies CTable of grain level changes.
* CTable re-calculates grains that have changed by querying the Fluff indicator view and writes them to SQL.

### The basic idea

Each report broken into set of indicators that can be calculated on a per document level where the key is the set of
filters and the value is usually a the value that this document contributes to the indicator.

e.g.
Indicator: Number of referrals per patient type per village (reported on a monthly basis) results in an set of
records of the following format for any document that contributes to the indicator:

([village, patient_type, 'referrals', date], 1)

These could then be aggregated across the various filters to get the final indicator.

The output of this view could be consumed by any external reporting service that the reports / aggregation
could be built on top of (or the reports could run directly off couchdbkit-aggregate, but that is likely a
bad interface for querying) e.g. ctable extracts the view data to a table in SQL.

### Counting unique values
Kenn suggested using bit flipping to do unique counts e.g. open case at a particular date. In this case would be
represented by a single bit in a binary blob. The case is mapped to a unique bit by hashing its unique ID.

Doing count accross filter ranges becomes a matter or ORing the bit sets and counting the number of positive bits

  e.g.
  Open cases in some time period (days)
  Each case would then result in one record for each day that it was open where the value is binary blob with a single
  bit (representing this case) is = 1. The specific bit that is set to 1 is determined by hashing the unique case ID.

  [2013,01,01,"open_case"] = [0,0,0,0,0,1,0,0,0]
  [2013,01,02,"open_case"] = [0,0,0,0,0,1,0,0,0]
  [2013,01,03,"open_case"] = [0,0,0,0,0,1,0,0,0]

More on this technique here: http://highscalability.com/blog/2012/4/5/big-data-counting-how-to-count-a-billion-distinct-objects-us.html

Read only DB per domain

To get some level of data segregation for improved performance it was suggested to use a read only DB per domain
that houses all the report views and logic. This DB would be kept up to date with the main DB but would only be used
for generating reports. This would make the indexing or the data much faster since there is less data.
It would also provide some protection to the rest of the databases from any errors in custom views etc. It would
also remove all the custom report views from the main DB.

