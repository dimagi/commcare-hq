from collections import defaultdict
from corehq.apps.users.models import CouchUser
from custom.openclinica.const import AUDIT_LOGS
from custom.openclinica.utils import (
    OpenClinicaIntegrationError,
    is_item_group_repeating,
    is_study_event_repeating,
    get_item_measurement_unit,
    get_question_item,
    get_oc_user,
    get_study_event_name,
)


class Subject(object):
    """
    Manages data for a subject case
    """
    def __init__(self, subject_key, study_subject_id, domain):
        self.subject_key = subject_key
        self.study_subject_id = study_subject_id

        # We need the domain to get study metadata for study events and item groups
        self._domain = domain

        # This subject's data. Stored as subject[study_event_oid][i][form_oid][item_group_oid][j][item_oid]
        # (Study events and item groups are lists because they can repeat.)
        self.data = {}

    def get_report_events(self):
        """
        The events as they appear in the report.

        These are useful for scheduling events in OpenClinica, which cannot be imported from ODM until they have
        been scheduled.
        """
        events = []
        for study_events in self.data.itervalues():
            for study_event in study_events:
                events.append(
                    '"{name}" ({start} - {end})'.format(
                        name=study_event.name,
                        start=study_event.start_short,
                        end=study_event.end_short))
        return ', '.join(events)

    def get_export_data(self):
        """
        Transform Subject.data into the structure that CdiscOdmExportWriter expects
        """
        mkitemlist = lambda d: [dict(v, item_oid=k) for k, v in d.iteritems()]  # `dict()` updates v with item_oid

        def mkitemgrouplist(itemgroupdict):
            itemgrouplist = []
            for oid, item_groups in itemgroupdict.iteritems():
                for i, item_group in enumerate(item_groups):
                    itemgrouplist.append({
                        'item_group_oid': oid,
                        'repeat_key': i + 1,
                        'items': mkitemlist(item_group.items)
                    })
            return itemgrouplist

        mkformslist = lambda d: [{'form_oid': k, 'item_groups': mkitemgrouplist(v)} for k, v in d.iteritems()]

        def mkeventslist(eventsdict):
            eventslist = []
            for oid, study_events in eventsdict.iteritems():
                for i, study_event in enumerate(study_events):
                    eventslist.append({
                        'study_event_oid': oid,
                        'repeat_key': i + 1,
                        'start_long': study_event.start_long,
                        'end_long': study_event.end_long,
                        'forms': mkformslist(study_event.forms)
                    })
            return eventslist

        return mkeventslist(self.data)
