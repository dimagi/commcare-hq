hqDefine("dhis2/js/dataset_map_create", [
    "jquery",
    "hqwebapp/js/widgets",
    'jquery-ui/ui/widgets/datepicker',
], function ($) {
    $('.date-picker').datepicker({ dateFormat: "yy-mm-dd" });
});
