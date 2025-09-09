import $ from "jquery";
import initialPageData from "hqwebapp/js/initial_page_data";

$(function () {
    if (initialPageData.get('read_only_mode')) {
        $('.main-form :input').prop('disabled', true);
    }
});
