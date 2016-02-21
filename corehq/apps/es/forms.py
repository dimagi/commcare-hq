"""
FormES
--------
"""
from .es_query import HQESQuery
from . import filters


class FormES(HQESQuery):
    index = 'forms'
    default_filters = {
        'is_xform_instance': {"term": {"doc_type": "xforminstance"}},
        'has_xmlns': {"not": {"missing": {"field": "xmlns"}}},
        'has_user': {"not": {"missing": {"field": "form.meta.userID"}}},
    }
    @property
    def builtin_filters(self):
        return [
            xmlns,
            app,
            submitted,
            completed,
            user_id,
        ] + super(FormES, self).builtin_filters

    def user_aggregation(self):
        return self.terms_aggregation('form.meta.userID', 'user')

    def completed_histogram(self, timezone=None):
        return self.date_histogram('date_histogram', 'form.meta.timeEnd', 'day', timezone=timezone)

    def submitted_histogram(self, timezone=None):
        return self.date_histogram('date_histogram', 'received_on', 'day', timezone=timezone)

    def domain_aggregation(self):
        return self.terms_aggregation('domain', 'domain')


def xmlns(xmlns):
    return filters.term('xmlns.exact', xmlns)


def app(app_id):
    return filters.term('app_id', app_id)


def submitted(gt=None, gte=None, lt=None, lte=None):
    return filters.date_range('received_on', gt, gte, lt, lte)


def completed(gt=None, gte=None, lt=None, lte=None):
    return filters.date_range('form.meta.timeEnd', gt, gte, lt, lte)


def user_id(user_ids):
    return filters.term('form.meta.userID', list(user_ids))
