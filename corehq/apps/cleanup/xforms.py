from corehq.apps.users.models import CouchUser
from corehq.elastic import get_es
from couchforms.models import XFormError
from dimagi.utils.couch.database import iter_docs


def get_problem_ids(domain, since=None):
    startkey = [domain, "by_type", "XFormError"]
    endkey = startkey + [{}]
    if since:
        startkey.append(since.isoformat())

    return [row['id'] for row in XFormError.get_db().view(
        "receiverwrapper/all_submissions_by_domain",
        startkey=startkey,
        endkey=endkey,
        reduce=False
    )]

def iter_problem_forms(domain, since=None):
    for doc in iter_docs(XFormError.get_db(), get_problem_ids(domain, since)):
        yield XFormError.wrap(doc)

def guess_domain(form):
    """
    Given a form (that presumably has no known domains) guess what domain it belogs to
    by looking for other forms submitted with this xmlns or by this user
    """

    def _domains_matching(key, value):
        es = get_es()
        throwaway_facet_name = 'facets'
        query = {
            "filter":{
                "term":{
                    key: value
                }
            },
            "facets":{
                throwaway_facet_name: {
                    "terms":{
                            "field":"domain.exact",
                            "size":1000
                        },
                        "facet_filter":{
                        "term":{
                            key: value
                        }
                    }
                }
            }
        }
        res = es['xforms'].post('_search', data=query)
        return [r['term'] for r in res['facets'][throwaway_facet_name]['terms']]

    xmlns_domains = username_domains = []

    if form.metadata.userID:
        user = CouchUser.get_by_user_id(form.metadata.userID)
        if user:
            username_domains = user.domains
            if len(username_domains) == 1:
                return username_domains

    if form.xmlns:
        xmlns_domains = _domains_matching("xmlns.exact", form.xmlns)
        if len(xmlns_domains) == 1:
            return xmlns_domains

    if xmlns_domains and username_domains:
        intersection = set(xmlns_domains).intersection(set(username_domains))
        if intersection:
            return list(intersection)

    return list(set(xmlns_domains).union(set(username_domains)))
