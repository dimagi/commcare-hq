from dimagi.utils.couch.database import get_db
from dimagi.utils.decorators import inline

class CasePaginator():

    def __init__(self, domain, params, case_type=None, owner_ids=None, user_ids=None, status=None):
        self.domain = domain
        self.params = params
        self.case_type = case_type
        self.owner_ids = owner_ids
        self.user_ids = user_ids
        self.status = status or None
        assert self.status in ('open', 'closed', None)

    def results(self):
        """Lucene Results"""

        # there's no point doing filters that are like owner_id:(x1 OR x2 OR ... OR x612)
        # so past a certain number just exclude
        MAX_IDS = 50
        
        def join_None(string):
            def _inner(things):
                return string.join([thing or '""' for thing in things])
            return _inner

        AND = join_None(' AND ')
        OR = join_None(' OR ')
        @AND
        @inline
        def query():
            if self.params.search:
                yield "(%s)" % self.params.search

            yield "exactDomain:(exact%sexact)" % self.domain

            @list
            @inline
            def user_filters():
                def _qterm(key, list):
                    if list and len(list) < MAX_IDS:
                        yield "(%(key)s:(%(ids)s))" % \
                            {"key": key, "ids": OR(list)}
                    # demo user hack
                    elif list and "demo_user" not in list:
                        yield "-%(key)s:demo_user" % {"key": key}
                
                for val in _qterm("owner_id", self.owner_ids):
                    yield val
                for val in _qterm("user_id", self.user_ids):
                    yield val
                

            if user_filters:
                yield "%s" % OR(user_filters)

            if self.case_type:
                yield 'type:"%s"' % self.case_type

            if self.status:
                yield "is:(%s)" % self.status
        
        results = get_db().search("case/search",
            q=query,
            handler="_fti/_design",
            skip=self.params.start,
            limit=self.params.count,
            sort="\sort_modified",
            stale='ok',
        )
        return results