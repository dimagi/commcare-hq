# Commcare Reporting

More info available at https://commcare-hq.readthedocs.io/reporting.html

## Custom reporting
### Terms:
* indicator fact - contirbutions to an indicator from individual documents (form / case)
  * e.g. 1 birth at clinicA on 2013-02-01 from case 123
* indicator grain - aggreagtion of facts at the most detailed level
  * e.g. 3 births at clinicA on 2013-02-01
* Fluff - python processors that calculate facts in real time
  * Each new version of a document causes the document to be passed to fluff which caluculates all the indicator
  facts for that document.
* CTable - python library for writing indicators to SQL
  * Reads data form CouchDB views and translates it into SQL insert / update statments based on pre-defined mappings.
  * Can also listen to changes from Fluff to provide real time updates to the SQL data.

### Brief overview:
In order to produce a custom report for a project there are two or three components that need to be considered:
1. Extracting the indicator facts from the cases / forms.
  * Write custom CouchDB views that emit the indicator facts.
  * Write a Fluff pillow to create IndicatorDocuments with the indicator facts.
2. Optionally (but recommended) creating the ctable mappings.
3. Creating the report 'view'. Options are:
  * Completely custom (class extends GenericTabularReport).
  * If data is in SQL table, extend SqlTabularReport.

### Writing couchdb views to use with ctable

The best output format of indicator facts to use for couchdb views for consumption by ctable is as follows:

`key = [date, <filter and group by parameters>, 'indicator_name'], value = N`

* Filter and group by parameters
  * These are any values that are required to filter or group the report by e.g. location, user etc.
* Indicator name
  * This is the name of the indicator to which this 'fact' is contribution.
* N
  * The numeric value that this fact is contribution to the indicator

e.g.
Indicator: Number of referrals per patient type per village (reported on a monthly basis)

Filter and group by parameters: village, patient type, date
Indicator name: 'referrals'

Couch view output: `([date, village, patient_type, 'referrals'], 1)`

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

## Example fully custom report
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
```

## Example SQL report
See SqlTabularReport for more detailed docs.

```python


class DemoReport(SqlTabularReport, CustomProjectReport, DatespanMixin):
    name = "SQL Demo"
    slug = "sql_demo"
    field_classes = (DatespanFilter,)
    datespan_default_days = 30
    group_by = ["user"]
    table_name = "user_report_data"

    @property
    def filters(self):
        return [
            "date between :startdate and :enddate"
        ]

    @property
    def filter_values(self):
        return {
            "startdate": self.datespan.startdate_param_utc,
            "enddate": self.datespan.enddate_param_utc
        }

    @property
    def keys(self):
        # would normally be loaded from couch
        return [["user1"], ["user2"], ['user3']]

    @property
    def columns(self):
        user = DatabaseColumn("Username1", "user", column_type=SimpleColumn, format_fn=self.username)
        i_a = DatabaseColumn("Indicator A", "indicator_a")
        i_b = DatabaseColumn("Indicator B", "indicator_b")

        agg_c_d = AggregateColumn("C/D", self.calc_percentage,
                                  SumColumn("indicator_c"),
                                  SumColumn("indicator_d"),
                                  format_fn=self.format_percent)

        return [
            user,
            i_a,
            i_b,
            agg_c_d
        ]

    _usernames = {"user1": "Joe", "user2": "Bob", 'user3': "Gill"}  # normally loaded from couch
    def username(self, key):
        return self._usernames[key]

    def calc_percentage(num, denom):
        if isinstance(num, Number) and isinstance(denom, Number):
            if denom != 0:
                return num * 100 / denom
            else:
                return 0
        else:
            return None

    def format_percent(self, value):
        return format_datatables_data("%d%%" % value, value)
```
