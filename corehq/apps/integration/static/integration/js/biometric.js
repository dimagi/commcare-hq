import "commcarehq";
import $ from "jquery";
import initialPageData from "hqwebapp/js/initial_page_data";
import simprints from "integration/js/simprints";

$(function () {
    var simprintsModel = simprints.simprintsFormModel(initialPageData.get('simprintsFormData'));
    $('#simprints-form').koApplyBindings(simprintsModel);
});
