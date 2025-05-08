import "commcarehq";
import $ from "jquery";
import dataModel from "userreports/js/data_source_select_model";

$(function () {
    $("#data-source-config").koApplyBindings(dataModel);
});
