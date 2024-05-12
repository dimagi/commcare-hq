/*
 * Some of these constants need correspond to constants set in corehq/apps/exports/const.py
 * so if changing a value, ensure that both places reflect the change
 */

hqDefine('export/js/const', [], function () {
    var TAG_DELETED = 'deleted';
    var MULTISELECT_SPLIT_TYPE = 'multi-select';
    var PLAIN_SPLIT_TYPE = 'plain';
    var USER_DEFINED_SPLIT_TYPES = [
        PLAIN_SPLIT_TYPE,
        MULTISELECT_SPLIT_TYPE,
    ];
    var SAVE_STATES = {
        SAVING: 'saving',
        ERROR: 'error',
        READY: 'ready',
        SUCCESS: 'done',
    };
    var EXPORT_FORMATS = {
        HTML: 'html',
        CSV: 'csv',
        XLS: 'xls',
        XLSX: 'xlsx',
        GEOJSON: 'geojson',
    };
    var SHARING_OPTIONS = {
        PRIVATE: 'private',
        EXPORT_ONLY: 'export_only',
        EDIT_AND_EXPORT: 'edit_and_export',
    };
    var DEID_OPTIONS = {
        NONE: null,
        ID: 'deid_id',
        DATE: 'deid_date',
    };
    var ANALYTICS_EVENT_CATEGORIES = {
        'form': 'Form Exports',
        'case': 'Case Exports',
    };
    var FORM_EXPORT = 'form';
    var CASE_EXPORT = 'case';

    // These must match the constants in corehq/apps/export/models/new.py
    var MAIN_TABLE = [];
    var CASE_HISTORY_TABLE = [{'name': 'actions', 'is_repeat': true, 'doc_type': 'PathNode'}];
    var PARENT_CASE_TABLE = [{'name': 'indices', 'is_repeat': true, 'doc_type': 'PathNode'}];
    var ALL_CASE_TYPE_TABLE = {'name': 'commcare-all-case-types', is_repeat: false, 'doc_type': 'PathNode'};

    return {
        TAG_DELETED: TAG_DELETED,
        MULTISELECT_SPLIT_TYPE: MULTISELECT_SPLIT_TYPE,
        PLAIN_SPLIT_TYPE: PLAIN_SPLIT_TYPE,
        USER_DEFINED_SPLIT_TYPES: USER_DEFINED_SPLIT_TYPES,
        SAVE_STATES: SAVE_STATES,
        EXPORT_FORMATS: EXPORT_FORMATS,
        SHARING_OPTIONS: SHARING_OPTIONS,
        DEID_OPTIONS: DEID_OPTIONS,
        ANALYTICS_EVENT_CATEGORIES: ANALYTICS_EVENT_CATEGORIES,
        FORM_EXPORT: FORM_EXPORT,
        CASE_EXPORT: CASE_EXPORT,
        MAIN_TABLE: MAIN_TABLE,
        CASE_HISTORY_TABLE: CASE_HISTORY_TABLE,
        PARENT_CASE_TABLE: PARENT_CASE_TABLE,
        ALL_CASE_TYPE_TABLE: ALL_CASE_TYPE_TABLE,
    };
});
