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
                if self.owner_ids and len(self.owner_ids) < MAX_IDS:
                    yield "owner_id:(%s)" % (OR(self.owner_ids))
                if self.user_ids and len(self.user_ids) < MAX_IDS:
                    yield "user_id:(%s)" % (OR(self.user_ids))

            if user_filters:
                yield "(%s)" % OR(user_filters)

            if self.case_type:
                yield "type:(%s)" % self.case_type

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