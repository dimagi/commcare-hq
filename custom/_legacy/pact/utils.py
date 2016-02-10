from corehq.apps.api.es import ReportCaseES
from pact.enums import PACT_DOTS_DATA_PROPERTY, PACT_DOMAIN
from StringIO import StringIO
from django.test.client import RequestFactory
from corehq.apps.receiverwrapper import views as rcv_views


def submit_xform(url_path, domain, submission_xml_string, extra_meta=None):
    """
    RequestFactory submitter
    """
    rf = RequestFactory()
    f = StringIO(submission_xml_string.encode('utf-8'))
    f.name = 'form.xml'

    req = rf.post(url_path, data={'xml_submission_file': f}) #, content_type='multipart/form-data')
    if extra_meta:
        req.META.update(extra_meta)
    return rcv_views.post(req, domain)


def pact_script_fields():
    """
    This is a hack of the query to allow for the encounter date and pact_ids to show up as first class properties
    """
    return {
        "script_pact_id": {
            "script": """if(_source['form']['note'] != null) { _source['form']['note']['pact_id']['#value']; }
                      else if (_source['form']['pact_id'] != null) { _source['form']['pact_id']['#value']; }
                      else {
                          null;
                      }
                      """
        },
        "script_encounter_date": {
            "script": """if(_source['form']['note'] != null) { _source['form']['note']['encounter_date']['#value']; }
        else if (_source['form']['encounter_date'] != null) { _source['form']['encounter_date']['#value']; }
        else {
            _source['received_on'];
        }
        """
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
        query['facets']['case_submissions']['facet_filter']['and'].append(
            {"term": {"form.meta.username": username}})
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
    case_es = ReportCaseES(PACT_DOMAIN)
    query = {
        "fields": [
            "_id",
            "name",
        ],
        "script_fields": {
            "case_id": {
                "script": "_source._id"
            },
            "pactid": get_report_script_field("pactid"),
            "first_name": get_report_script_field("first_name"),
            "last_name": get_report_script_field("last_name"),
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
                    }
                }
            ]
        },
        "size": len(case_ids)
    }
    res = case_es.run_query(query)

    from pact.reports.patient import PactPatientInfoReport

    ret = {}
    for entry in res['hits']['hits']:
        case_id = entry['fields']['case_id']
        ret[case_id] = entry['fields']
        ret[case_id]['url'] = PactPatientInfoReport.get_url(*['pact']) + "?patient_id=%s" % case_id

    return ret


REPORT_XFORM_MISSING_DOTS_QUERY = {
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
                            "field": "%s.processed.#type" % PACT_DOTS_DATA_PROPERTY,
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


def get_report_script_field(field_path, is_known=False):
    """
    Generate a script field string for easier querying.
    field_path: is the path.to.property.name in the _source
    is_known: if true, then query as is, if false, then it's a dynamically mapped item,
    so put on the #value property at the end.
    """
    property_split = field_path.split('.')
    property_path = '_source%s' % ''.join("['%s']" % x for x in property_split)
    if is_known:
        script_string = property_path
    else:
        full_script_path = "%s['#value']" % property_path
        script_string = """if (%(prop_path)s != null) { %(value_path)s; }
        else { null; }""" % {
            'prop_path': property_path,
            'value_path': full_script_path
        }

    ret = {"script": script_string}
    return ret
