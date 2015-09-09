from corehq.apps.hqcase.management.commands.ptop_fast_reindexer import ElasticReindexer
from corehq.pillows.user import UserPillow, UnknownUsersPillow
from couchforms.models import XFormInstance


class Command(ElasticReindexer):
    help = "Fast reindex of user elastic index by using the domain view and reindexing users"

    doc_class = XFormInstance
    view_name = 'reports_forms/all_forms'
    pillow_class = UnknownUsersPillow
    indexing_pillow_class = UserPillow
    own_index_exists = False

    def get_extra_view_kwargs(self):
        return {'startkey': ['submission'], 'endkey': ['submission', {}]}

    def process_row(self, row, count):
        doc = _make_view_dict_look_like_xform_doc(row)
        super(Command, self).process_row({'id': doc['_id'], 'doc': doc}, count)


def _make_view_dict_look_like_xform_doc(emitted_dict):
    # this is an optimization hack for preindexing - in order to avoid getting the
    # full xform docs out of couch we just transform the view key/values into what
    # the pillow would expect to get from the doc
    domain = emitted_dict['key'][1]
    user_id = emitted_dict['value'].get('user_id')
    username = emitted_dict['value'].get('username')
    xform_id = emitted_dict['id']
    return {
        '_id': xform_id,
        'doc_type': 'XFormInstance',
        'domain': domain,
        'form': {
            'meta': {
                'userID': user_id,
                'username': username,
            }
        }
    }
