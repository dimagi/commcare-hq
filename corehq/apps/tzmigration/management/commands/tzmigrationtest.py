import collections
from django.core.management.base import LabelCommand
import logging
from couchdbkit import ResourceNotFound
from corehq.apps.tzmigration.timezonemigration import json_diff
from corehq.util.dates import iso_string_to_datetime
from couchforms import convert_xform_to_json
from couchforms.models import XFormInstance
from couchforms.util import adjust_datetimes, scrub_meta
from dimagi.utils.couch.database import iter_docs
from couchforms.dbaccessors import get_form_ids_by_type


def is_datetime(string):
    if not isinstance(string, basestring):
        return False

    try:
        iso_string_to_datetime(string)
    except ValueError:
        return False
    else:
        return True


class Command(LabelCommand):
    def handle_label(self, domain, **options):
        self.tzmigrationtest(domain)

    def tzmigrationtest(self, domain):
        xform_ids = get_form_ids_by_type(domain, 'XFormInstance')
        headers_printed = set()
        diffs = collections.Counter()
        for xform in iter_docs(XFormInstance.get_db(), xform_ids):
            xform_id = xform['_id']
            # can this fail?
            try:
                xml = XFormInstance.get_db().fetch_attachment(xform_id, 'form.xml')
            except ResourceNotFound:
                logging.warn('Form {} does not have an attachment form.xml'
                             .format(xform_id))
                continue
            try:
                form_json = convert_xform_to_json(xml)
            except Exception:
                logging.exception(u'failed on form\n{}'.format(xml))
                continue
            adjust_datetimes(form_json)
            # this is actually in-place bc of how jsonobject works
            scrub_meta(XFormInstance.wrap({'form': form_json, '_id': xform_id}))

            def _print(msg):
                if not xform_id in headers_printed:
                    print "==={}===".format(xform_id)
                    print "===ACTUAL==="
                    print xform['form']
                    print "===NEW==="
                    print form_json
                    headers_printed.add(xform_id)
                print '[{}] {}'.format(xform_id, msg)

            for type_, path, first, second in json_diff(xform['form'], form_json):
                path = '/'.join(map(unicode, path))

                if type_ == 'diff':
                    if path in ('meta/timeEnd', 'meta/timeStart') or path.endswith('case/@date_modified'):
                        continue
                    try:
                        if is_datetime(first) and is_datetime(second):
                            diffs[path] += 1
                            continue
                    except Exception:
                        pass

                    _print('differing values at {}: {!r}, {!r}'.format(
                        path, first, second))
                elif type_ == 'missing':
                    _print('missing value at {}: {!r}, {!r}'.format(
                        path, first, second))
                else:
                    _print('differing types at {} ({} vs {}): {!r}, {!r}'.format(
                        path, type(first), type(second), first, second))

        print diffs
