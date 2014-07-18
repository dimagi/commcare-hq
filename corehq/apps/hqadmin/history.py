import csv
from couchdbkit import Consumer


def download_changes(db, limit, target):
    """
    Download changes to a target file-like object
    """
    writer = csv.writer(target, dialect=csv.excel)
    # headings
    keys = [
        'domain',
        'doc_type',
        'date',
        'id',
        'rev',
    ]
    writer.writerow(keys)
    for row in get_recent_changes(db, limit):
        writer.writerow([row[k] for k in keys])


def get_recent_changes(db, limit):
    c = Consumer(db)
    changes = c.fetch(limit=limit, descending=True, include_docs=True)['results']
    for row in changes:
        yield {
            'id':row['id'],
            'rev': row['changes'][0]['rev'],
            'domain': row['doc'].get('domain', '[no domain]'),
            'doc_type': row['doc'].get('doc_type', '[no doc_type]'),
            'date': _guess_date(row['doc']),
        }

def _guess_date(doc):
    # note: very quick and dirty approach to this
    properties_to_check = (
        'server_modified_on',  # cases
        'received_on',  # forms
        'built_on',  # built apps
        'date',  # shotgun
    )
    for p in properties_to_check:
        val = doc.get(p)
        if val:
            return val
    return '[no date]'
