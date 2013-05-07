from couchdbkit import ResourceNotFound


class MockCouch(object):
    def __init__(self, mock_data):
        self.mock_data = mock_data

    def view(self, *args, **kwargs):
        return MockResult(self.mock_data)

    def save_doc(self, doc, **params):
        self.mock_data[doc["_id"]] = doc

    def get(self, docid, rev=None, wrapper=None):
        doc = self.mock_data.get(docid, None)
        if not doc:
            raise ResourceNotFound
        elif wrapper:
            return wrapper(doc)
        else:
            return doc

    def open_doc(self, docid):
        doc = self.mock_data.get(docid, None)
        return doc

class MockResult(object):
    def __init__(self, rows):
        self.rows = rows

    @property
    def total_rows(self):
        return len(self.rows)

    def __iter__(self):
        return iter(self.rows)
