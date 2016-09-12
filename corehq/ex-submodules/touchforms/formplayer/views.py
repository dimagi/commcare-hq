from functools import wraps
from django.http.response import HttpResponseServerError, Http404
from django.shortcuts import get_object_or_404
from django.conf import settings
from django.views.decorators.http import require_POST

from corehq.form_processor.utils.general import use_sqlite_backend
from touchforms.formplayer.models import XForm, EntrySession
from touchforms.formplayer.autocomplete import autocompletion, DEFAULT_NUM_SUGGESTIONS
from django.http import HttpResponseRedirect, HttpResponse,\
    HttpResponseNotFound
from django.core.urlresolvers import reverse
import logging
import json
from collections import defaultdict
from touchforms.formplayer.signals import xform_received
from django.template.context import RequestContext
from django.shortcuts import render_to_response
from django.views.decorators.csrf import csrf_exempt
from django.utils.translation import ugettext as _
import tempfile
import os
from . import api
from touchforms.formplayer.api import DjangoAuth, get_raw_instance
from touchforms.formplayer.const import PRELOADER_TAG_UID
from datetime import datetime
from dimagi.utils.web import json_response


def debug_only(fn):
    @wraps(fn)
    def _inner(*args, **kwargs):
        if not settings.DEBUG:
            return HttpResponseNotFound()
        else:
            return fn(*args, **kwargs)

    return _inner


@debug_only
def xform_list(request):
    forms_by_namespace = defaultdict(list)
    success = True
    notice = ""
    if request.method == "POST":
        if "file" in request.FILES:
            file = request.FILES["file"]
            try:
                tmp_file_handle, tmp_file_path = tempfile.mkstemp()
                tmp_file = os.fdopen(tmp_file_handle, 'w')
                tmp_file.write(file.read())
                tmp_file.close()
                XForm.from_file(tmp_file_path, str(file))
                notice = "Created form: %s " % file
            except Exception, e:
                logging.error("Problem creating xform from %s: %s" % (file, e))
                success = False
                notice = "Problem creating xform from %s: %s" % (file, e)
        else:
            success = False
            notice = "No uploaded file set."
            
    for form in XForm.objects.all():
        forms_by_namespace[form.namespace].append(form)
    return render_to_response("formplayer/xform_list.html", {
            'forms_by_namespace': dict(forms_by_namespace),
            "success": success,
            "notice": notice
        }, context_instance=RequestContext(request))


@debug_only
def download(request, xform_id):
    """
    Download an xform
    """
    xform = get_object_or_404(XForm, id=xform_id)
    try:
        contents = xform.file.read()
    except IOError:
        # file not found, don't fail hard as in a multi-worker environment
        # this method is just kind of deprecated.
        return HttpResponseNotFound("Sorry that form is no longer available.")
    else:
        response = HttpResponse(content_type='application/xml')
        response.write(contents)
        return response


def _coalesce(*args):
    for arg in args:
        if arg is not None:
            return arg
    return None


@csrf_exempt
@debug_only
def enter_form(request, **kwargs):
    xform_id = kwargs.get('xform_id')
    xform = kwargs.get('xform')
    instance_xml = kwargs.get('instance_xml')
    session_data = _coalesce(kwargs.get('session_data'), {})
    input_mode = _coalesce(kwargs.get('input_mode'), 'touch')
    submit_callback = _coalesce(kwargs.get('onsubmit'), default_submit)
    abort_callback = _coalesce(kwargs.get('onabort'), _default_abort)
    force_template = _coalesce(kwargs.get('force_template'), None)
    offline_mode = kwargs.get('offline', False)

    # support for backwards compatibility; preloaders are DEPRECATED
    preload_data = kwargs.get('preloader_data')
    if preload_data:
        session_data['preloaders'] = preload_data

    if not xform:
        try:
            xform = get_object_or_404(XForm, id=xform_id)
        except ValueError:
            raise Http404()

        if not os.path.exists(xform.file.path):
            raise Http404()
    if request.method == "POST":
        if request.POST["type"] == 'form-complete':
            instance_xml = request.POST["output"]
            return _form_entry_complete(request, xform, instance_xml,
                                       submit_callback)

        elif request.POST["type"] == 'form-aborted':
            return _form_entry_abort(request, xform, abort_callback)

    return _form_entry_new(request, xform, instance_xml, session_data,
                          input_mode, offline_mode, force_template)

def _form_entry_new(request, xform, instance_xml, session_data, input_mode,
                   offline_mode, force_template=None):
    """start a new touchforms/typeforms session"""
    if force_template is not None:
        templ = force_template
    else:
        templ = {
            'touch': 'touchforms/touchscreen.html',
            'type': 'typeforms.html',
        }[input_mode]
    if offline_mode:
        touchforms_url = 'http://localhost:%d' % settings.OFFLINE_TOUCHFORMS_PORT
    else:
        touchforms_url = reverse('xform_player_proxy')

    return render_to_response(templ, {
            "touchforms_url": touchforms_url,
            "form": xform,
            "mode": 'xform',
            "instance_xml": json.dumps(instance_xml),
            "session_data": json.dumps(session_data),
            "dim": _get_player_dimensions(request),
            "fullscreen": request.GET.get('mode', '').startswith('full'),
            "lang": request.GET.get('lang'),
            'session_id': request.GET.get('sess'),
            'maps_api_key': settings.GMAPS_API_KEY,
            'use_sqlite_backend': hasattr(request, 'domain') and use_sqlite_backend(request.domain),
        }, context_instance=RequestContext(request))

def _form_entry_abort(request, xform, callback):
    """handle an aborted form entry session"""
    return callback(xform)

def _form_entry_complete(request, xform, instance_xml, callback):
    """handle a completed form entry session (xform finished and submitted)"""
    xform_received.send(sender="player", instance=instance_xml)
    return callback(xform, instance_xml)

def default_submit(xform, instance_xml):
    response = HttpResponse(content_type='application/xml')
    response.write(instance_xml)
    return response

def _default_abort(xform, abort_url='/'):
    return HttpResponseRedirect(abort_url)

# this function is here for backwards compatibility (just BHOMA?); use enter_form() instead
def play(request, xform_id, callback=None, preloader_data=None, input_mode=None,
         abort_callback=_default_abort, force_template=None):
    """
    Play an XForm.

    xform_id - which xform to play
    callback(xform, instance_xml) - action to perform when form is submitted or aborted (both via POST) 
        default behavior is to display the xml, and return to the form list, respectively
        for abort, instance_xml will be None
    preloader_data - data to satisfy form preloaders: {preloader type => {preload param => preload value}} 
    input_mode - 'touch' for touchforms, 'type' for typeforms
    instance_xml - an xml instance that, if present, will be edited during the form session
    """

    return enter_form(request,
                      xform_id=xform_id,
                      preloader_data=preloader_data,
                      input_mode=input_mode,
                      onsubmit=callback,
                      onabort=abort_callback,
                      force_template=force_template,
                      )

def _get_player_dimensions(request):
    def get_dim(getparam, settingname):
        dim = request.GET.get(getparam)
        if not dim:
            try:
                dim = getattr(settings, settingname)
            except AttributeError:
                pass
        return dim

    return {
        'width': get_dim('w', 'TOUCHSCREEN_WIDTH'),
        'height': get_dim('h', 'TOUCHSCREEN_HEIGHT')
    }

@csrf_exempt
@require_POST
def player_proxy(request):
    """
    Proxy to an xform player, to avoid cross-site scripting issues
    """
    data = request.body
    auth_cookie = request.COOKIES.get('sessionid')
    try:
        response = api.post_data(data, auth=DjangoAuth(auth_cookie))
        _track_session(request, json.loads(data), json.loads(response))
        return HttpResponse(response, content_type='application/json')
    except IOError:
        logging.exception('Unable to connect to touchforms.')
        msg = _(
            'An error occurred while trying to connect to the CloudCare service. '
            'If you have problems filling in the rest of your form please report an issue.'
        )
        return HttpResponseServerError(json.dumps({'message': msg}), content_type='application/json')


def _track_session(request, payload, response):
    def _concat_name(name):
        return u'...{0}'.format(name[-96:]) if len(name) > 99 else name

    action = payload['action']
    if action == 'new-form' and 'form-url' in payload and 'session_id' in response:
        session_id = response['session_id']
        session_name = payload['session-data'].get(
            'session_name', response.get('title', _('Unknown Form'))
        )
        app_id = payload['session-data'].get('app_id', None)
        sess = EntrySession(
            session_id=session_id,
            user=request.user,
            form=payload['form-url'],
            session_name=_concat_name(session_name),
            app_id=app_id,
        )
        sess.save()
    elif 'session-id' in payload:
        try:
            sess = EntrySession.objects.get(session_id=payload['session-id'])
        except EntrySession.DoesNotExist:
            # we must have manually purged our session. don't bother doing
            # any updates to it.
            pass
        else:
            if action == 'submit-all':
                if response['status'] == 'success':
                    sess.delete()
            elif action not in ('current', 'heartbeat'):
                # these actions don't make the session dirty
                if sess is not None:
                    sess.last_activity_date = datetime.utcnow()
                    sess.save()
            elif response.get('error') == 'invalid session id':
                # purge dead sessions
                sess.delete()

# DEPRECATED    
def api_preload_provider(request):
    param = request.GET.get('param', "")
    param = param.strip().lower()

    value = param
    if param == PRELOADER_TAG_UID:
        import uuid
        value = uuid.uuid4().hex

    return HttpResponse(value)

def api_autocomplete(request):
    domain = request.GET.get('domain')
    key = request.GET.get('key', '')
    max_results = int(request.GET.get('max', str(DEFAULT_NUM_SUGGESTIONS)))

    if domain is None or key is None or max_results is None:
        return HttpResponse("Please specify 'domain', 'key' and 'max' parameters.", status=400)

    try:
        response = HttpResponse(json.dumps(autocompletion(domain, key, max_results)), 'text/json')
    except Exception:
        logging.error("Exception on getting response from api_autocomplete")
        return HttpResponse(status=500)

    return response


def player_abort(request):
    class TimeoutException(Exception):
        pass

    try:
        raise TimeoutException("A touchscreen view has timed out and was aborted")
    except TimeoutException:
        logging.exception('')

    try:
        redirect_to = reverse(settings.TOUCHFORMS_ABORT_DEST)
    except AttributeError:
        redirect_to = '/'

    return HttpResponseRedirect(redirect_to)
