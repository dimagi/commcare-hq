hqDefine('hqadmin/js/raw_doc', [
    'jquery',
    'hqwebapp/js/initial_page_data',
    "hqwebapp/js/base_ace",
], function ($, intialPageData, baseAce) {
    $(function () {
        var allDatabase = intialPageData.get('all_databases').map(function (database) {
            return {'dbName': database,'dbValue': database};
        });
        allDatabase = [{'dbName': 'All Databases','dbValue': ''}].concat(allDatabase);

        var viewModel = {'allDatabases': allDatabase};
        $("#doc-form").koApplyBindings(viewModel);

        var $element = $("#doc-element"),
            doc = ($element.length ? JSON.stringify($element.data('doc'), null, 4) : null);
        baseAce.initAceEditor($element.get(0), 'ace/mode/json', {}, doc);
    });
});
