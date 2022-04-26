import json

from django.conf import settings

from datetime import datetime

from google.oauth2.credentials import Credentials

from corehq.apps.export.esaccessors import get_case_export_base_query, get_form_export_base_query
from corehq.apps.oauth_integrations.models import GoogleApiToken, LiveGoogleSheetSchedule

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


def create_or_update_spreadsheet(spreadsheet_data, user, export_instance, spreadsheet_id=None):
    token = GoogleApiToken.objects.get(user=user)
    credentials = load_credentials(token.token)

    service = build(settings.GOOGLE_SHEETS_API_NAME, settings.GOOGLE_SHEETS_API_VERSION, credentials=credentials)
    if spreadsheet_id is None:
        spreadsheet_name = export_instance.name
        sheets_file = service.spreadsheets().create(
            body={
                'properties': {
                    'title': spreadsheet_name
                }
            }
        ).execute()
        spreadsheet_id = sheets_file['spreadsheetId']
    else:
        sheets_file = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
        clear_spreadsheet(service, spreadsheet_id)

    for worksheet_number, worksheet in enumerate(spreadsheet_data, start=1):
        worksheet_name = f"Sheet{worksheet_number}"

        if not check_worksheet_exists(sheets_file, worksheet_name):
            create_empty_worksheet(service, worksheet_name, spreadsheet_id)

        for chunk in worksheet:
            value_range_body = {
                'majorDimension': 'ROWS',
                'values': chunk
            }
            service.spreadsheets().values().append(
                spreadsheetId=spreadsheet_id,
                valueInputOption='USER_ENTERED',
                body=value_range_body,
                range=f"{worksheet_name}!A1"
            ).execute()

    return sheets_file


def clear_spreadsheet(service, spreadsheet_id):
    service.spreadsheets().values().clear(
        spreadsheetId=spreadsheet_id,
        range='A1'
    ).execute()


def create_empty_worksheet(service, worksheet_name, spreadsheet_id):
    request_body = {
        'requests': [{
            'addSheet': {
                'properties': {
                    'title': worksheet_name
                }
            }
        }]
    }

    return service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body=request_body
    ).execute()


def check_worksheet_exists(sheets_file, worksheet_name):
    for worksheet in sheets_file['sheets']:
        if worksheet_name == worksheet['properties']['title']:
            return True
    return False


def create_table(documents, config):
    ROW_DICT_INDEX = 0
    list_of_tables = []
    for table_obj in config.tables:
        table_list = []
        for row_number, document in enumerate(documents):
            row_dict = table_obj.get_rows(
                document,
                document.get('_id'),
                split_columns=config.split_multiselects,
                transform_dates=config.transform_dates,
                as_json=True,
            )
            if(row_number == 0):
                table_headers = list(row_dict[ROW_DICT_INDEX].keys())
                table_list.append(table_headers)
            table_values = list(row_dict[ROW_DICT_INDEX].values())
            table_list.append(table_values)
        list_of_tables.append(list(table_list))
    return list_of_tables


def chunkify_data(data, chunk_size):
    return [data[x: x + chunk_size] for x in range(0, len(data), chunk_size)]


def get_export_data(export, domain):
    if export.type == "case":
        query = get_case_export_base_query(domain, export.case_type)
    else:
        query = get_form_export_base_query(domain, export.app_id, export.xmlns, include_errors=False)

    for filter in export.get_filters():
        query = query.filter(filter.to_es_filter())

    query = query.run()
    return query.hits


def get_live_google_sheet_schedule(export_config_id):
    try:
        schedule = LiveGoogleSheetSchedule.objects.get(export_config_id=export_config_id)
        if schedule is not None:
            return schedule
        else:
            return None
    except LiveGoogleSheetSchedule.DoesNotExist:
        return None


def create_live_google_sheet_schedule(export_config_id, spreadsheet_id):
    new_schedule = LiveGoogleSheetSchedule(
        export_config_id=export_config_id,
        google_sheet_id=spreadsheet_id
    )
    new_schedule.save()
    return new_schedule
