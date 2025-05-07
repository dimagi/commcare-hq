import "commcarehq";
import $ from "jquery";
import "hqwebapp/js/bulk_upload_file";

// Most bulk upload pages use .disable-on-submit and reload the page on submit.
// This one downloads an excel file, so the page doesn't get reloaded.
$(function () {
    $(".disable-on-submit").removeClass("disable-on-submit");
});
