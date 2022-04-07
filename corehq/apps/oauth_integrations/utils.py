import json

from django.conf import settings

from datetime import datetime

from google.oauth2.credentials import Credentials

from corehq.util.couch import get_document_or_404

from corehq.apps.export.esaccessors import get_case_export_base_query, get_form_export_base_query
from corehq.apps.oauth_integrations.models import GoogleApiToken

from googleapiclient.discovery import build


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


def get_token(user):
    try:
        return GoogleApiToken.objects.get(user=user)
    except GoogleApiToken.DoesNotExist:
        return None


def get_query_results(export_instance, domain, id):
    export = get_document_or_404(export_instance, domain, id)
    query = get_case_export_base_query(domain, export.case_type)
    results = query.run()
    return results


def create_spreadsheet(spreadsheet_data, user):
    token = GoogleApiToken.objects.get(user=user)
    credentials = load_credentials(token.token)

    service = build(settings.GOOGLE_SHEETS_API_NAME, settings.GOOGLE_SHEETS_API_VERSION, credentials=credentials)
    sheets_file = service.spreadsheets().create().execute()
    spreadsheet_id = sheets_file['spreadsheetId']

    for chunk in spreadsheet_data:
        value_range_body = {
            'majorDimension': 'ROWS',
            'values': chunk
        }
        service.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id,
            valueInputOption='USER_ENTERED',
            body=value_range_body,
            range='A1'
        ).execute()

    return sheets_file


def listify_data(query_results):
    data = []
    for row_number, document in enumerate(query_results):
        row_values = document.get("case_json")

        if(row_number == 0):
            headers = list(row_values.keys())
            data.append(headers)
        data.append(list(row_values.values()))

    return data


def get_export_data(export, domain):
    if export.type == "case":
        query = get_case_export_base_query(domain, export.case_type)
    else:
        query = get_form_export_base_query(domain, export.app_id, export.xlmns, include_errors=False)

    for filter in export.get_filters():
        query = query.filter(filter.to_es_filter())

    return query.run()
