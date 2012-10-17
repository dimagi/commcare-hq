

def pillow_processor():
    pool = ConnectionPool(factory=Connection, backend='gevent')

    db = XFormInstance.get_db()
    db.server.pool = pool

    #stream = ChangesStream(db, feed='continuous', heartbeat=True, filter= "auditcare/filter_auditdocs", since=139400)
    #stream = ChangesStream(db, feed='continuous', heartbeat=True, filter= "auditcare/filter_auditdocs", since=0)
    stream = ChangesStream(db, feed='continuous', heartbeat=True, filter= "couchforms/xforms", since=0)
    print 'got changes'
    output = []
    from datetime import datetime
    start= datetime.utcnow()

    for change in stream:
        dump_json(db, change)
        #data = db.get(change['id'])
        #output.append(ujson.dumps(data))
    print (datetime.utcnow() - start).seconds


    def fold_fun(change, acc):
        acc.append(change)
        print "appending %s" % change
        return acc
    def process_change(c):
