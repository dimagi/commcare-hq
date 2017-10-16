"""
# Usage

$ python raw_data.py <lastX-datespan> <interval>

This extracts raw data from few ICDS datadog timeseries metrics and prints to
stdout. Duration can be specified by 'lastX' and 'startX'
(for e.g. last5, start10 to indicate from 10 days ago to 5 days ago).
Either an 'hourly' or 'monthly' sampling interval can be specfied as well.

# Adding a new metric

Current metrics that the script extracts is defined in the below
METRICS dict. To include any new metric, simply add it to METRICS dict.
"""

import time
import re
import sys

from datadog import initialize, api
from datetime import datetime


OPTIONS = {
    'api_key': '29251913a8f80abba985a4db87b209ee',
    'app_key': 'b83af867e36bc44f03adedced8e6e0cba99c1934'
}
METRICS = {
    'submission_count': "sum:nginx.requests{environment:icds,url_group:receiver}",
    'submission_count_success': "sum:nginx.requests{environment:icds,url_group:receiver,status_code:201}",
    'restores_count': "sum:nginx.requests{environment:icds,url_group:phone}",
    'restores_count_success': "sum:nginx.requests{environment:icds,url_group:phone,status_code:200}",
    # 'storage': "sum:system.disk.used{environment:icds,device:/dev/mapper/consolidated-data1}",
}
INTERVALS = {
    # Even though we can set granularity, datadog has limit on max points it can return in a go
    # see https://help.datadoghq.com/hc/en-us/articles/204526615-What-is-the-rollup-function-
    'hourly': 60*60,
    'daily': 60*60*24,
    '15min': 15*60,
}
initialize(**OPTIONS)


def get_query_results(lastX, startX, interval):
    # queries datadog API for all metrics for 'lastX' days, at given 'interval'
    assert interval in INTERVALS, "Unknown interval"

    start, end = get_datespan(lastX, startX)
    query = ", ".join([
        make_query(m, interval)
        for m in METRICS.keys()
    ])
    return api.Metric.query(start=start, end=end, query=query)


def make_query(metric, interval):
    # modify the query to sample at given 'interval'
    return "{metric}.rollup(sum, {interval})".format(
        metric=METRICS[metric],
        interval=INTERVALS[interval]
    )


def print_csv_series(results):
    # parse and print datadog query results in a CSV format
    data = results['series'][0].get('pointlist', [])
    print ", ".join(["date"] + METRICS.keys())
    for i in range(0, len(data)):
        posix_time = data[i][0]
        datespan = datetime.fromtimestamp(posix_time / 1000)  # python datetime POSIX TZ issue
        print ", ".join([str(datespan)] + [
            str(series['pointlist'][i][1])
            for series in results['series']
        ])


def get_datespan(lastX, startX):
    # returns a (from, to) datetime tuple from 'startX' days ago till 'lastX' days
    assert re.match(r'last\d+', lastX), "Use lastX to specify last X days"
    assert re.match(r'start\d+', startX), "Use startX to specify offset of X days"
    numdays = int(re.findall(r'\d+', lastX)[0]) or 1
    days_ago = int(re.findall(r'\d+', startX)[0]) or 0
    end = int(time.time()) - days_ago*24*60*60
    start = end - numdays*24*60*60
    return (start, end)

[_, lastX, startX, interval] = sys.argv
print_csv_series(get_query_results(lastX, startX, interval))
