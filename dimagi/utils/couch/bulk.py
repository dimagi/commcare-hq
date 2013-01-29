from collections import defaultdict

class CouchTransaction(object):

    def __init__(self):
        self.depth = 0
        self.docs_to_delete = defaultdict(list)
        self.docs_to_save = defaultdict(dict)

    def delete(self, doc):
        self.docs_to_delete[doc.__class__].append(doc)

    def delete_all(self, docs):
        for doc in docs:
            self.delete(doc)

    def save(self, doc):
        cls = doc.__class__
        if not doc.get_id:
            doc._id = cls.get_db().server.next_uuid()
        self.docs_to_save[cls][doc.get_id] = doc

    def preview_save(self, cls=None):
        if cls:
            return self.docs_to_save[cls].values()
        else:
            return [doc for _cls in self.docs_to_save.keys()
                            for doc in self.preview_save(cls=_cls)]

    def commit(self):
        for cls, docs in self.docs_to_delete.items():
            cls.get_db().bulk_delete(docs)

        for cls, doc_map in self.docs_to_save.items():
            docs = doc_map.values()
            cls.bulk_save(docs)

    def __enter__(self):
        self.depth += 1
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.depth -= 1
        if self.depth == 0 and not exc_type:
            self.commit()
