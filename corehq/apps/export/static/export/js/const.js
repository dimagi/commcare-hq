/*
 * Some of these constants need correspond to constants set in corehq/apps/exports/const.py
 * so if changing a value, ensure that both places reflect the change
 */
Exports.Constants.TAG_DELETED = 'deleted';
Exports.Constants.SAVE_STATES = {
    SAVING: 'saving',
    ERROR: 'error',
    READY: 'ready',
    SUCCESS: 'done'
};
Exports.Constants.EXPORT_FORMATS = {
    HTML: 'html',
    CSV: 'csv',
    XLS: 'xls',
    XLSX: 'xlsx'
};
Exports.Constants.DEID_OPTIONS = {
    NONE: null,
    ID: 'deid_id',
    DATE: 'deid_date'
};
Exports.Constants.ANALYTICS_EVENT_CATEGORIES = {
    'form': 'Form Exports',
    'case': 'Case Exports'
};
Exports.Constants.FORM_EXPORT = 'form';
Exports.Constants.CASE_EXPORT = 'case';

Exports.Constants.MAIN_TABLE = null;
Exports.Constants.CASE_HISTORY = ['case_history'];
