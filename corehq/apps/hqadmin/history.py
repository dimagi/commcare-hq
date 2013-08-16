from couchdbkit import Consumer


def get_recent_changes(db, limit=500):
    c = Consumer(db)
    changes = c.fetch(limit=limit, descending=True, include_docs=True)['results']
    for row in changes:
        yield {
            'id':row['id'],
            'rev': row['changes'][0]['rev'],
            'domain': row['doc'].get('domain', '[no domain]'),
            'doc_type': row['doc'].get('doc_type', '[no doc_type]'),
        }
