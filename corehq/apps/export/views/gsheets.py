import json

from datetime import datetime

from django.http import HttpResponseRedirect
from django.http.response import JsonResponse
from django.urls import reverse
from corehq.apps.export.esaccessors import get_case_export_base_query

from corehq.apps.export.models.gsuite import GoogleApiToken
from corehq.apps.export.exceptions import InvalidLoginException
from corehq.blobs.util import _utcnow

from corehq.util.couch import get_document_or_404

from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

from corehq.apps.export.models.new import CaseExportInstance


def stringify_credentials(credentials):
    credentials_dict = {
        'token': credentials.token,
        'refresh_token': credentials.refresh_token,
        'id_token': credentials.id_token,
        'token_uri': credentials.token_uri,
        'client_id': credentials.client_id,
        'client_secret': credentials.client_secret,
        'scopes': credentials.scopes,
        'expiry': datetime.strftime(credentials.expiry, '%Y-%m-%d %H:%M:%S')
    }
    return json.dumps(credentials_dict)


def load_credentials(stringified_credentials):
    credentials_dict = json.loads(stringified_credentials)
    credentials = Credentials(
        credentials_dict['token'],
        refresh_token=credentials_dict['refresh_token'],
        id_token=credentials_dict['id_token'],
        token_uri=credentials_dict['token_uri'],
        client_id=credentials_dict['client_id'],
        client_secret=credentials_dict['client_secret'],
        scopes=credentials_dict['scopes'],
    )
    return credentials


def redirect_oauth_view(request, domain):
    config = {"web":
        {"client_id": "699334824903-fsomonub18fa0en5c7t0ao01l0fhduil.apps.googleusercontent.com",
        "project_id": "manifest-ivy-331810",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "auth_provider_x509_cert_url":
        "https://www.googleapis.com/oauth2/v1/certs",
        "client_secret":
        "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"}}
    scopes = ['https://www.googleapis.com/auth/spreadsheets']
    redirect_uri = 'https://staging.commcarehq.org/a/{}/data/export/google_sheets_oauth/callback/'.format(domain)
    INDEX_URL = 0

    try:
        token = GoogleApiToken.objects.get(user=request.user)
    except GoogleApiToken.DoesNotExist:
        token = None

    if token is None:
        flow = Flow.from_client_config(config, scopes, redirect_uri=redirect_uri)
        auth_tuple = flow.authorization_url(prompt='consent')
        return HttpResponseRedirect(auth_tuple[INDEX_URL])
    else:
        return HttpResponseRedirect(reverse('google_sheet_view_redirect', args=[domain]))


def call_back_view(request, domain):
    config = {"web":
        {"client_id": "699334824903-fsomonub18fa0en5c7t0ao01l0fhduil.apps.googleusercontent.com",
        "project_id": "manifest-ivy-331810",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "auth_provider_x509_cert_url":
        "https://www.googleapis.com/oauth2/v1/certs",
        "client_secret":
        "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"}}
    scopes = ['https://www.googleapis.com/auth/spreadsheets']
    redirect_uri = 'https://staging.commcarehq.org/a/{}/data/export/google_sheets_oauth/callback/'.format(domain)

    try:
        state = request.GET.get('state', None)

        if not state:
            raise InvalidLoginException

        flow = Flow.from_client_config(config, scopes, redirect_uri=redirect_uri)
        flow.redirect_uri = redirect_uri

        authorization_response = request.build_absolute_uri()
        flow.fetch_token(authorization_response=authorization_response)
        credentials = flow.credentials
        stringified_token = stringify_credentials(credentials)
        print(len(stringified_token))

        GoogleApiToken.objects.create(
            user=request.user,
            token=stringified_token
        )

    except InvalidLoginException:
        print("Hello There")

    return HttpResponseRedirect(reverse('list_form_exports', args=[domain]))


def google_sheet_view(request, domain):
    view_time_start = _utcnow()
    api_name = 'sheets'
    api_version = 'v4'
    default_limit = 10000
    export_id = request.GET.get('export_id')
    mult = int(request.GET.get('mult'))

    export = get_document_or_404(CaseExportInstance, domain, export_id)
    query = get_case_export_base_query(domain, export.case_type)
    query = query.size(default_limit * mult)
    results = query.run()

    token = GoogleApiToken.objects.get(user=request.user)
    credentials = load_credentials(token.token)

    service = build(api_name, api_version, credentials=credentials)
    sheets_file = service.spreadsheets().create().execute()
    spreadsheet_id = sheets_file['spreadsheetId']

    data = []
    for row_number, document in enumerate(results.hits):
        row_values = document.get("case_json")

        if(row_number == 0):
            headers = list(row_values.keys())
            data.append(headers)
        data.append(list(row_values.values()))

    cell_range_insert = 'A1'
    value_range_body = {
        'majorDimension': 'ROWS',
        'values': data
    }
    upload_time_start = _utcnow()
    service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        valueInputOption='USER_ENTERED',
        body=value_range_body,
        range=cell_range_insert
    ).execute()

    view_runtime = (_utcnow() - view_time_start).total_seconds()
    upload_runtime = (_utcnow() - upload_time_start).total_seconds()

    response = dict(
        link=sheets_file['spreadsheetUrl'],
        view_runtime='{} seconds'.format(view_runtime),
        upload_runtime='{} seconds'.format(upload_runtime)
    )
    return JsonResponse(response)
