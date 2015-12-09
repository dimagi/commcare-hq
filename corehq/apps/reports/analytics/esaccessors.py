from corehq.apps.es import FormES
from dimagi.utils.parsing import string_to_datetime


def get_last_submission_time_for_user(domain, user_id, datespan):
    form_query = FormES() \
        .domain(domain) \
        .user_id([user_id]) \
        .completed(gte=datespan.startdate.date(), lte=datespan.enddate.date()) \
        .sort("form.meta.timeEnd", desc=True) \
        .size(1)
    results = form_query.run().raw_hits

    def convert_to_date(date):
        return string_to_datetime(date).date() if date else None

    return convert_to_date(results[0]['_source']['form']['meta']['timeEnd'] if results else None)

