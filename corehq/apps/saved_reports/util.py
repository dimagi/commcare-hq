from django.http import HttpRequest, QueryDict


def create_mock_request(couch_user, domain, language, query_string, method='GET', bypass_two_factor=True):
    mock_request = HttpRequest()
    mock_request.couch_user = couch_user
    mock_request.user = couch_user.get_django_user()
    mock_request.domain = domain
    mock_request.couch_user.current_domain = domain
    mock_request.couch_user.language = language
    mock_request.method = method
    mock_request.bypass_two_factor = bypass_two_factor

    mock_query_string_parts = [query_string, 'filterSet=true']
    mock_request.GET = QueryDict('&'.join(mock_query_string_parts))

    return mock_request
