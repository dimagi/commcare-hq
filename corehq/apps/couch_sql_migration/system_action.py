import json

from corehq.form_processor.backends.couch.dbaccessors import FormAccessorCouch
from corehq.form_processor.backends.sql.dbaccessors import FormAccessorSQL
from corehq.form_processor.exceptions import XFormNotFound
from corehq.form_processor.interfaces.dbaccessors import ARCHIVE_FORM
from corehq.form_processor.system_action import do_system_action as _do_system_action

from .asyncforms import get_case_ids


def do_system_action(couch_form):
    name = couch_form.form_data["name"]
    args_json = json.loads(couch_form.form_data["args"])
    try:
        domain, args, iter_forms_and_cases = _load_action_data(name, args_json)
    except IgnoreSystemAction:
        return []
    if couch_form.domain != domain:
        raise UnauthorizedSystemAction(repr(couch_form))
    _do_system_action(name, args)
    return iter_forms_and_cases()


def _load_action_data(name, args_json):
    return _actions[name](args_json)


def _action(name):
    def decorator(func):
        assert name not in _actions, name
        _actions[name] = func
        return func
    return decorator


_actions = {}


@_action(ARCHIVE_FORM)
def _archive_form_data(args_json):
    def iter_forms_and_cases():
        couch_form = FormAccessorCouch.get_form(form.form_id)
        yield form.form_id, get_case_ids(couch_form)
    args = list(args_json)
    try:
        args[0] = form = FormAccessorSQL.get_form(args_json[0])
    except XFormNotFound:
        couch_form = FormAccessorCouch.get_form(args_json[0])
        if couch_form.doc_type != "XFormInstance":
            # form has not been migrated yet; will be copied as "unprocessed form"
            raise IgnoreSystemAction
        # edge case: form was archived when migration started, then unarchived
        # during migration -> should be migrated as unarchived form
        raise
    return form.domain, args, iter_forms_and_cases


class IgnoreSystemAction(Exception):
    pass


class UnauthorizedSystemAction(Exception):
    pass
