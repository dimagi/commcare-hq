import datetime

from corehq.util.datadog.gauges import datadog_counter


def _report_skipped_records(skipped_records):
    now = datetime.datetime.utcnow()
    for skipped_record in skipped_records:
        delay = max([0, (now - skipped_record.scheduled_for).total_seconds()])
        datadog_counter('commcare.scheduled_reports.skipped', tags={

        })
