from __future__ import with_statement
import sys
import os
from datetime import datetime
import threading
import codecs
import time
import uuid
import hashlib

from java.util import Date
from java.util import Vector
from java.io import StringReader

import customhandlers
from util import to_jdate, to_pdate, to_jtime, to_ptime, to_vect, to_arr, index_from_str

from setup import init_classpath, init_jr_engine
import logging
init_classpath()
init_jr_engine()

import com.xhaus.jyson.JysonCodec as json
from org.javarosa.xform.parse import XFormParser
from org.javarosa.form.api import FormEntryModel, FormEntryController, FormEntryPrompt
from org.javarosa.core.model import Constants, FormIndex
from org.javarosa.core.model.data import IntegerData, LongData, DecimalData, StringData, DateData, TimeData, SelectOneData, SelectMultiData, GeoPointData
from org.javarosa.core.model.data.helper import Selection
from org.javarosa.core.util import UnregisteredLocaleException
from org.javarosa.model.xform import XFormSerializingVisitor as FormSerializer
from org.commcare.suite.model import Text as JRText
from java.util import Hashtable as JHashtable
from org.javarosa.xpath import XPathException

from touchcare import CCInstances, process_form_xml
from util import query_factory
from decorators import require_xform_session
from xcp import CaseNotFound
import persistence
import settings

logger = logging.getLogger('formplayer.xformplayer')


class NoSuchSession(Exception):
    pass


class GlobalStateManager(object):
    session_cache = {}
    session_locks = {}

    def __init__(self):
        self.global_lock = threading.Lock()

    def get_lock(self, session_id):
        if session_id not in self.session_locks:
            self.session_locks[session_id] = threading.Lock()

        logger.info('[locking] requested lock for session %s' % session_id)
        return self.session_locks[session_id]

    def cache_session(self, xfsess):
        with self.get_lock(xfsess.uuid):
            logger.info('[locking] cache_session got lock for session %s' % xfsess.uuid)
            self.session_cache[xfsess.uuid] = xfsess
        logger.info('[locking] cache_session released lock for session %s' % xfsess.uuid)

    def get_session(self, session_id, override_state=None):
        logging.debug("Getting session id: " + str(session_id))
        with self.get_lock(session_id):
            logger.info('[locking] get_session got lock for session %s' % session_id)
            try:
                logging.debug("Getting session_cache " + str(self.session_cache[session_id]))
                logging.debug("Getting session_cache state: " + str(self.session_cache[session_id].session_state()))
                return self.session_cache[session_id]
            except KeyError:
                # see if session has been persisted
                logging.debug("Except key error id: " + str(session_id))
                sess = persistence.restore(session_id, XFormSession, override_state)
                logging.debug("Restored session with id: " + str(session_id))
                if sess:
                    logging.debug("Returning new session")
                    self.cache_session(sess)  # repopulate in-memory cache
                    return sess
                else:
                    logging.debug("No such session")
                    raise NoSuchSession()

        logger.info('[locking] get_session released lock for session %s' % session_id)

    def purge(self):
        num_sess_purged = 0
        num_sess_active = 0

        with self.global_lock:
            logger.info('[locking] purging got global lock')

            now = time.time()
            for sess_id, sess in self.session_cache.items():
                if now - sess.last_activity > sess.staleness_window:
                    with self.get_lock(sess_id):
                        logger.info('[locking] purging got lock for session %s' % sess_id)
                        del self.session_cache[sess_id]
                        num_sess_purged += 1
                        # also purge the session lock
                        del self.session_locks[sess_id]
                    logger.info('[locking] purging released lock for session %s' % sess_id)
                else:
                    num_sess_active += 1

        logger.info('[locking] purging released global lock')
        # note that persisted entries use the timeout functionality provided by the caching framework
        return {'purged': num_sess_purged, 'active': num_sess_active}

    @classmethod
    def get_globalstate(cls):
        return global_state

global_state = None


def _init():
    global global_state
    global_state = GlobalStateManager()


def load_form(xform, instance=None, extensions=None, session_data=None,
              api_auth=None, form_context=None, uses_sql_backend=False):
    """Returns an org.javarosa.core.model.FormDef

    Parameters
    ----------
    xform : string
        String representation of an xform
    form_context : dictionary
        A hash that contains optional context for the form. Supported parameters are: 'all_case_ids' and
        'case_model'. The XFormPlayer uses the context to avoid making redundant calls to CommcareHQ.
    """
    extensions = extensions or []
    session_data = session_data or {}
    is_editing = session_data.get("is_editing", False)

    form = XFormParser(StringReader(xform)).parse()
    if instance is not None:
        XFormParser(None).loadXmlInstance(form, StringReader(instance))

    # retrieve preloaders out of session_data (for backwards compatibility)
    customhandlers.attach_handlers(
        form,
        extensions,
        context=session_data.get('function_context', {}),
        preload_data=session_data.get('preloaders', {})
    )

    try:
        session_data.get('additional_filters', {}).update({
            'use_cache': 'true',
            'hsph_hack': session_data.get('case_id', None)
        })
        form.initialize(instance is None, is_editing, CCInstances(session_data,
                                                      api_auth,
                                                      form_context=form_context,
                                                      uses_sqlite=uses_sql_backend))
    except CaseNotFound:
        # Touchforms repeatedly makes a call to HQ to get all the case ids in its universe. We can optimize
        # this by caching that call to HQ. However, when someone adds a case to that case list, we want to ensure
        # that that case appears in the universe of cases. Therefore we first attempt to use the cached version
        # of the case id list, and in the event that we cannot find a case, we try again, but do not use the cache.
        session_data.get('additional_filters', {}).update({'use_cache': 'false'})
        form.initialize(instance is None, is_editing, CCInstances(session_data,
                                                      api_auth,
                                                      form_context=form_context,
                                                      uses_sqlite=uses_sql_backend))

    return form


class SequencingException(Exception):
    pass


class XFormSession(object):
    def __init__(self, xform, instance=None, **params):
        self.uuid = params.get('uuid', uuid.uuid4().hex)
        self.nav_mode = params.get('nav_mode', 'prompt')
        self.seq_id = params.get('seq_id', 0)
        self.uses_sql_backend = params.get('uses_sql_backend')

        self.form = load_form(
            xform,
            instance,
            params.get('extensions', []),
            params.get('session_data', {}),
            params.get('api_auth'),
            params.get('form_context', None),
            self.uses_sql_backend,
        )
        self.fem = FormEntryModel(self.form, FormEntryModel.REPEAT_STRUCTURE_NON_LINEAR)
        self.fec = FormEntryController(self.fem)

        if params.get('init_lang'):
            try:
                self.fec.setLanguage(params.get('init_lang'))
            except UnregisteredLocaleException:
                pass # just use default language

        if params.get('cur_index'):
            self.fec.jumpToIndex(self.parse_ix(params.get('cur_index')))

        self._parse_current_event()

        self.staleness_window = 3600. * params['staleness_window']
        self.persist = params.get('persist', settings.PERSIST_SESSIONS)
        self.orig_params = {
            'xform': xform,
            'nav_mode': params.get('nav_mode'),
            'session_data': params.get('session_data'),
            'api_auth': params.get('api_auth'),
            'staleness_window': params['staleness_window'],
        }
        self.update_last_activity()

    def _assert_locked(self):
        if not global_state.get_lock(self.uuid).locked():
            # note that this isn't a perfect check that we have the lock
            # but is hopefully a good enough proxy. this is basically an
            # assertion.
            raise Exception('Tried to update XFormSession without the lock!')

    def __enter__(self):
        self._assert_locked()
        self.seq_id += 1
        self.update_last_activity()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._assert_locked()
        if self.persist:
            # TODO should this be done async? we must dump state before releasing the lock, however
            persistence.persist(self)


    def update_last_activity(self):
        self.last_activity = time.time()

    def session_state(self):
        state = dict(self.orig_params)
        state.update({
            'instance': self.output(),
            'init_lang': self.get_lang(),
            'cur_index': str(self.fem.getFormIndex()) if self.nav_mode != 'fao' else None,
            'seq_id': self.seq_id,
        })
        # prune entries with null value, so that defaults will take effect when the session is re-created
        state = dict((k, v) for k, v in state.iteritems() if v is not None)
        return state

    def get_xmlns(self):
        """
        :return: the xmlns header for the instance of the current session
        """
        metadata = self.fem.getForm().getMainInstance().getMetaData()
        return metadata.get("XMLNS")

    def evaluate_xpath(self, xpath):
        """
        :param xpath: the xpath expression to be evaluated EG "/data/question1"
        :return: the value stored in the referenced path
        at the moment only supports single values IE won't return nodesets
        We use the JavaRosa "Text" type as a factory to turn our String into and XPath
        """
        evaluation_context = self.fem.getForm().exprEvalContext
        args = JHashtable()
        result = {}
        try:
            m_text = JRText.XPathText(xpath, args)
            result['status'] = 'success'
            result['output'] = m_text.evaluate(evaluation_context)
        except XPathException, e:
            result['status'] = 'failure'
            result['output'] = e.getMessage()

        return result

    def output(self):
        if self.cur_event['type'] != 'form-complete':
            #warn that not at end of form
            pass

        instance_bytes = FormSerializer().serializeInstance(self.form.getInstance())
        return unicode(''.join(chr(b) for b in instance_bytes.tolist()), 'utf-8')

    def walk(self):
        form_ix = FormIndex.createBeginningOfFormIndex()
        tree = []
        self._walk(form_ix, tree)
        return tree

    def _walk(self, parent_ix, siblings):
        def step(ix, descend):
            next_ix = self.fec.getAdjacentIndex(ix, True, descend)
            self.fem.setQuestionIndex(next_ix)  # needed to trigger events in form engine
            return next_ix

        def ix_in_scope(form_ix):
            if form_ix.isEndOfFormIndex():
                return False
            elif parent_ix.isBeginningOfFormIndex():
                return True
            else:
                return FormIndex.isSubElement(parent_ix, form_ix)

        form_ix = step(parent_ix, True)
        while ix_in_scope(form_ix):
            relevant = self.fem.isIndexRelevant(form_ix)

            if not relevant:
                form_ix = step(form_ix, False)
                continue

            evt = self.__parse_event(form_ix)
            evt['relevant'] = relevant
            if evt['type'] == 'sub-group':
                siblings.append(evt)
                evt['children'] = []
                form_ix = self._walk(form_ix, evt['children'])
            elif evt['type'] == 'repeat-juncture':
                siblings.append(evt)
                evt['children'] = []
                for i in range(0, self.fem.getForm().getNumRepetitions(form_ix)):
                    subevt = {
                        'type': 'sub-group',
                        'ix': self.fem.getForm().descendIntoRepeat(form_ix, i),
                        'caption': evt['repetitions'][i],
                        'repeatable': True,
                        'children': [],
                    }

                    # kinda ghetto; we need to be able to track distinct repeat instances, even if their position
                    # within the list of repetitions changes (such as by deleting a rep in the middle)
                    # would be nice to have proper FormEntryAPI support for this
                    java_uid = self.form.getInstance().resolveReference(subevt['ix'].getReference()).hashCode()
                    subevt['uuid'] = hashlib.sha1(str(java_uid)).hexdigest()[:12]

                    evt['children'].append(subevt)
                    self._walk(subevt['ix'], subevt['children'])
                for key in ['repetitions', 'del-choice', 'del-header', 'done-choice']:
                    del evt[key]
                form_ix = step(form_ix, True)  # why True?
            else:
                siblings.append(evt)
                form_ix = step(form_ix, True)  # why True?

        return form_ix

    def _parse_current_event(self):
        self.cur_event = self.__parse_event(self.fem.getFormIndex())
        return self.cur_event

    def __parse_event (self, form_ix):
        event = {'ix': form_ix}

        status = self.fem.getEvent(form_ix)
        if status == self.fec.EVENT_BEGINNING_OF_FORM:
            event['type'] = 'form-start'
        elif status == self.fec.EVENT_END_OF_FORM:
            event['type'] = 'form-complete'
        elif status == self.fec.EVENT_QUESTION:
            event['type'] = 'question'
            self._parse_question(event)
        elif status == self.fec.EVENT_REPEAT_JUNCTURE:
            event['type'] = 'repeat-juncture'
            self._parse_repeat_juncture(event)
        else:
            event['type'] = 'sub-group'
            prompt = self.fem.getCaptionPrompt(form_ix)
            event.update(get_caption(prompt))
            if status == self.fec.EVENT_GROUP:
                event['repeatable'] = False
            elif status == self.fec.EVENT_REPEAT:
                event['repeatable'] = True
                event['exists'] = True
            elif status == self.fec.EVENT_PROMPT_NEW_REPEAT: #obsolete
                event['repeatable'] = True
                event['exists'] = False

        return event

    def _get_question_choices(self, q):
        return [choice(q, ch) for ch in q.getSelectChoices()]

    def _parse_style_info(self, rawstyle):
        info = {}

        if rawstyle != None:
            info['raw'] = rawstyle
            try:
                info.update([[p.strip() for p in f.split(':')][:2] for f in rawstyle.split(';') if f.strip()])
            except ValueError:
                pass

        return info

    def _parse_question (self, event):
        q = self.fem.getQuestionPrompt(event['ix'])

        event.update(get_caption(q))
        event['help'] = q.getHelpText()
        event['style'] = self._parse_style_info(q.getAppearanceHint())
        event['binding'] = q.getQuestion().getBind().getReference().toString()

        if q.getControlType() == Constants.CONTROL_TRIGGER:
            event['datatype'] = 'info'
        else:
            try:
                event['datatype'] = {
                    Constants.DATATYPE_NULL: 'str',
                    Constants.DATATYPE_TEXT: 'str',
                    Constants.DATATYPE_INTEGER: 'int',
                    Constants.DATATYPE_LONG: 'longint',
                    Constants.DATATYPE_DECIMAL: 'float',
                    Constants.DATATYPE_DATE: 'date',
                    Constants.DATATYPE_TIME: 'time',
                    Constants.DATATYPE_CHOICE: 'select',
                    Constants.DATATYPE_CHOICE_LIST: 'multiselect',
                    Constants.DATATYPE_GEOPOINT: 'geo',

                    # not supported yet
                    Constants.DATATYPE_BARCODE: 'barcode',
                    Constants.DATATYPE_BINARY: 'binary',
                }[q.getDataType()]
            except KeyError:
                event['datatype'] = 'unrecognized'

            if event['datatype'] in ('select', 'multiselect'):
                event['choices'] = self._get_question_choices(q)

            event['required'] = q.isRequired()

            value = q.getAnswerValue()
            if value == None:
                event['answer'] = None
            elif event['datatype'] in ('int', 'float', 'str', 'longint'):
                event['answer'] = value.getValue()
            elif event['datatype'] == 'date':
                event['answer'] = to_pdate(value.getValue())
            elif event['datatype'] == 'time':
                event['answer'] = to_ptime(value.getValue())
            elif event['datatype'] == 'select':
                event['answer'] = choice(q, selection=value.getValue()).ordinal()
            elif event['datatype'] == 'multiselect':
                event['answer'] = [choice(q, selection=sel).ordinal() for sel in value.getValue()]
            elif event['datatype'] == 'geo':
                event['answer'] = list(value.getValue())[:2]

    def _parse_repeat_juncture(self, event):
        r = self.fem.getCaptionPrompt(event['ix'])
        ro = r.getRepeatOptions()

        event.update(get_caption(r))
        event['header'] = ro.header
        event['repetitions'] = list(r.getRepetitionsText())

        event['add-choice'] = ro.add
        event['del-choice'] = ro.delete
        event['del-header'] = ro.delete_header
        event['done-choice'] = ro.done

    def next_event (self):
        self.fec.stepToNextEvent()
        return self._parse_current_event()

    def back_event (self):
        self.fec.stepToPreviousEvent()
        return self._parse_current_event()

    def answer_question (self, answer, _ix=None):
        ix = self.parse_ix(_ix)
        event = self.cur_event if ix is None else self.__parse_event(ix)

        if event['type'] != 'question':
            raise ValueError('not currently on a question')

        datatype = event['datatype']
        if datatype == 'unrecognized':
            # don't commit answers to unrecognized questions, since we
            # couldn't parse what was originally there. whereas for
            # _unsupported_ questions, we're parsing and re-committing the
            # answer verbatim
            return {'status': 'success'}

        def multians(a):
            if hasattr(a, '__iter__'):
                return a
            else:
                return str(a).split()

        if answer == None or str(answer).strip() == '' or answer == []:
            ans = None
        elif datatype == 'int':
            if isinstance(int(answer), long):
                ans = LongData(int(answer))
            else:
                ans = IntegerData(int(answer))
        elif datatype == 'longint':
            ans = LongData(int(answer))
        elif datatype == 'float':
            ans = DecimalData(float(answer))
        elif datatype == 'str' or datatype == 'info':
            ans = StringData(str(answer))
        elif datatype == 'date':
            ans = DateData(to_jdate(datetime.strptime(str(answer), '%Y-%m-%d').date()))
        elif datatype == 'time':
            ans = TimeData(to_jtime(datetime.strptime(str(answer), '%H:%M').time()))
        elif datatype == 'select':
            ans = SelectOneData(event['choices'][int(answer) - 1].to_sel())
        elif datatype == 'multiselect':
            ans = SelectMultiData(to_vect(event['choices'][int(k) - 1].to_sel() for k in multians(answer)))
        elif datatype == 'geo':
            ans = GeoPointData(to_arr((float(x) for x in multians(answer)), 'd'))

        result = self.fec.answerQuestion(*([ans] if ix is None else [ix, ans]))
        if result == self.fec.ANSWER_REQUIRED_BUT_EMPTY:
            return {'status': 'error', 'type': 'required'}
        elif result == self.fec.ANSWER_CONSTRAINT_VIOLATED:
            q = self.fem.getQuestionPrompt(*([] if ix is None else [ix]))
            return {'status': 'error', 'type': 'constraint', 'reason': q.getConstraintText()}
        elif result == self.fec.ANSWER_OK:
            return {'status': 'success'}

    def descend_repeat (self, rep_ix=None, _junc_ix=None):
        junc_ix = self.parse_ix(_junc_ix)
        if (junc_ix):
            self.fec.jumpToIndex(junc_ix)

        if rep_ix:
            self.fec.descendIntoRepeat(rep_ix - 1)
        else:
            self.fec.descendIntoNewRepeat()

        return self._parse_current_event()

    def delete_repeat (self, rep_ix, _junc_ix=None):
        junc_ix = self.parse_ix(_junc_ix)
        if (junc_ix):
            self.fec.jumpToIndex(junc_ix)

        self.fec.deleteRepeat(rep_ix)
        return self._parse_current_event()

    #sequential (old-style) repeats only
    def new_repetition (self):
        #currently in the form api this always succeeds, but theoretically there could
        #be unsatisfied constraints that make it fail. how to handle them here?
        self.fec.newRepeat(self.fem.getFormIndex())

    def set_locale(self, lang):
        self.fec.setLanguage(lang)
        return self._parse_current_event()

    def get_locales(self):
        return self.fem.getLanguages() or []

    def get_lang(self):
        if self.fem.getForm().getLocalizer() is not None:
            return self.fem.getLanguage()
        else:
            return None

    def finalize(self):
        self.fem.getForm().postProcessInstance()

    def parse_ix(self, s_ix):
        return index_from_str(s_ix, self.form)

    def form_title(self):
        return self.form.getTitle()

    def response(self, resp, ev_next=None, no_next=False):
        if no_next:
            navinfo = {}
        elif self.nav_mode == 'prompt':
            if ev_next is None:
                ev_next = next_event(self)
            navinfo = {'event': ev_next}
        elif self.nav_mode == 'fao':
            navinfo = {'tree': self.walk()}

        resp.update(navinfo)
        resp.update({'seq_id': self.seq_id})
        return resp

class choice(object):
    def __init__(self, q, select_choice=None, selection=None):
        self.q = q

        if select_choice is not None:
            self.select_choice = select_choice

        elif selection is not None:
            selection.attachChoice(q.getFormElement())
            self.select_choice = selection.choice

    def to_sel(self):
        return Selection(self.select_choice)

    def ordinal(self):
        return self.to_sel().index + 1

    def __repr__(self):
        return self.q.getSelectChoiceText(self.select_choice)

    def __json__(self):
        return json.dumps(repr(self))

def load_file(path):
    if not os.path.exists(path):
        raise Exception('no form found at %s' % path)

    with codecs.open(path, encoding='utf-8') as f:
        return f.read()

def get_loader(spec, **kwargs):
    if not spec:
        return lambda: None

    type, val = spec
    return {
        'uid': lambda: load_file(val),
        'raw': lambda: val,
        'url': lambda: query_factory(auth=kwargs.get('api_auth', None), format='raw')(val),
    }[type]

def init_context(xfsess):
    """return the 'extra' response context needed when initializing a session"""
    return {
        'title': xfsess.form_title(),
        'langs': xfsess.get_locales(),
    }


def open_form(form_spec, inst_spec=None, **kwargs):

    try:
        xform_xml = get_loader(form_spec, **kwargs)()
    except Exception, e:
        return {'error': 'There was a problem downloading the XForm: %s' % str(e)}

    try:
        instance_xml = get_loader(inst_spec, **kwargs)()
    except Exception, e:
        return {'error': 'There was a problem downloading the XForm instance: %s' % str(e)}

    xfsess = XFormSession(xform_xml, instance_xml, **kwargs)
    global_state.cache_session(xfsess)
    with global_state.get_lock(xfsess.uuid):
        with xfsess:
            # triggers persisting of the fresh session
            extra = {'session_id': xfsess.uuid}
            extra.update(init_context(xfsess))
            response = xfsess.response(extra)
            return response


@require_xform_session
def answer_question(xform_session, answer, ix):
    result = xform_session.answer_question(answer, ix)
    if result['status'] == 'success':
        return xform_session.response({'status': 'accepted'})
    else:
        result['status'] = 'validation-error'
        return xform_session.response(result, no_next=True)


@require_xform_session
def edit_repeat(xform_session, ix):
    ev = xform_session.descend_repeat(ix)
    return {'event': ev}


@require_xform_session
def new_repeat(xform_session, form_ix):
    ev = xform_session.descend_repeat(_junc_ix=form_ix)
    return xform_session.response({}, ev)


@require_xform_session
def delete_repeat(xform_session, rep_ix, form_ix):
    ev = xform_session.delete_repeat(rep_ix, form_ix)
    return xform_session.response({}, ev)


#  sequential (old-style) repeats only
@require_xform_session
def new_repetition(xform_session):
    #  new repeat creation currently cannot fail, so just blindly proceed to the next event
    xform_session.new_repetition()
    return {'event': next_event(xform_session)}


@require_xform_session
def skip_next(xfrom_session):
    return {'event': next_event(xfrom_session)}


@require_xform_session
def go_back(xform_session):
    (at_start, event) = prev_event(xform_session)
    return {'event': event, 'at-start': at_start}


# fao mode only
@require_xform_session
def submit_form(xform_session, answers, prevalidated):
    errors = dict(
        filter(lambda resp: resp[1]['status'] != 'success',
            ((_ix, xform_session.answer_question(answer, _ix)) for _ix, answer in answers.iteritems()))
    )

    if errors or not prevalidated:
        resp = {'status': 'validation-error', 'errors': errors}
    else:
        resp = form_completion(xform_session)
        resp['status'] = 'success'

    xml = xform_session.output()
    # only try processing if user is on sql backend
    if xform_session.uses_sql_backend:
        process_form_xml(
            xform_session.orig_params['api_auth'],
            xml,
            xform_session.orig_params['session_data']
        )

    return xform_session.response(resp, no_next=True)


@require_xform_session
def set_locale(xform_session, lang):
    ev = xform_session.set_locale(lang)
    return xform_session.response({}, ev)


@require_xform_session
def current_question(xform_session, override_state=None):
    """override_state kwarg used by require_xform_session decorator"""
    extra = {'lang': xform_session.get_lang()}
    extra.update(init_context(xform_session))
    return xform_session.response(extra, xform_session.cur_event)


def next_event (xfsess):
    ev = xfsess.next_event()
    if ev['type'] != 'form-complete':
        return ev
    else:
        ev.update(form_completion(xfsess))
        return ev


def prev_event (xfsess):
    at_start, ev = False, xfsess.back_event()
    if ev['type'] == 'form-start':
        at_start, ev = True, xfsess.next_event()
    return at_start, ev


def save_form(xfsess):
    xfsess.finalize()
    xml = xfsess.output()
    return (None, xml)


def form_completion(xfsess):
    return dict(zip(('save-id', 'output'), save_form(xfsess)))


def get_caption(prompt):
    return {
        'caption': prompt.getLongText(),
        'caption_audio': prompt.getAudioText(),
        'caption_image': prompt.getImageText(),
        'caption_video': prompt.getSpecialFormQuestionText(FormEntryPrompt.TEXT_FORM_VIDEO),
        # TODO use prompt.getMarkdownText() when commcare jars support it
        'caption_markdown': prompt.getSpecialFormQuestionText("markdown"),
    }


def purge():
    resp = global_state.purge()
    resp.update({'status': 'ok'})
    return resp


class Actions:
    NEW_FORM = 'new-form'
    ANSWER = 'answer'
    ADD_REPEAT = 'add-repeat'
    NEXT = 'next'
    BACK = 'back'
    CURRENT = 'current'
    HEARTBEAT = 'heartbeat'
    EDIT_REPEAT = 'edit-repeat'
    NEW_REPEAT = 'new-repeat'
    DELETE_REPEAT = 'delete-repeat'
    SUBMIT_ALL = 'submit-all'
    SET_LANG = 'set-lang'
    PURGE_STALE = 'purge-stale'
    GET_INSTANCE = 'get-instance'
    EVALUATE_XPATH = 'evaluate-xpath'
    SYNC_USER_DB = 'sync-db'
