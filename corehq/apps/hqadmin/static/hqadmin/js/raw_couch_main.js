/* globals ace, hqDefine */
hqDefine('hqadmin/js/raw_couch_main', [
    'jquery',
    'hqwebapp/js/initial_page_data',
    'ace-builds/src-min-noconflict/mode-json',
    'ace-builds/src-min-noconflict/ext-searchbox',
], function ($, intialPageData) {
    $(function() {
        var allDatabase = intialPageData.get('all_databases').map(function(database){
            return {'dbName':database,'dbValue':database};
        });
        allDatabase = [{'dbName':'All Databases','dbValue':''}].concat(allDatabase);

        var viewModel = {'allDatabases': allDatabase};
        $("#doc-form").koApplyBindings(viewModel);
        var $element = $("#couch-document");
        var editor = ace.edit($element.get(0), {
            showPrintMargin: false,
            maxLines: 40,
            minLines: 3,
            fontSize: 14,
            wrap: true,
            useWorker: false,
        });
        editor.session.setMode('ace/mode/json');
        editor.setReadOnly(true);
        editor.session.setValue(JSON.stringify($element.data('doc'), null, 4));
    });
});
