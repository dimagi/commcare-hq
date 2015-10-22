from collections import defaultdict
from corehq.apps.users.models import CouchUser
from corehq.util.quickcache import quickcache
from custom.openclinica.const import AUDIT_LOGS, SINGLE_EVENT_FORM_EVENT_INDEX
from custom.openclinica.utils import (
    OpenClinicaIntegrationError,
    is_item_group_repeating,
    is_study_event_repeating,
    get_item_measurement_unit,
    get_question_item,
    get_oc_user,
    get_study_event_name,
    oc_format_date,
)


_reserved_keys = ('@uiVersion', '@xmlns', '@name', '#type', 'case', 'meta', '@version')


class ItemGroup(object):
    """
    One CommCare form can contribute to multiple item groups. And multiple forms can be required to
    complete one item group. When a second instance of a form type (identified by xmlns) is added to an
    item group, then the item group is closed and a new one opened.
    """
    def __init__(self, domain, oid):
        self.oid = oid
        self.completed_cc_forms = set([])
        # self.is_repeating = is_item_group_repeating(domain, oid)  # Unused. We use use CommCare repeat groups
        self.items = defaultdict(dict)


class StudyEvent(object):
    """
    Like item groups, study events can also be repeated. To make things
    interesting, repeating study events can contain repeating item groups.

    We use SINGLE_EVENT_FORM_EVENT_INDEX to know whether to create a new
    StudyEvent. In subsequent projects we should us a study_event subcase of
    the subject case type.
    """
    def __init__(self, domain, oid):
        self.oid = oid
        # Unused. We use SINGLE_EVENT_FORM_EVENT_INDEX in this project.
        # self.is_repeating = is_study_event_repeating(domain, oid)
        self.forms = defaultdict(lambda: defaultdict(list))  # a dict of forms containing a dict of item groups
        self.name = get_study_event_name(domain, oid)
        self.start_datetime = None
        self.end_datetime = None

    @property
    def start_short(self):
        """
        Format the start date and time for the UI.

        Format the date and time so that the user to copy and paste into OpenClinica
        """
        return self.start_datetime.strftime('%d-%b-%Y %H:%M')  # e.g. 01-Jan-1970 00:00

    @property
    def end_short(self):
        return self.end_datetime.strftime('%d-%b-%Y %H:%M')

    @property
    def start_long(self):
        """
        Format the start date and time for the ODM export.

        OpenClinica UI doesn't allow the user to set seconds, so theirs is always "%H:%M:00.0". Make ours match:
        """
        return self.start_datetime.strftime('%Y-%m-%d %H:%M:00.0')

    @property
    def end_long(self):
        return self.end_datetime.strftime('%Y-%m-%d %H:%M:00.0')


class Subject(object):
    """
    Manages data for a subject case
    """
    def __init__(self, subject_key, study_subject_id, domain):
        self.subject_key = subject_key
        self.study_subject_id = study_subject_id
        self.enrollment_date = None
        self.sex = None
        self.dob = None

        # We need the domain to get study metadata for study events and item groups
        self._domain = domain

        # This subject's data. Stored as subject[study_event_oid][i][form_oid][item_group_oid][j][item_oid]
        # (Study events and item groups are lists because they can repeat.)
        self.data = defaultdict(list)

        # Tracks items in self.data by reference using form ID and question. We need this so that we can
        # update an item if its form has been edited on HQ, by looking it up with new_form.orig_id.
        self.question_items = defaultdict(dict)

        # The mobile workers who entered this subject's data. Used for audit logs. The number of mobile workers
        # entering data for any single subject should be small, even in large studies with thousands of users.
        # Because we are fetching the user for every question, use a dictionary for speed.
        self.mobile_workers = {}

    def get_study_event(self, item, form):
        """
        Return the current study event. Opens a new study event if necessary.
        """
        count = len(self.data[item.study_event_oid])
        if form.xmlns in SINGLE_EVENT_FORM_EVENT_INDEX:
            # This is a bad way to determine whether to create a new event because it needs "special cases"
            # TODO: Use an "event" subcase of subject
            index = SINGLE_EVENT_FORM_EVENT_INDEX[form.xmlns]
            if count < index + 1:
                self.data[item.study_event_oid].extend([None] * (index + 1 - count))
            if self.data[item.study_event_oid][index] is None:
                self.data[item.study_event_oid][index] = StudyEvent(self._domain, item.study_event_oid)
            return self.data[item.study_event_oid][index]
        if not count:
            self.data[item.study_event_oid].append(StudyEvent(self._domain, item.study_event_oid))
        study_event = self.data[item.study_event_oid][-1]
        return study_event

    def get_item_group(self, item, form):
        """
        Return the current item group and study event. Opens a new item group if necessary.

        Item groups are analogous to CommCare question groups. Like question groups, they can repeat.
        """
        study_event = self.get_study_event(item, form)
        oc_form = study_event.forms[item.form_oid]
        if not oc_form[item.item_group_oid]:
            oc_form[item.item_group_oid].append(ItemGroup(self._domain, item.item_group_oid))
        item_group = oc_form[item.item_group_oid][-1]
        return item_group, study_event

    def get_item_dict(self, item, form, question):
        """
        Return a dict for storing item data, and current study event.

        Return both because both the item dict and study event may be updated by a form or question.
        """
        item_group, study_event = self.get_item_group(item, form)
        item_dict = item_group.items[item.item_oid]
        self.question_items[form.get_id][question] = (item_dict, study_event)
        return item_dict, study_event

    @staticmethod
    def edit_item(item_dict, form, question, answer, audit_log_id_ref, oc_user):
        if AUDIT_LOGS:
            audit_log_id_ref['id'] += 1
            item_dict['audit_logs'].append({
                'id': 'AL_{}'.format(audit_log_id_ref['id']),
                'user_id': oc_user.user_id,
                'username': oc_user.username,
                'full_name': oc_user.full_name,
                'timestamp': form.received_on,
                'audit_type': 'Item data value updated',
                'old_value': item_dict['value'],
                'new_value': answer,
                'value_type': question,
            })
        item_dict['value'] = answer

    @staticmethod
    @quickcache(['domain', 'user_id'])
    def _get_cc_user(domain, user_id):
        return CouchUser.get_by_user_id(user_id, domain)

    def _get_oc_user(self, user_id):
        if user_id not in self.mobile_workers:
            cc_user = self._get_cc_user(self._domain, user_id)
            oc_user = get_oc_user(self._domain, cc_user)
            if oc_user is None:
                raise OpenClinicaIntegrationError(
                    'OpenClinica user not found for CommCare user "{}"'.format(cc_user.username))
            self.mobile_workers[user_id] = oc_user
        return self.mobile_workers[user_id]

    def add_item(self, item, form, question, answer, audit_log_id_ref):
        oc_user = self._get_oc_user(form.auth_context['user_id'])
        if getattr(form, 'deprecated_form_id', None) and question in self.question_items[form.deprecated_form_id]:
            # This form has been edited on HQ. Fetch original item
            item_dict, study_event = self.question_items[form.deprecated_form_id][question]
            if item_dict['value'] != answer:
                self.edit_item(item_dict, form, question, answer, audit_log_id_ref, oc_user)
        else:
            item_dict, study_event = self.get_item_dict(item, form, question)
            if item_dict and item_dict['value'] != answer:
                # This form has been submitted more than once for a non-repeating item group. This is an edit.
                self.edit_item(item_dict, form, question, answer, audit_log_id_ref, oc_user)
            else:
                item_dict['value'] = answer
                if AUDIT_LOGS:
                    audit_log_id_ref['id'] += 1
                    item_dict['audit_logs'] = [{
                        'id': 'AL_{}'.format(audit_log_id_ref['id']),
                        'user_id': oc_user.user_id,
                        'username': oc_user.username,
                        'full_name': oc_user.full_name,
                        'timestamp': form.received_on,
                        'audit_type': 'Item data value updated',
                        'reason': 'initial value',
                        'new_value': answer,
                        'value_type': question,
                    }]
                mu_oid = get_item_measurement_unit(self._domain, item)
                if mu_oid:
                    item_dict['measurement_unit_oid'] = mu_oid

        if study_event.start_datetime is None or form.form['meta']['timeStart'] < study_event.start_datetime:
            study_event.start_datetime = form.form['meta']['timeStart']
        if study_event.end_datetime is None or form.form['meta']['timeEnd'] > study_event.end_datetime:
            study_event.end_datetime = form.form['meta']['timeEnd']

    def add_item_group(self, item, form):
        study_event = self.get_study_event(item, form)
        oc_form = study_event.forms[item.form_oid]
        item_group = ItemGroup(self._domain, item.item_group_oid)
        oc_form[item.item_group_oid].append(item_group)

    def add_data(self, data, form, audit_log_id_ref):
        def get_next_item(question_list):
            for question_ in question_list:
                item_ = get_question_item(self._domain, form.xmlns, question_)
                if item_:
                    return item_
            return None

        # If a CommCare form is an OpenClinica repeating item group, then we would need to add a new item
        # group. This isn't relevant for this project.
        # if form.xmlns in REPEATING_ITEM_GROUP_FORMS:
        #     pass
        for key, value in data.iteritems():
            if key in _reserved_keys:
                continue
            if isinstance(value, list):
                # Repeat group
                # NOTE: We need to assume that repeat groups can't be edited in later form submissions
                item = get_next_item(value)
                if item is None:
                    # None of the questions in this group are OpenClinica items
                    continue
                self.add_item_group(item, form)
                for v in value:
                    # TODO: More testing
                    if not isinstance(v, dict):
                        raise OpenClinicaIntegrationError(
                            'CommCare question value is an unexpected data type. Form XMLNS: "{}"'.format(
                                form.xmlns))
                    self.add_data(v, form, audit_log_id_ref)
            elif isinstance(value, dict):
                # Group
                self.add_data(value, form, audit_log_id_ref)
            else:
                # key is a question and value is its answer
                item = get_question_item(self._domain, form.xmlns, key)
                if item is None:
                    # This is a CommCare-only question or form
                    continue
                self.add_item(item, form, key, oc_format_date(value), audit_log_id_ref)

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
