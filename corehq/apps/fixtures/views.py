import json
import logging
from corehq.apps.domain.decorators import login_and_domain_required
from corehq.apps.fixtures.models import FixtureDataType, FixtureDataItem
from dimagi.utils.web import json_response, render_to_response
from django.http import HttpResponse, HttpResponseBadRequest

def strip_json(obj, disallow_basic=None, disallow=None):
    disallow = disallow or []
    if disallow_basic is None:
        disallow_basic = ['_rev', 'domain', 'doc_type']
    disallow += disallow_basic
    ret = {}
    try:
        obj = obj.to_json()
    except Exception:
        pass
    for key in obj:
        if key not in disallow:
            ret[key] = obj[key]

    return ret

@login_and_domain_required
def data_types(request, domain, data_type_id):
    if request.method == 'POST' and data_type_id is None:
        o = FixtureDataType(domain=domain, **json.load(request))
        o.save()
        return json_response(strip_json(o))
    elif request.method == 'GET' and data_type_id is None:
        return json_response([strip_json(x) for x in FixtureDataType.by_domain(domain)])
    elif request.method == 'GET' and data_type_id:
        return json_response(strip_json(FixtureDataType.get(data_type_id)))
    elif request.method == 'PUT' and data_type_id:
        original = FixtureDataType.get(data_type_id)
        new = FixtureDataType(domain=domain, **json.load(request))
        for attr in 'tag', 'name', 'fields':
            setattr(original, attr, getattr(new, attr))
        original.save()
        return json_response(strip_json(original))
    else:
        return HttpResponseBadRequest()

@login_and_domain_required
def data_items(request, domain, data_type_id, data_item_id):
    if request.method == 'POST' and data_item_id is None:
        o = FixtureDataItem(domain=domain, data_type_id=data_type_id, **json.load(request))
        o.save()
        return json_response(strip_json(o, disallow=['data_type_id']))
    elif request.method == 'GET' and data_item_id is None:
        return json_response([strip_json(x, disallow=['data_type_id']) for x in FixtureDataItem.by_data_type(domain, data_type_id)])
    elif request.method == 'GET' and data_item_id:
        o = FixtureDataItem.get(data_item_id)
        assert(o.domain == domain and o.data_type.get_id == data_type_id)
        return json_response(strip_json(o, disallow=['data_type_id']))
    elif request.method == 'PUT' and data_type_id:
        original = FixtureDataItem.get(data_item_id)
        new = FixtureDataItem(domain=domain, **json.load(request))
        for attr in 'fields',:
            setattr(original, attr, getattr(new, attr))
        original.save()
        return json_response(strip_json(original, disallow=['data_type_id']))
    elif request.method == 'DELETE' and data_type_id:
        o = FixtureDataItem.get(data_item_id)
        assert(o.domain == domain and o.data_type.get_id == data_type_id)
        o.delete()
        return json_response({})
    else:
        return HttpResponseBadRequest()

@login_and_domain_required
def view(request, domain, template='fixtures/view.html'):
    return render_to_response(request, template, {})