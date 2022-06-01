import json

from dimagi.utils.logging import notify_exception

from django.db.models import Q
from django.conf import settings

from datetime import datetime

from google.oauth2.credentials import Credentials

from corehq.util.couch import get_document_or_404

from corehq.apps.es.exceptions import ESError
from corehq.apps.export.esaccessors import get_case_export_base_query, get_form_export_base_query
from corehq.apps.oauth_integrations.models import (
    GoogleApiToken,
    LiveGoogleSheetRefreshStatus,
    LiveGoogleSheetSchedule,
    LiveGoogleSheetErrorReason,
)

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.auth.exceptions import MutualTLSChannelError


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


def create_or_update_spreadsheet(export, schedule):
    """
    This interfaces with the Google sheet API to create workbooks based on the export data passed into it.
    If no workbook id is present, then it will create a new workbook, otherwise it will update the workbook
    with the suplied ID.
    :param: spreadsheet_data - Three dimensional list containing export data
    :param: schedule - Instance of LiveGoogleSheetSchedule
    :param: export - Instance of ExportInstance
    """

    try:
        export_data = get_data_for_gsheet_exports(export, export.domain)
    except ESError as e:
        schedule.stop_refresh(
            LiveGoogleSheetErrorReason.OTHER,
            "An Elasticsearch error occured, contact support."
        )
        notify_exception(None, message=str(e))
        return

    data_table = create_table(export_data, export)

    token = GoogleApiToken.objects.get(user__username=schedule.user)
    credentials = load_credentials(token.token)

    try:
        service = build(
            settings.GOOGLE_SHEETS_API_NAME,
            settings.GOOGLE_SHEETS_API_VERSION,
            credentials=credentials
        )
        if not schedule.google_sheet_id:
            spreadsheet_name = export.name
            sheets_file = service.spreadsheets().create(
                body={
                    'properties': {
                        'title': spreadsheet_name
                    }
                }
            ).execute()
            spreadsheet_id = sheets_file['spreadsheetId']

            schedule.google_sheet_id = spreadsheet_id
            schedule.save()
        else:
            spreadsheet_id = schedule.google_sheet_id
            sheets_file = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
            clear_spreadsheet(service, spreadsheet_id)

        add_last_updated_field_to_spreadsheet(service, spreadsheet_id)

        for worksheet_number, worksheet in enumerate(data_table, start=1):
            worksheet_name = f"Sheet{worksheet_number}"

            starting_cell = "A3" if worksheet_number == 1 else "A1"

            if not check_worksheet_exists(sheets_file, worksheet_name):
                create_empty_worksheet(service, worksheet_name, spreadsheet_id)

            value_range_body = {
                'majorDimension': 'ROWS',
                'values': worksheet,
            }

            service.spreadsheets().values().append(
                spreadsheetId=spreadsheet_id,
                valueInputOption='USER_ENTERED',
                body=value_range_body,
                range=f"{worksheet_name}!{starting_cell}"
            ).execute()
    except HttpError as e:
        notify_exception(None, message=str(e))
        #TODO
        schedule.stop_refresh(
            LiveGoogleSheetErrorReason.OTHER,
            "Google Raised an HttpError. Contact support."
        )
        return
    except MutualTLSChannelError as e:
        notify_exception(None, message=str(e))
        #TODO
        schedule.stop_refresh(
            LiveGoogleSheetErrorReason.OTHER,
            "Google Raised an MutualTLSChannelError. Contact support."
        )
        return

    schedule.stop_refresh()
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


def add_last_updated_field_to_spreadsheet(service, spreadsheet_id):
    last_updated = (
        ('Last Updated',),
        (datetime.utcnow().strftime('%d %B %Y - %H:%M:%S'),),
    )

    value_range_body = {
        'majorDimension': 'COLUMNS',
        'values': last_updated
    }

    service.spreadsheets().values().append(
        spreadsheetId=spreadsheet_id,
        valueInputOption='USER_ENTERED',
        body=value_range_body,
        range="A1"
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


def get_data_for_gsheet_exports(export, domain):
    if export.type == "case":
        query = get_case_export_base_query(domain, export.case_type)
    else:
        query = get_form_export_base_query(domain, export.app_id, export.xmlns, include_errors=False)

    for filter in export.get_filters():
        query = query.filter(filter.to_es_filter())

    query = query.run()
    return query.hits


def get_scheduled_refreshes(today=None):
    today = today or datetime.utcnow()

    scheduled_this_hour = LiveGoogleSheetSchedule.objects.filter(
        start_time=today.hour,
        is_active=True
    )

    scheduled_refreshes = []
    for schedule in scheduled_this_hour:
        if not LiveGoogleSheetRefreshStatus.objects.filter(
            schedule=schedule
        ).exists():
            scheduled_refreshes.append(schedule)
        elif not LiveGoogleSheetRefreshStatus.objects.filter(
            schedule=schedule
        ).filter(
            Q(
                date_end__year=today.year,
                date_end__month=today.month,
                date_end__day=today.day,
                date_end__hour=today.hour
            ) | Q(date_end=None)
        ).exists():
            scheduled_refreshes.append(schedule)

    return scheduled_refreshes
