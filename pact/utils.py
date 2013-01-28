from corehq.apps.api.es import  CaseES
from pact.enums import PACT_DOTS_DATA_PROPERTY, PACT_DOMAIN
from StringIO import StringIO
from django.test.client import RequestFactory
from corehq.apps.receiverwrapper import views as rcv_views





def submit_xform(url_path, domain, submission_xml_string, extra_meta={}):
    """
    RequestFactory submitter
    """
    rf = RequestFactory()
    f = StringIO(submission_xml_string.encode('utf-8'))
    f.name = 'form.xml'

    req = rf.post(url_path, data = { 'xml_submission_file': f }) #, content_type='multipart/form-data')
    req.META.update(extra_meta)
    return rcv_views.post(req, domain)

def pact_script_fields():
    """
    This is a hack of the query to allow for the encounter date and pact_ids to show up as first class properties
    """
    return {
        "script_pact_id": {
            "script": """if(_source['form']['note'] != null) { _source['form']['note']['pact_id']; }
                      else { _source['form']['pact_id']; }"""
        },
        "script_encounter_date": {
            "script": """if(_source['form']['note'] != null) { _source['form']['note']['encounter_date']; }
        else { _source['form']['encounter_date']; }"""
        }
    }


def case_script_field():
    """
    Hack method to give a single case_id placeholder for viewing results for both old and new style
    """
    return {
        "script_case_id": {
            "script": """
            if(_source['form']['case'] != null) {
              if (_source['form']['case']['@case_id'] != null) {
                _source['form']['case']['@case_id'];
              }
              else { _source['form']['case']['case_id'];
             }
            }"""
        }
    }


def query_per_case_submissions_facet(domain, username=None, limit=100):
    """
    Xform query to get count facet by case_id
    """
    query = {
        "facets": {
            "case_submissions": {
                "terms": {
                    #                    "field": "form.case.case_id",
                    "script_field": case_script_field()['script_case_id']['script'],
                    "size": limit
                },
                "facet_filter": {
                    "and": [
                        {
                            "term": {
                                "domain.exact": domain
                            }
                        }
                    ]
                }
            }
        },
        "size": 0
    }

    if username is not None:
        query['facets']['case_submissions']['facet_filter']['and'].append({ "term": { "form.meta.username": username } })
    return query

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
    if len(case_ids) == 0:
        return {}
    case_es = CaseES(PACT_DOMAIN)
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
        },
        "size": len(case_ids)
    }
    res = case_es.run_query(query)

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

