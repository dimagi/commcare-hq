import json

from testil import eq

from django.views import View
from django.test.client import RequestFactory

from ..jqueryrmi import JSONResponseException, JSONResponseMixin, allow_remote_invocation


def test_get():
    response = get_response("rmi_endpoint")
    eq(response.status_code, 200)
    eq(response['Cache-Control'], 'no-cache')
    eq(json.loads(response.content), {"data": None})


def test_data_not_passed_to_get():
    response = get_response("rmi_endpoint", {"some": "data"})
    eq(response.status_code, 200)
    eq(response['Cache-Control'], 'no-cache')
    eq(json.loads(response.content), {"data": None})


def test_non_ajax_get():
    response = get_response("rmi_endpoint", HTTP_X_REQUESTED_WITH="not ajax")
    eq(response.status_code, 405)
    eq(response.content, b'This view can not handle method GET')


def test_non_rmi_get():
    response = get_response(None)
    eq(response.status_code, 405)
    eq(response.content, b'This view can not handle method GET')


def test_non_callable_get():
    response = get_response("not_callable")
    eq(response.status_code, 405)
    eq(response.content, b'This view can not handle method GET')


def test_private_method_get():
    response = get_response("private_method")
    eq(response.status_code, 403)
    eq(response.content, b"Method 'RmiView.private_method' has no decorator '@allow_remote_invocation'")


def test_error_get():
    response = get_response("err_endpoint")
    eq(response.status_code, 400)
    eq(response['Cache-Control'], 'no-cache')
    eq(json.loads(response.content), {"message": "something went wrong"})


def test_post():
    response = post_response("rmi_endpoint", {"some": "data"})
    eq(response.status_code, 200)
    eq(response['Cache-Control'], 'no-cache')
    eq(json.loads(response.content), {"data": {"some": "data"}})


def test_post_with_no_data():
    response = post_response("rmi_endpoint")
    eq(response.status_code, 200)
    eq(response['Cache-Control'], 'no-cache')
    eq(json.loads(response.content), {"data": None})


def test_post_with_non_json_data():
    response = post_response("rmi_endpoint", "not json", content_type="text/plain")
    eq(response.status_code, 200)
    eq(response['Cache-Control'], 'no-cache')
    eq(json.loads(response.content), {"data": "not json"})


def test_non_ajax_post():
    response = post_response("rmi_endpoint", HTTP_X_REQUESTED_WITH="not ajax")
    eq(response.status_code, 405)
    eq(response.content, b'This view can not handle method POST')


def test_non_rmi_post():
    response = post_response(None)
    eq(response.status_code, 405)
    eq(response.content, b'This view can not handle method POST')


def test_non_callable_post():
    response = post_response("not_callable")
    eq(response.status_code, 405)
    eq(response.content, b'This view can not handle method POST')


def test_private_method_post():
    response = post_response("private_method")
    eq(response.status_code, 403)
    eq(response.content, b"Method 'RmiView.private_method' has no decorator '@allow_remote_invocation'")


def test_error_post():
    response = post_response("err_endpoint")
    eq(response.status_code, 400)
    eq(response['Cache-Control'], 'no-cache')
    eq(json.loads(response.content), {"message": "something went wrong"})


def test_put():
    response = make_response("put", "rmi_endpoint", {}, {})
    eq(response.status_code, 405)
    eq(response.content, b'')


def test_delete():
    response = make_response("delete", "rmi_endpoint", {}, {})
    eq(response.status_code, 405)
    eq(response.content, b'')


class RmiView(JSONResponseMixin, View):

    not_callable = "value"

    @allow_remote_invocation
    def rmi_endpoint(self, data=None):
        return {"data": data}

    @allow_remote_invocation
    def err_endpoint(self, data=None):
        raise JSONResponseException("something went wrong")

    def private_method(self, *args, **kw):
        raise Exception("should not be called")


def get_response(method, data=None, **extra):
    return make_response("get", method, data, extra)


def post_response(method, data=None, **extra):
    if "content_type" not in extra:
        data = json.dumps(data)
        extra["content_type"] = "application/json"
    return make_response("post", method, data, extra)


def make_response(http_method, method, data, extra):
    assert "HTTP_DJNG_REMOTE_METHOD" not in extra, "use 'method' arg"
    if method is not None:
        extra["HTTP_DJNG_REMOTE_METHOD"] = method
    extra.setdefault("HTTP_X_REQUESTED_WITH", "XMLHttpRequest")
    factory = RequestFactory()
    make_request = getattr(factory, http_method)
    request = make_request('/', data, **extra)
    view = RmiView.as_view()
    return view(request)
