import datetime
from dimagi.utils.couch.database import iter_docs
from corehq.util.couch import IterDB
from django.core.management.base import NoArgsCommand
from couchforms.models import XFormInstance


def get_form_received_on_by_id(domain):
    results = XFormInstance.get_db().view(
        "couchforms/all_submissions_by_domain",
        startkey=[domain, "by_date"],
        endkey=[domain, "by_date", {}],
        reduce=False,
    ).all()
    return [(result['id'], result['key'][2]) for result in results]


def _fix_weird_datetime_string(weird_datetime_string):
    return datetime.datetime.strptime(
        weird_datetime_string, '%Y-%m-%dT%H:%M:%S+00:00Z'
    ).isoformat() + 'Z'


def _tests():
    # just a jenky/low overhead way to unit test
    assert (
        _fix_weird_datetime_string('2012-05-18T10:22:25+00:00Z')
        == '2012-05-18T10:22:25Z'
    )


class Command(NoArgsCommand):
    option_list = NoArgsCommand.option_list + ()

    seen_doc_ids = {}

    def handle_noargs(self, **options):
        _tests()

        received_on_by_id = get_form_received_on_by_id('pact')
        print ('{} total forms in domain'
               .format(len(received_on_by_id)))
        weird_received_on = [
            (id, received_on)
            for (id, received_on) in received_on_by_id
            if '+' in received_on
        ]
        print ('{} forms with weird received on'
               .format(len(weird_received_on)))
        # make sure all these dates fit the expected weird format
        bad_format_error = None
        for id, received_on in weird_received_on:
            try:
                _fix_weird_datetime_string(received_on)
            except ValueError as bad_format_error:
                print bad_format_error, id, received_on
        if bad_format_error:
            exit(1)

        db = XFormInstance.get_db()
        with IterDB(db) as iter_db:
            for doc in iter_docs(db, [id for id, _ in weird_received_on], 500):
                doc['received_on'] = _fix_weird_datetime_string(doc['received_on'])
                iter_db.save(doc)

        print 'Saved:'
        for id in iter_db.saved_ids:
            print id
        print 'Errors:'
        for id in iter_db.error_ids:
            print id
