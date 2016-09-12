import urllib
from urllib2 import HTTPError, URLError
import logging
from datetime import datetime
from copy import copy
import settings
import os

from org.javarosa.core.services.storage import IStorageUtilityIndexed
from org.javarosa.core.services.storage import IStorageIterator
from org.commcare.cases.instance import CaseInstanceTreeElement
from org.commcare.cases.ledger.instance import LedgerInstanceTreeElement
from org.commcare.core.process import CommCareInstanceInitializer
from org.commcare.cases.model import Case
from org.commcare.cases.ledger import Ledger
from org.commcare.session import CommCareSession, SessionInstanceBuilder
from org.javarosa.xml import TreeElementParser
from org.javarosa.xpath.expr import XPathFuncExpr
from org.javarosa.xpath import XPathParseTool, XPathException
from org.javarosa.xpath.parser import XPathSyntaxException
from org.javarosa.core.model.condition import EvaluationContext
from org.javarosa.core.model.instance import ExternalDataInstance
from org.commcare.api.persistence import SqlSandboxUtils
from org.commcare.core.sandbox import SandboxUtils
from org.commcare.modern.process import FormRecordProcessorHelper as FormRecordProcessor
from org.commcare.modern.parse import ParseUtilsHelper as ParseUtils
from org.kxml2.io import KXmlParser
import persistence
from java.io import File
from util import to_vect, to_jdate, to_hashtable, to_input_stream, query_factory
from xcp import TouchFormsUnauthorized, TouchcareInvalidXPath, TouchFormsNotFound, CaseNotFound

logger = logging.getLogger('formplayer.touchcare')


def get_restore_url(criteria=None):
    query_url = '%s?%s' % (settings.RESTORE_URL, urllib.urlencode(criteria))
    return query_url


def force_ota_restore(username, domain, auth):
    CCInstances({"username": username, "domain": domain, "host": settings.URL_HOST},
                auth, force_sync=True, uses_sqlite=True)
    result = {'status': 'OK'}
    return result


class CCInstances(CommCareInstanceInitializer):
    def __init__(self, sessionvars, auth, restore_xml=None,
                 force_sync=False, form_context=None, uses_sqlite=False):
        self.vars = sessionvars
        self.auth = auth
        self.uses_sqlite = uses_sqlite
        if self.uses_sqlite:
            username = sessionvars['username']
            self.username = username + '@' + sessionvars['domain'] if '@' not in username else username
            self.sandbox = SqlSandboxUtils.getStaticStorage(self.username, settings.SQLITE_DBS_DIRECTORY)
            self.host = settings.URL_HOST
            self.domain = sessionvars['domain']
            self.query_func = query_factory(self.host, self.domain, self.auth, 'raw')
            self.query_url = get_restore_url({'as': self.username, 'version': '2.0'})
            CommCareInstanceInitializer.__init__(self, self.sandbox)

            if force_sync or self.needs_sync():
                self.perform_ota_restore(restore_xml)
        else:
            self.fixtures = {}
            self.form_context = form_context or {}

    def clear_tables(self):
        db_name = self.username + ".db"
        full_path = os.path.join(settings.SQLITE_DBS_DIRECTORY, db_name)
        if os.path.isfile(full_path):
            os.remove(full_path)
        self.sandbox = SqlSandboxUtils.getStaticStorage(self.username, settings.SQLITE_DBS_DIRECTORY)
        persistence.postgres_drop_sqlite(self.username)

    def perform_ota_restore(self, restore=None):
        self.clear_tables()
        if not restore:
            restore_xml = self.get_restore_xml()
            ParseUtils.parseXMLIntoSandbox(restore_xml, self.sandbox)
        else:
            restore_file = restore
            ParseUtils.parseFileIntoSandbox(File(restore_file), self.sandbox)
        persistence.postgres_set_sqlite(self.username, 1)

    def get_restore_xml(self):
        payload = self.query_func(self.query_url)
        return payload

    def needs_sync(self):
        try:
            self.last_sync = persistence.postgres_lookup_sqlite_last_modified(self.username)
        except:
            logger.exception("Unable to get last sync for usertime for user %s " % self.username)
            return True

        current_time = datetime.utcnow()
        elapsed = current_time - self.last_sync
        minutes_elapsed = divmod(elapsed.days * 86400 + elapsed.seconds, 60)[0]
        return minutes_elapsed > settings.SQLITE_STALENESS_WINDOW

    def generateRoot(self, instance):

        ref = instance.getReference()

        def from_bundle(inst):
            root = inst.getRoot()
            root.setParent(instance.getBase())
            return root

        if 'casedb' in ref:
            if self.uses_sqlite:
                case_storage = self.sandbox.getCaseStorage()
            else:
                case_storage = CaseDatabase(
                    self.vars.get('host'),
                    self.vars['domain'],
                    self.auth,
                    self.vars.get("additional_filters", {}),
                    self.vars.get("preload_cases", False),
                    self.form_context,
                )
            return CaseInstanceTreeElement(
                instance.getBase(),
                case_storage,
                False
            )
        elif 'fixture' in ref:
            fixture_id = ref.split('/')[-1]
            user_id = self.vars['user_id']
            if self.uses_sqlite:
                fixture = SandboxUtils.loadFixture(self.sandbox, fixture_id, user_id)
                root = fixture.getRoot()
            else:
                root = self._get_fixture(user_id, fixture_id)
            root.setParent(instance.getBase())
            return root
        elif 'ledgerdb' in ref:
            if self.uses_sqlite:
                ledger_storage = self.sandbox.getLedgerStorage()
            else:
                ledger_storage = LedgerDatabase(
                    self.vars.get('host'), self.vars['domain'],
                    self.auth, self.vars.get("additional_filters", {}),
                    self.vars.get("preload_cases", False),
                )
            return LedgerInstanceTreeElement(
                instance.getBase(),
                ledger_storage
            )
        elif 'session' in ref:
            meta_keys = ['device_id', 'app_version', 'username', 'user_id']
            exclude_keys = ['additional_filters', 'user_data']
            sess = CommCareSession()  # will not passing a CCPlatform cause problems later?
            for k, v in self.vars.iteritems():
                if k not in meta_keys \
                        and k not in exclude_keys:
                    # com.xhaus.jyson.JysonCodec returns data as byte strings
                    # in unknown encoding (possibly ISO-8859-1)
                    sess.setDatum(k, unicode(v, errors='replace'))

            clean_user_data = {}
            for k, v in self.vars.get('user_data', {}).iteritems():
                clean_user_data[k] = unicode(v if v is not None else '', errors='replace')

            form_instance = SessionInstanceBuilder.getSessionInstance(sess.getFrame(), *([self.vars.get(k, '') for k in meta_keys] +
                                                     [to_hashtable(clean_user_data)]))
            return from_bundle(form_instance)

    def _get_fixture(self, user_id, fixture_id):
        query_url = '%(base)s/%(user)s/%(fixture)s' % {"base": settings.FIXTURE_API_URL,
                                                       "user": user_id,
                                                       "fixture": fixture_id}
        q = query_factory(self.vars.get('host'), self.vars['domain'], self.auth, format="raw")
        try:
            results = q(query_url)
        except (HTTPError, URLError), e:
            fixture_name = query_url[query_url.rfind('/') + 1:]
            if "user-group" in fixture_name:
                raise TouchFormsNotFound('This form requires that the user be in a case sharing group '
                                         'but one could not be found.')
            elif "commtrack:locations" in fixture_name:
                raise TouchFormsNotFound('This form requires that the user be assigned to a location '
                                         'but one could not be found.')
            elif "item-list" in fixture_name:
                raise TouchFormsNotFound('Unable to fetch lookup table %s. '
                                         'Ensure the logged in user has access '
                                         'to this lookup table.' % fixture_name)
            elif "commtrack:products" in fixture_name:
                raise TouchFormsNotFound('Unable to retrieve the product list for this user. Ensure '
                                         'the logged in user is assigned a product list.')
            else:
                raise TouchFormsNotFound('Unable to fetch fixture %s. Ensure the logged in user has access '
                                         'to this fixture.' % fixture_name)
        parser = KXmlParser()
        parser.setInput(to_input_stream(results), "UTF-8")
        parser.setFeature(KXmlParser.FEATURE_PROCESS_NAMESPACES, True)
        parser.next()
        return TreeElementParser(parser, 0, fixture_id).parse()


def process_form_file(auth, submission_file, session_data=None):
    """
    process_form_file and process_form_xml both perform submissions of the completed form form_data
    against the sandbox of the current user.

    """
    ccInstances = CCInstances(session_data, auth, uses_sqlite=True)
    sandbox = ccInstances.sandbox
    FormRecordProcessor.processFile(sandbox, File(submission_file))


def process_form_xml(auth, submission_xml, session_data=None):
    ccInstances = CCInstances(session_data, auth, uses_sqlite=True)
    sandbox = ccInstances.sandbox
    FormRecordProcessor.processXML(sandbox, submission_xml)


def perform_restore(auth, session_data=None, restore_xml=None):
    CCInstances(session_data, auth, restore_xml, True, uses_sqlite=True)


def filter_cases(filter_expr, api_auth, session_data=None, form_context=None,
                 restore_xml=None, force_sync=False, uses_sqlite=False):
    session_data = session_data or {}
    form_context = form_context or {}

    modified_xpath = "join(',', instance('casedb')/casedb/case%(filters)s[@status= 'open']/@case_id)" % \
                     {"filters": filter_expr}
    # whenever we do a filter case operation we need to load all
    # the cases, so force this unless manually specified
    if 'preload_cases' not in session_data:
        session_data['preload_cases'] = True

    ccInstances = CCInstances(session_data, api_auth, form_context=form_context,
                              restore_xml=restore_xml, force_sync=force_sync, uses_sqlite=uses_sqlite)
    caseInstance = ExternalDataInstance("jr://instance/casedb", "casedb")

    try:
        caseInstance.initialize(ccInstances, "casedb")
    except (HTTPError, URLError), e:
        raise TouchFormsUnauthorized('Unable to connect to HQ: %s' % str(e))

    instances = to_hashtable({"casedb": caseInstance})

    # load any additional instances needed
    for extra_instance_config in session_data.get('extra_instances', []):
        data_instance = ExternalDataInstance(extra_instance_config['src'], extra_instance_config['id'])
        data_instance.initialize(ccInstances, extra_instance_config['id'])
        instances[extra_instance_config['id']] = data_instance

    try:
        case_list = XPathFuncExpr.toString(
            XPathParseTool.parseXPath(modified_xpath).eval(
                EvaluationContext(None, instances)))
        return {'cases': filter(lambda x: x, case_list.split(","))}
    except (XPathException, XPathSyntaxException), e:
        raise TouchcareInvalidXPath('Error querying cases with xpath %s: %s' % (filter_expr, str(e)))


def query_case_ids(q, criteria=None):
    criteria = copy(criteria) or {}  # don't modify the passed in dict
    criteria["ids_only"] = 'true'
    query_url = '%s?%s' % (settings.CASE_API_URL, urllib.urlencode(criteria))
    return [id for id in q(query_url)]


def query_cases(q, criteria=None):
    query_url = '%s?%s' % (settings.CASE_API_URL, urllib.urlencode(criteria)) \
        if criteria else settings.CASE_API_URL
    return [case_from_json(cj) for cj in q(query_url)]


def query_case(q, case_id):
    cases = query_cases(q, {'case_id': case_id})
    try:
        return cases[0]
    except IndexError:
        return None


def case_from_json(data):
    c = Case()
    c.setCaseId(data['case_id'])
    c.setTypeId(data['properties']['case_type'])
    c.setName(data['properties']['case_name'])
    c.setClosed(data['closed'])
    if data['properties']['date_opened']:
        c.setDateOpened(to_jdate(
            datetime.strptime(
                data['properties']['date_opened'],
                '%Y-%m-%dT%H:%M:%S')))  # 'Z' in fmt string omitted due to jython bug
    owner_id = data['properties']['owner_id'] or data['user_id'] or ""
    c.setUserId(owner_id)  # according to clayton "there is no user_id, only owner_id"

    for k, v in data['properties'].iteritems():
        if v is not None and k not in ['case_name', 'case_type', 'date_opened']:
            c.setProperty(k, v)

    for k, v in data['indices'].iteritems():
        c.setIndex(k, v['case_type'], v['case_id'])

    for k, v in data['attachments'].iteritems():
        c.updateAttachment(k, v['url'])

    return c


def query_ledger_for_case(q, case_id):
    query_string = urllib.urlencode({'case_id': case_id})
    query_url = '%s?%s' % (settings.LEDGER_API_URL, query_string)
    return ledger_from_json(q(query_url))


def ledger_from_json(data):
    ledger = Ledger(data['entity_id'])
    for section_id, section in data['ledger'].items():
        for product_id, amount in section.items():
            ledger.setEntry(section_id, product_id, int(amount))
    return ledger


class StaticIterator(IStorageIterator):
    def __init__(self, ids):
        self.ids = ids
        self.i = 0

    def hasMore(self):
        return self.i < len(self.ids)

    def nextID(self):
        id = self.ids[self.i]
        self.i += 1
        return id


class TouchformsStorageUtility(IStorageUtilityIndexed):
    """
    The TouchformsStorageUtility provides an interface for working with the case database. The mobile phone
    uses this to populate and reference cases in the SQLite database on the Android phone. Touchforms uses HQ
    as its "mobile database" so when populating the case universe, it calls HQ to get the case universe for
    that particular user.
    See:
    https://github.com/dimagi/javarosa/blob/master/core/src/org/javarosa/core/services/storage/IStorageUtilityIndexed.java
    for more information on the interface.
    """

    def __init__(self, host, domain, auth, additional_filters=None, preload=False, form_context=None):

        self.cached_lookups = {}
        self.form_context = form_context or {}

        if self.form_context.get('case_model', None):
            case_model = self.form_context['case_model']
            self.cached_lookups[('case-id', case_model['case_id'])] = [case_from_json(case_model)]

        self._objects = {}
        self.ids = {}
        self.fully_loaded = False  # when we've loaded every possible object
        self.query_func = query_factory(host, domain, auth)
        self.additional_filters = additional_filters or {}
        if preload:
            self.load_all_objects()
        else:
            self.load_object_ids()

    def get_object_id(self, object):
        raise NotImplementedError("subclasses must handle this")

    def fetch_object(self, object_id):
        raise NotImplementedError("subclasses must handle this")

    def load_all_objects(self):
        raise NotImplementedError("subclasses must handle this")

    def load_object_ids(self):
        raise NotImplementedError("subclasses must handle this")

    @property
    def objects(self):
        if self.fully_loaded:
            return self._objects
        else:
            self.load_all_objects()
        return self._objects

    def put_object(self, object):
        object_id = self.get_object_id(object)
        self._objects[object_id] = object

    def read(self, record_id):
        logger.debug('read record %s' % record_id)
        try:
            # record_id is an int, object_id is a guid
            object_id = self.ids[record_id]
        except KeyError:
            return None
        return self.read_object(object_id)

    def read_object(self, object_id):
        logger.debug('read object %s' % object_id)
        if object_id not in self._objects:
            self.put_object(self.fetch_object(object_id))
        try:
            return self._objects[object_id]
        except KeyError:
            raise Exception('could not find an object for id [%s]' % object_id)

    def setReadOnly(self):
        # todo: not sure why this exists. is it part of the public javarosa API?
        pass

    def getNumRecords(self):
        return len(self.ids)

    def iterate(self):
        return StaticIterator(self.ids.keys())


class CaseDatabase(TouchformsStorageUtility):
    def get_object_id(self, case):
        return case.getCaseId()

    def fetch_object(self, case_id):
        if ('case-id', case_id) in self.cached_lookups:
            return self.cached_lookups[('case-id', case_id)][0]
        return query_case(self.query_func, case_id)

    def load_all_objects(self):
        if self.form_context.get('cases', None):
            cases = map(lambda c: case_from_json(c), self.form_context.get('cases'))
        else:
            cases = query_cases(self.query_func,
                                criteria=self.additional_filters)
        for c in cases:
            self.put_object(c)
        # todo: the sorted() call is a hack to try and preserve order between bootstrapping
        # this with IDs versus full values. Really we should store a _next_id integer and then
        # update things as they go into self._objects inside the put_object() function.
        # http://manage.dimagi.com/default.asp?169413
        self.ids = dict(enumerate(sorted(self._objects.keys())))
        self.fully_loaded = True

    def load_object_ids(self):
        if self.form_context.get('all_case_ids', None):
            case_ids = self.form_context.get('all_case_ids')
        else:
            case_ids = query_case_ids(self.query_func, criteria=self.additional_filters)
        # todo: see note above about why sorting is necessary
        self.ids = dict(enumerate(sorted(case_ids)))

    def getIDsForValue(self, field_name, value):
        logger.debug('case index lookup %s %s' % (field_name, value))

        if (field_name, value) not in self.cached_lookups:
            if field_name == 'case-id':
                cases = [self.read_object(value)]
            else:
                try:
                    get_val = {
                        'case-type': lambda c: c.getTypeId(),
                        'case-status': lambda c: 'closed' if c.isClosed() else 'open',
                    }[field_name]
                except KeyError:
                    # Try any unrecognized field name as a case id field.
                    # Needed for 'case-in-goal' lookup in PACT Care Plan app.
                    cases = [self.read_object(value)]
                else:
                    cases = [c for c in self.objects.values() if get_val(c) == value]

            self.cached_lookups[(field_name, value)] = cases

        cases = self.cached_lookups[(field_name, value)]
        id_map = dict((v, k) for k, v in self.ids.iteritems())
        try:
            return to_vect(id_map[c.getCaseId()] for c in cases)
        except KeyError:
            # Case was not found in id_map
            raise CaseNotFound


class LedgerDatabase(TouchformsStorageUtility):
    def __init__(self, host, domain, auth, additional_filters, preload):
        super(LedgerDatabase, self).__init__(host, domain, auth, additional_filters, preload)

    def get_object_id(self, ledger):
        return ledger.getEntiyId()

    def fetch_object(self, entity_id):
        return query_ledger_for_case(self.query_func, entity_id)

    def load_object_ids(self):
        case_ids = query_case_ids(self.query_func, criteria=self.additional_filters)
        self.ids = dict(enumerate(case_ids))

    def getIDsForValue(self, field_name, value):
        logger.debug('ledger lookup %s %s' % (field_name, value))
        if (field_name, value) not in self.cached_lookups:
            if field_name == 'entity-id':
                ledgers = [self.read_object(value)]
            else:
                raise NotImplementedError("Only entity-id lookup is currently supported!")

            self.cached_lookups[(field_name, value)] = ledgers

        else:
            ledgers = self.cached_lookups[(field_name, value)]

        id_map = dict((v, k) for k, v in self.ids.iteritems())
        return to_vect(id_map[l.getEntiyId()] for l in ledgers)


class Actions:
    FILTER_CASES = 'touchcare-filter-cases'
