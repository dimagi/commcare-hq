import simplejson
from corehq.apps.api.es import XFormES, CaseES
from pact.enums import PACT_DOTS_DATA_PROPERTY

def get_case_id(xform):
    if xform['form'].has_key('case'):
        if xform['form']['case'].has_key('case_id'):
            return xform['form']['case']['case_id']
        elif xform['form']['case'].has_key('@case_id'):
            return xform['form']['case']['@case_id']
    return None


def get_patient_display_cache(case_ids):
    """
    For a given set of case_ids, return name and pact_ids
    """
    case_es = CaseES()
    query = {
        "fields": [
            "_id",
            "last_name",
            "first_name",
            "name",
            "pactid",
        ],
        "script_fields": {
            "case_id": {
                "script": "_source._id"
            }
        },
        "filter": {
            "and": [
                {
                    "term": {
                        "domain.exact": "pact"
                    }
                },
                {
                    "ids": {
                        "values": case_ids,
                        #                        "execution": "or",
                        #                        "_cache": True
                    }
                }
            ]
        }
    }
    print simplejson.dumps(query)
    res = case_es.run_query(query)
    #print res['hits']['total']
    ret = {}
    if res is not None:
        for entry in res['hits']['hits']:
        #            entry['fields']['case_id'] = entry['fields']['_id']
        #            del(entry['fields']['_id'])
            ret[entry['fields']['case_id']] = entry['fields']
    return ret


MISSING_DOTS_QUERY = {
    "query": {
        "filtered": {
            "query": {
                "match_all": {}
            },
            "filter": {
                "and": [
                    {
                        "term": {
                            "domain.exact": "pact"
                        }
                    },
                    {
                        "term": {
                            "form.#type": "dots_form"
                        }
                    },
                    {
                        "missing": {
                            "field": "%s.processed" % PACT_DOTS_DATA_PROPERTY,
                        }
                    }
                ]
            }
        },
    },
    "fields": [],
    "sort": {
        "received_on": "asc"
    },
    "size": 1

}

