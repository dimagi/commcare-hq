import "commcarehq";
import $ from "jquery";
import intialPageData from "hqwebapp/js/initial_page_data";
import baseAce from "hqwebapp/js/base_ace";

$(function () {
    var allDatabase = intialPageData.get('all_databases').map(function (database) {
        return {'dbName': database,'dbValue': database};
    });
    allDatabase = [{'dbName': 'All Databases','dbValue': ''}].concat(allDatabase);

    var viewModel = {'allDatabases': allDatabase};
    $("#doc-form").koApplyBindings(viewModel);

    var $element = $("#doc-element"),
        options = {maxLines: Infinity},
        doc = ($element.length ? JSON.stringify($element.data('doc'), null, 4) : null);
    baseAce.initAceEditor($element.get(0), 'ace/mode/json', options, doc);
});
