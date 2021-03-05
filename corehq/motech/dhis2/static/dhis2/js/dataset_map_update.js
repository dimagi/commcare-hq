hqDefine("dhis2/js/dataset_map_update", [
    "jquery",
    "hqwebapp/js/crud_paginated_list_init",
    "hqwebapp/js/widgets",
    'jquery-ui/ui/datepicker',
], function ($) {
    $('.date-picker').datepicker({ dateFormat: "yy-mm-dd" });
});
