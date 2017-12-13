from __future__ import absolute_import
from collections import defaultdict
import hashlib
import re
from lxml import etree
from corehq.apps.domain.models import Domain
from corehq.apps.users.models import CouchUser
from corehq.util.quickcache import quickcache
from custom.openclinica.const import (
    AUDIT_LOGS,
    CC_DOB,
    CC_ENROLLMENT_DATE,
    CC_SEX,
    CC_STUDY_SUBJECT_ID,
    CC_SUBJECT_KEY,
)
from custom.openclinica.utils import (
    OpenClinicaIntegrationError,
    get_item_measurement_unit,
    get_question_item,
    get_oc_user,
    get_study_event_name,
    is_study_event_repeating,
    oc_format_date,
    oc_format_time,
    originals_first,
)
from dimagi.ext.couchdbkit import (
    Document,
    DocumentSchema,
    StringProperty,
    SchemaProperty,
    BooleanProperty,
)
from dimagi.utils.couch.cache import cache_core
from suds.client import Client
from suds.plugin import MessagePlugin
from suds.wsse import Security, UsernameToken


_reserved_keys = ('@uiVersion', '@xmlns', '@name', '#type', 'case', 'meta', '@version')


class OpenClinicaAPI(object):
    """
    We use OpenClinica's SOAP API. because their REST API is limited.

    CommCare subject cases are iterated, and data built up from form
    submissions. Subjects and their data are then compared with OpenClinica.
    Missing subjects are created using `StudySubject.create` and missing
    events are scheduled with `Event.schedule`. Data is then ready to import
    using `Data.import`.

    This automates a process that would otherwise need to be done manually.

    One manual aspect still remains. The OpenClinica administrator still needs
    to create users on OpenClinica for all CommCare mobile workers for the
    study, in order for AuditLog data exported from CommCare to match
    OpenClinica users.

    +============+==============================+====================+==========================================+
    | Web        | Method                       | Description        | WSDL Location (Input Value)              |
    | Service    |                              |                    |                                          |
    +============+==============================+====================+==========================================+
    | Create     | StudySubject.create          | Creates a new      | http://${your instance}/OpenClinica-ws/  |
    | Study      |                              | Study Subject      | ws/studySubject/v1/studySubjectWsdl.wsdl |
    | Subject    |                              |                    |                                          |
    +------------+------------------------------+--------------------+------------------------------------------+
    | List all   | StudySubject                 | Lists the Subjects | http://${your instance}/OpenClinica-ws/  |
    | Study      | .listAllByStudy              | in a study         | ws/studySubject/v1/studySubjectWsdl.wsdl |
    | Subjects   |                              |                    |                                          |
    +------------+------------------------------+--------------------+------------------------------------------+
    | Find if    | StudySubject.isStudySubject  | Find if Study      | http://${your instance}/OpenClinica-ws/  |
    | Study      |                              | Subject exists     | ws/studySubject/v1/studySubjectWsdl.wsdl |
    | Subject    |                              |                    |                                          |
    | exists     |                              |                    |                                          |
    +------------+------------------------------+--------------------+------------------------------------------+
    | Schedule   | Event.schedule               | Schedules an       | http://${your instance}/OpenClinica-ws/  |
    | Event      |                              | Event for an       | ws/event/v1/eventWsdl.wsdl               |
    |            |                              | enrolled Study     |                                          |
    |            |                              | Subject            |                                          |
    +------------+------------------------------+--------------------+------------------------------------------+
    | Import     | Data.import                  | Imports Data onto  | http://${your instance}/OpenClinica-ws/  |
    | Data       |                              | an OpenClincia     | ws/data/v1/dataWsdl.wsdl                 |
    |            |                              | CRF for an already |                                          |
    |            |                              | scheduled study    |                                          |
    |            |                              | event              |                                          |
    +------------+------------------------------+--------------------+------------------------------------------+
    | Get Study  | Study.getMetadata            | Returns study      | http://${your instance}/OpenClinica-ws/  |
    | Metadata   |                              | definition         | ws/study/v1/studyWsdl.wsdl               |
    |            |                              | metadata in        |                                          |
    |            |                              | CDISC ODM XML      |                                          |
    |            |                              | format (with       |                                          |
    |            |                              | OpenClinica        |                                          |
    |            |                              | extensions)        |                                          |
    +------------+------------------------------+--------------------+------------------------------------------+
    | List Study | Study.listAll                | Returns a lists of | http://${your instance}/OpenClinica-ws/  |
    |            |                              | studies and sites  | ws/study/v1/studyWsdl.wsdl               |
    +------------+------------------------------+--------------------+------------------------------------------+
    | Study      | StudyEventDefinition.listAll | Lists study event  | http://${your instance}/OpenClinica-ws/  |
    | Event      |                              | definitions in     | ws/studyEventDefinition/v1/              |
    | Definition |                              | study              | studyEventDefinitionWsdl.wsdl            |
    +------------+------------------------------+--------------------+------------------------------------------+

    """

    def __init__(self, base_url, username, password, study_id, prefetch=False):
        """
        Initialise OpenClinicaAPI

        :param base_url: Protocol, address (and port) of the server, e.g. "https://openclinica.example.com:8080/"
        :param username: Username enabled for API authentication
        :param password: Password
        :param study_id: Study identifier
        :param prefetch: Fetch WSDLs on init?
        """
        self._base_url = base_url if base_url[-1] == '/' else base_url + '/'
        self._username = username
        self._password = password
        self._study_id = study_id
        self._clients = {
            'data': None,
            'event': None,
            'study': None,
            'studyEventDefinition': None,
            'studySubject': None
        }
        if prefetch:
            for endpoint in self._clients:
                self.get_client(endpoint)

    def get_client(self, endpoint):

        class FixMimeMultipart(MessagePlugin):
            """
            StudySubject.listAllByStudy replies with what looks like part of a multipart MIME message(!?) Fix this.
            """
            def received(self, context):
                reply = context.reply
                if reply.startswith('------='):
                    matches = re.search(r'(<SOAP-ENV:Envelope.*</SOAP-ENV:Envelope>)', reply)
                    context.reply = matches.group(1)

        if endpoint not in self._clients:
            raise ValueError('Unknown OpenClinica API endpoint')
        if self._clients[endpoint] is None:
            client = Client(
                '{url}OpenClinica-ws/ws/{endpoint}/v1/{endpoint}Wsdl.wsdl'.format(
                    url=self._base_url,
                    endpoint=endpoint
                ),
                plugins=[FixMimeMultipart()]
            )
            security = Security()
            password = hashlib.sha1(self._password).hexdigest()  # SHA1, not AES as documentation says
            token = UsernameToken(self._username, password)
            security.tokens.append(token)
            client.set_options(wsse=security)
            self._clients[endpoint] = client
        return self._clients[endpoint]

    def get_study_metadata_string(self):
        """
        Returns study metadata as an XML string
        """
        study_client = self.get_client('study')
        study_client.set_options(retxml=True)  # Don't parse the study metadata; just give us the raw XML
        resp = study_client.service.getMetadata({'identifier': self._study_id})
        soap_env = etree.fromstring(resp)
        nsmap = {
            'SOAP-ENV': "http://schemas.xmlsoap.org/soap/envelope/",
            'OC': "http://openclinica.org/ws/study/v1"
        }
        odm = soap_env.xpath('./SOAP-ENV:Body/OC:createResponse/OC:odm', namespaces=nsmap)[0]
        return odm.text

    def get_subject_keys(self):
        subject_client = self.get_client('studySubject')
        resp = subject_client.service.listAllByStudy({'identifier': self._study_id})
        return [s.subject.uniqueIdentifier for s in resp.studySubjects.studySubject] if resp.studySubjects else []

    def create_subject(self, subject):
        subject_client = self.get_client('studySubject')
        subject_data = {
            'label': subject['study_subject_id'],
            'enrollmentDate': str(subject['enrollment_date']),
            'subject': {
                'uniqueIdentifier': subject['subject_key'][3:],  # Drop the initial 'SS_'
                'gender': {'1': 'm', '2': 'f'}[subject['sex']],
                'dateOfBirth': str(subject['dob']),
            },
            'studyRef': {
                'identifier': self._study_id,
            },
        }
        resp = subject_client.service.create(subject_data)
        if resp.result != 'Success':
            raise OpenClinicaIntegrationError(
                'Unable to register subject "{}" via OpenClinica webservice'.format(subject['subject_key'])
            )

    def schedule_event(self, subject, event):
        event_client = self.get_client('event')
        event_data = {
            'studySubjectRef': {
                'label': subject['study_subject_id'],
            },
            'studyRef': {
                'identifier': self._study_id,
            },
            'eventDefinitionOID': event['study_event_oid'],
            'startDate': event['start_long'].split()[0],  # e.g. 1999-12-31
            'startTime': event['start_short'].split()[1],  # e.g. 23:59
            'endDate': event['end_long'].split()[0],
            'endTime': event['end_short'].split()[1],
        }
        resp = event_client.service.schedule(event_data)
        if resp.result != 'Success':
            raise OpenClinicaIntegrationError(
                'Unable to schedule event "{}"  via OpenClinica webservice'.format(event['study_event_oid'])
            )


class StudySettings(DocumentSchema):
    is_ws_enabled = BooleanProperty()
    url = StringProperty()
    username = StringProperty()
    password = StringProperty()
    protocol_id = StringProperty()
    metadata = StringProperty()  # Required when web service is not enabled


class OpenClinicaSettings(Document):
    domain = StringProperty()
    study = SchemaProperty(StudySettings)  # One study per domain prevents cases from getting mixed up

    @classmethod
    def for_domain(cls, domain):
        res = cache_core.cached_view(
            cls.get_db(),
            "by_domain_doc_type_date/view",
            key=[domain, 'OpenClinicaSettings', None],
            reduce=False,
            include_docs=True,
            wrapper=cls.wrap)
        return res[0] if len(res) > 0 else None


class ItemGroup(object):
    """
    Corresponds to a question group in CommCare.

    ItemGroups can repeat. To reproduce this behaviour in CommCare we use
    repeat groups.
    """

    def __init__(self, domain, oid):
        self.oid = oid
        self.completed_cc_forms = set([])
        self.items = defaultdict(dict)


class StudyEvent(object):
    """
    Like item groups, study events can also be repeating.
    """
    def __init__(self, domain, oid, case_id):
        self.oid = oid
        self.case_id = case_id
        self.is_repeating = is_study_event_repeating(domain, oid)
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
        self._domain = Domain.get_by_name(domain)
        self._domain_name = domain

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

    def get_study_event(self, item, form, case_id):
        """
        Return the current study event. Opens a new study event if necessary.
        """
        if len(self.data[item.study_event_oid]):
            study_event = self.data[item.study_event_oid][-1]
            if study_event.is_repeating and study_event.case_id != case_id:
                study_event = StudyEvent(self._domain_name, item.study_event_oid, case_id)
                self.data[item.study_event_oid].append(study_event)
        else:
            study_event = StudyEvent(self._domain_name, item.study_event_oid, case_id)
            self.data[item.study_event_oid].append(study_event)
        return study_event

    def get_item_group(self, item, form, case_id):
        """
        Return the current item group and study event. Opens a new item group if necessary.

        Item groups are analogous to CommCare question groups. Like question groups, they can repeat.
        """
        study_event = self.get_study_event(item, form, case_id)
        oc_form = study_event.forms[item.form_oid]
        if not oc_form[item.item_group_oid]:
            oc_form[item.item_group_oid].append(ItemGroup(self._domain_name, item.item_group_oid))
        item_group = oc_form[item.item_group_oid][-1]
        return item_group, study_event

    def get_item_dict(self, item, form, case_id, question):
        """
        Return a dict for storing item data, and current study event.

        Return both because both the item dict and study event may be updated by a form or question.
        """
        item_group, study_event = self.get_item_group(item, form, case_id)
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
            cc_user = self._get_cc_user(self._domain_name, user_id)
            oc_user = get_oc_user(self._domain_name, cc_user)
            if oc_user is None:
                raise OpenClinicaIntegrationError(
                    'OpenClinica user not found for CommCare user "{}"'.format(cc_user.username))
            self.mobile_workers[user_id] = oc_user
        return self.mobile_workers[user_id]

    def add_item(self, item, form, case_id, question, answer, audit_log_id_ref):
        answer = oc_format_date(answer)
        answer = oc_format_time(answer, self._domain.get_default_timezone())
        oc_user = self._get_oc_user(form.auth_context['user_id'])
        if getattr(form, 'deprecated_form_id', None) and question in self.question_items[form.deprecated_form_id]:
            # This form has been edited on HQ. Fetch original item
            item_dict, study_event = self.question_items[form.deprecated_form_id][question]
            if item_dict['value'] != answer:
                self.edit_item(item_dict, form, question, answer, audit_log_id_ref, oc_user)
        else:
            item_dict, study_event = self.get_item_dict(item, form, case_id, question)
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
                mu_oid = get_item_measurement_unit(self._domain_name, item)
                if mu_oid:
                    item_dict['measurement_unit_oid'] = mu_oid

        if study_event.start_datetime is None or form.form['meta']['timeStart'] < study_event.start_datetime:
            study_event.start_datetime = form.form['meta']['timeStart']
        if study_event.end_datetime is None or form.form['meta']['timeEnd'] > study_event.end_datetime:
            study_event.end_datetime = form.form['meta']['timeEnd']

    def add_item_group(self, item, form):
        study_event = self.get_study_event(item, form)
        oc_form = study_event.forms[item.form_oid]
        item_group = ItemGroup(self._domain_name, item.item_group_oid)
        oc_form[item.item_group_oid].append(item_group)

    def add_data(self, data, form, event_case, audit_log_id_ref):
        def get_next_item(event_id, question_list):
            for question_ in question_list:
                item_ = get_question_item(self._domain_name, event_id, question_)
                if item_:
                    return item_
            return None

        event_id = getattr(event_case, 'event_type')
        # If a CommCare form is an OpenClinica repeating item group, then we would need to add a new item
        # group.
        for key, value in data.iteritems():
            if key in _reserved_keys:
                continue
            if isinstance(value, list):
                # Repeat group
                # NOTE: We need to assume that repeat groups can't be edited in later form submissions
                item = get_next_item(event_id, value)
                if item is None:
                    # None of the questions in this group are OpenClinica items
                    continue
                self.add_item_group(item, form)
                for v in value:
                    if not isinstance(v, dict):
                        raise OpenClinicaIntegrationError(
                            'CommCare question value is an unexpected data type. Form XMLNS: "{}"'.format(
                                form.xmlns))
                    self.add_data(v, form, event_case, audit_log_id_ref)
            elif isinstance(value, dict):
                # Group
                self.add_data(value, form, event_case, audit_log_id_ref)
            else:
                # key is a question and value is its answer
                item = get_question_item(self._domain_name, event_id, key)
                if item is None:
                    # This is a CommCare-only question or form
                    continue
                case_id = event_case.get_id
                self.add_item(item, form, case_id, key, value, audit_log_id_ref)

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
                        'start_short': study_event.start_short,
                        'start_long': study_event.start_long,
                        'end_short': study_event.end_short,
                        'end_long': study_event.end_long,
                        'forms': mkformslist(study_event.forms)
                    })
            return eventslist

        return mkeventslist(self.data)

    @classmethod
    def wrap(cls, case, audit_log_id_ref):
        subject = cls(getattr(case, CC_SUBJECT_KEY), getattr(case, CC_STUDY_SUBJECT_ID), case.domain)
        subject.enrollment_date = getattr(case, CC_ENROLLMENT_DATE, None)
        subject.sex = getattr(case, CC_SEX, None)
        subject.dob = getattr(case, CC_DOB, None)
        for event in case.get_subcases():
            for form in originals_first(event.get_forms()):
                # Pass audit log ID by reference to increment it for each audit log
                subject.add_data(form.form, form, event, audit_log_id_ref)
        return subject
