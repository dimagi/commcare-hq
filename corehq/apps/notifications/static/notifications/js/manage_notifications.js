import "commcarehq";
import $ from "jquery";
import initialPageData from "hqwebapp/js/initial_page_data";

$(function () {
    $('#ko-alert-container').koApplyBindings({
        alerts: initialPageData.get('alerts'),
    });
});
