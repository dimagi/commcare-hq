from couchexport.models import SavedBasicExport
from pillowtop.listener import BasicPillow


class BlobDeletionPillow(BasicPillow):

    include_docs = False
    doc_types = {cls.__name__: cls for cls in [
        # list of all model classes that use BlobMixin
        SavedBasicExport,
    ]}

    def change_trigger(self, changes_dict):
        if not changes_dict.get('deleted', False):
            return None
        doc = self.db.get(changes_dict['id'])
        if doc.get('doc_type') not in self.doc_types or not doc['external_blobs']:
            return None
        changes_dict['doc'] = doc
        return changes_dict

    def change_transport(self, doc):
        # delete attachment from blob db
        obj = self.doc_types[doc["doc_type"]](doc)
        for name in obj.external_blobs:
            obj.delete_attachment(name)
