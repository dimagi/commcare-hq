from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals

import six.moves.html_parser
import json
from collections import OrderedDict, defaultdict, namedtuple

from couchdbkit import ResourceNotFound
from django.core.exceptions import ObjectDoesNotExist
from django.http import (
    HttpResponseRedirect,
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseNotFound,
    JsonResponse,
    StreamingHttpResponse,
)
from django.shortcuts import render
from django.views import View

from corehq.apps.domain.decorators import (
    require_superuser, require_superuser_or_contractor,
    login_or_basic, domain_admin_required,
    check_lockout)
from corehq.apps.locations.models import SQLLocation
from corehq.apps.hqwebapp.decorators import use_datatables, use_jquery_ui, \
    use_nvd3_v3
from corehq.elastic import ES_META, run_query
from corehq.form_processor.exceptions import XFormNotFound, CaseNotFound
from corehq.form_processor.models import XFormInstanceSQL, CommCareCaseSQL
from corehq.form_processor.serializers import XFormInstanceSQLRawDocSerializer, \
    CommCareCaseSQLRawDocSerializer
from corehq.util import reverse
from corehq.util.couchdb_management import couch_config
from corehq.util.supervisord.api import (
    PillowtopSupervisorApi,
    SupervisorException,
    all_pillows_supervisor_status,
    pillow_supervisor_status
)
from corehq.apps.hqadmin.forms import (
    AuthenticateAsForm, EmailForm, SuperuserManagementForm,
    ReprocessMessagingCaseUpdatesForm,
    DisableTwoFactorForm, DisableUserForm)
import six


class _Db(object):
    """
    Light wrapper for providing interface like Couchdbkit's Database objects.
    """

    def __init__(self, dbname, getter, doc_type):
        self.dbname = dbname
        self._getter = getter
        self.doc_type = doc_type

    def get(self, record_id):
        try:
            return self._getter(record_id)
        except (XFormNotFound, CaseNotFound, ObjectDoesNotExist):
            raise ResourceNotFound("missing")


_SQL_DBS = OrderedDict((db.dbname, db) for db in [
    _Db(
        XFormInstanceSQL._meta.db_table,
        lambda id_: XFormInstanceSQLRawDocSerializer(XFormInstanceSQL.get_obj_by_id(id_)).data,
        XFormInstanceSQL.__name__
    ),
    _Db(
        CommCareCaseSQL._meta.db_table,
        lambda id_: CommCareCaseSQLRawDocSerializer(CommCareCaseSQL.get_obj_by_id(id_)).data,
        CommCareCaseSQL.__name__
    ),
    _Db(
        SQLLocation._meta.db_table,
        lambda id_: SQLLocation.objects.get(location_id=id_).to_json(),
        SQLLocation.__name__
    ),
])


def get_db_from_db_name(db_name):
    if db_name in _SQL_DBS:
        return _SQL_DBS[db_name]
    elif db_name == couch_config.get_db(None).dbname:  # primary db
        return couch_config.get_db(None)
    else:
        return couch_config.get_db(db_name)


def _lookup_id_in_database(doc_id, db_name=None):
    db_result = namedtuple('db_result', 'dbname result status')
    STATUSES = defaultdict(lambda: 'warning', {
        'missing': 'default',
        'deleted': 'danger',
    })

    response = {"doc_id": doc_id}
    if db_name:
        dbs = [get_db_from_db_name(db_name)]
        response['selected_db'] = db_name
    else:
        couch_dbs = list(couch_config.all_dbs_by_slug.values())
        sql_dbs = list(_SQL_DBS.values())
        dbs = couch_dbs + sql_dbs

    db_results = []
    for db in dbs:
        try:
            doc = db.get(doc_id)
        except ResourceNotFound as e:
            db_results.append(db_result(db.dbname, six.text_type(e), STATUSES[six.text_type(e)]))
        else:
            db_results.append(db_result(db.dbname, 'found', 'success'))
            response.update({
                "doc": json.dumps(doc, indent=4, sort_keys=True),
                "doc_type": doc.get('doc_type', getattr(db, 'doc_type', 'Unknown')),
                "dbname": db.dbname,
            })

    response['db_results'] = db_results
    return response


@require_superuser
def doc_in_es(request):
    doc_id = request.GET.get("id")
    if not doc_id:
        return render(request, "hqadmin/doc_in_es.html", {})

    def to_json(doc):
        return json.dumps(doc, indent=4, sort_keys=True) if doc else "NOT FOUND!"

    query = {"filter": {"ids": {"values": [doc_id]}}}
    found_indices = {}
    es_doc_type = None
    for index in ES_META:
        res = run_query(index, query)
        if 'hits' in res and res['hits']['total'] == 1:
            es_doc = res['hits']['hits'][0]['_source']
            found_indices[index] = to_json(es_doc)
            es_doc_type = es_doc_type or es_doc.get('doc_type')

    context = {
        "doc_id": doc_id,
        "es_info": {
            "status": "found" if found_indices else "NOT FOUND IN ELASTICSEARCH!",
            "doc_type": es_doc_type,
            "found_indices": found_indices,
        },
        "couch_info": _lookup_id_in_database(doc_id),
    }
    return render(request, "hqadmin/doc_in_es.html", context)


@require_superuser
def raw_couch(request):
    get_params = dict(six.iteritems(request.GET))
    return HttpResponseRedirect(reverse("raw_doc", params=get_params))


@require_superuser
def raw_doc(request):
    doc_id = request.GET.get("id")
    db_name = request.GET.get("db_name", None)
    if db_name and "__" in db_name:
        db_name = db_name.split("__")[-1]
    context = _lookup_id_in_database(doc_id, db_name) if doc_id else {}

    if request.GET.get("raw", False):
        if 'doc' in context:
            return HttpResponse(context['doc'], content_type="application/json")
        else:
            return HttpResponse(json.dumps({"status": "missing"}),
                                content_type="application/json", status=404)

    other_couch_dbs = sorted([_f for _f in couch_config.all_dbs_by_slug if _f])
    context['all_databases'] = ['commcarehq'] + other_couch_dbs + list(_SQL_DBS)
    return render(request, "hqadmin/raw_couch.html", context)


class Webconnector(View):
    urlname = 'webconnector'

    def get(self, request):
        return HttpResponse(
            '''
            <html>
            
            <head>
                <title>USGS Earthquake Feed</title>
                <meta http-equiv="Cache-Control" content="no-store" />
            
                <link href="https://maxcdn.bootstrapcdn.com/bootstrap/3.3.6/css/bootstrap.min.css" rel="stylesheet" crossorigin="anonymous">
                <script src="https://ajax.googleapis.com/ajax/libs/jquery/1.11.1/jquery.min.js" type="text/javascript"></script>
                <script src="https://maxcdn.bootstrapcdn.com/bootstrap/3.3.6/js/bootstrap.min.js" crossorigin="anonymous"></script>
            
                <script src="https://connectors.tableau.com/libs/tableauwdc-2.3.latest.js" type="text/javascript"></script>
                <script src="http://localhost:8000/hq/admin/earthquakeWDC.js" type="text/javascript"></script>
            </head>
            
            <body>
                <div class="container container-table">
                    <div class="row vertical-center-row">
                        <div class="text-center col-md-4 col-md-offset-4">
                            <button type="button" id="submitButton" class="btn btn-success" style="margin: 10px;">Get Earthquake Data!</button>
                        </div>
                    </div>
                </div>
            </body>
            
            </html>
            '''
        )


class WebconnectorJS(View):
    urlname = 'webconnectorjs'

    def get(self, request):
        return HttpResponse(
            '''
            (function() {
                // Create the connector object
                var myConnector = tableau.makeConnector();
            
                // Define the schema
                myConnector.getSchema = function(schemaCallback) {
                    var cols = [{
                        id: "id",
                        dataType: tableau.dataTypeEnum.string
                    }, {
                        id: "mag",
                        alias: "magnitude",
                        dataType: tableau.dataTypeEnum.float
                    }, {
                        id: "title",
                        alias: "title",
                        dataType: tableau.dataTypeEnum.string
                    }, {
                        id: "location",
                        dataType: tableau.dataTypeEnum.geometry
                    }];
            
                    var tableSchema = {
                        id: "earthquakeFeed",
                        alias: "Earthquakes with magnitude greater than 4.5 in the last seven days",
                        columns: cols
                    };
            
                    schemaCallback([tableSchema]);
                };
            
                // Download the data
                myConnector.getData = function(table, doneCallback) {
                    $.getJSON("http://localhost:8000/hq/admin/4.5_week.geojson", function(resp) {
                        var feat = resp.features,
                            tableData = [];
            
                        // Iterate over the JSON object
                        for (var i = 0, len = feat.length; i < len; i++) {
                            tableData.push({
                                "id": feat[i].id,
                                "mag": feat[i].properties.mag,
                                "title": feat[i].properties.title,
                                "location": feat[i].geometry
                            });
                        }
            
                        table.appendRows(tableData);
                        doneCallback();
                    });
                };
            
                tableau.registerConnector(myConnector);
            
                // Create event listeners for when the user submits the form
                $(document).ready(function() {
                    $("#submitButton").click(function() {
                        tableau.connectionName = "USGS Earthquake Feed"; // This will be the data source name in Tableau
                        tableau.submit(); // This sends the connector object to Tableau
                    });
                });
            })();
            '''
        )


class GeoJson(View):
    urlname = 'geojson'

    def get(self, request):
        return JsonResponse({
          "features": [
            {
              "type": "Feature",
              "properties": {
                "mag": 6.7,
                "place": "245km SE of Lambasa, Fiji",
                "time": 1542572745970,
                "updated": 1542574666040,
                "tz": -720,
                "url": "https://earthquake.usgs.gov/earthquakes/eventpage/us1000htm5",
                "detail": "https://earthquake.usgs.gov/earthquakes/feed/v1.0/detail/us1000htm5.geojson",
                "felt": None,
                "cdi": None,
                "mmi": 2.96,
                "alert": "green",
                "status": "reviewed",
                "tsunami": 1,
                "sig": 691,
                "net": "us",
                "code": "1000htm5",
                "ids": ",pt18322000,at00pieoqx,us1000htm5,",
                "sources": ",pt,at,us,",
                "types": ",geoserve,impact-link,losspager,moment-tensor,origin,phase-data,shakemap,",
                "nst": None,
                "dmin": 2.906,
                "rms": 1.02,
                "gap": 72,
                "magType": "mww",
                "type": "earthquake",
                "title": "M 6.7 - 245km SE of Lambasa, Fiji"
              },
              "geometry": {
                "type": "Point",
                "coordinates": [
                  -178.9,
                  -17.8972,
                  533.6
                ]
              },
              "id": "us1000htm5"
            },
          ],
        })
