
#inspector methods
from __future__ import absolute_import
from __future__ import unicode_literals
from dimagi.ext.couchdbkit import Document
from datetime import datetime, timedelta
from django.db.models.base import Model
from auditcare.models import ModelActionAudit

default_excludes = ['_rev']


class ObjectHistoryWrapper(object):
    def __init__(self, obj, filter_fields=None, exclude_fields=None, start_date=None, end_date=None, **kwargs):
        self.object = obj
        self.filter_fields = filter_fields or []
        self.exclude_fields = exclude_fields or []
        self.start_date = start_date
        self.end_date = end_date

        if isinstance(obj, Model):
            #it's a django model, search by content_type
            key = [obj.__class__.__name__, str(obj.id)]
        elif isinstance(obj, Document):
            #it's a couchdbkit document, search by __class__
            key = [obj.__class__.__name__, obj._id]
        elif isinstance(obj, dict):
            #it's a couchdbkit document, search by __class__
            key = [obj['doc_type'], obj['_id']]

        final_fields = []
        if len(self.filter_fields) > 0:
            final_fields = filter_fields[:]
        self.final_fields = final_fields

        revisions=ModelActionAudit.view('auditcare/model_actions_by_id', key=key, reduce=False, include_docs=True).all()
        #need a better view to filter by date

        #todo: filter by date ranges
        #return sorted(revisions, key=lambda x: x.event_date, reverse=True)

        self.revisions=sorted(ModelActionAudit.view('auditcare/model_actions_by_id', key=key, reduce=False, include_docs=True).all(), key=lambda x: x.event_date)

    def filtered_changes(self):
        """
        Generator for the filtered fields for a given instance.

        Returns a generator of dictionaries:
        key: revision, value: model audit log
        key: changed_fields, value: a tuple of field names ([changed fields], [added fields], [removed fields])
        """
        for rev in self.revisions:
            yield {"revision": rev, 'changed_fields': rev.get_changed_fields(filters=self.filter_fields, excludes=self.exclude_fields)}


    def change_narratives(self):
        """
        Return a list of dicts:
        key: Revision, value: the model audit revision log
        key: changes, value: a generator of tuples (field_name, (from_value, to_value))
        """
        ret = []
        for rev in self.revisions:
            changed, added, removed  = rev.get_changed_fields(filters=self.filter_fields, excludes=self.exclude_fields)
            if len(changed) > 0:
                ret.append({'revision': rev, 'changes': list(rev.resolved_changed_fields(filters=self.filter_fields, excludes=self.exclude_fields))})
        return ret



def history_for_doc(obj, start_date=None, end_date=None, date_range=None, filter_fields=None, exclude_fields=None):
    """
    Get an audit history for a given object

    obj needs to be a couchdoc or a django model known to be auditable

    Optional paramters:
    start_date if None, search from the beginning of time
    end_date if None, will assume now

    date_range - if set, will assume now-date_range (days), else, will assume end_date and work backwards with the date_range days

    filter_fields are the fields in which you want to track and report back the diffs for

    exclude_fields are the fields you do not not want to track, these will override the filter_fields.

    returns a list of all the deltas by field and value
    """



    #parameter/date range checking
    if date_range is None:
        if start_date is not None and end_date is None:
            end_date = datetime.utcnow()
        elif start_date is None and end_date is not None:
            start_date = datetime.min
        elif start_date is None and end_date is None:
            #both are null, so we're talking all time
            start_date = datetime.min
            end_date = datetime.utcnow()

    elif date_range is not None:
        if start_date is None and end_date is not None:
            start_date = end_date - timedelta(days=abs(date_range))
            pass
        elif end_date is None and start_date is not None:
            #who cares if it goes into the future
            end_date = start_date + timedelta(days=abs(date_range))
            pass
        elif start_date is None and end_date is None:
            #assume that end_date is now, and we subtract
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=abs(date_range))


    return ObjectHistoryWrapper(obj, filter_fields=filter_fields, exclude_fields=exclude_fields, start_date=start_date, end_date=end_date)
