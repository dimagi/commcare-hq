/* globals Exports
 *
 * Some of these constants need correspond to constants set in corehq/apps/exports/const.py
 * so if changing a value, ensure that both places reflect the change
 */
Exports.Constants.TAG_DELETED = 'deleted';
Exports.Constants.MULTISELECT_SPLIT_TYPE = 'multi-select';
Exports.Constants.PLAIN_SPLIT_TYPE = 'plain';
Exports.Constants.USER_DEFINED_SPLIT_TYPES = [
    Exports.Constants.PLAIN_SPLIT_TYPE,
    Exports.Constants.MULTISELECT_SPLIT_TYPE,
];
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

// These must match the constants in corehq/apps/export/models/new.py
Exports.Constants.MAIN_TABLE = [];
Exports.Constants.CASE_HISTORY_TABLE = [{'name': 'actions', 'is_repeat': true, 'doc_type': 'PathNode'}];
Exports.Constants.PARENT_CASE_TABLE = [{'name': 'indices', 'is_repeat': true, 'doc_type': 'PathNode'}];
