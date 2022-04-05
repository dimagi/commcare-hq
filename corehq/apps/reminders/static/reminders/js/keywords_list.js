hqDefine('reminders/js/keywords_list', [
    "jquery",
    "hqwebapp/js/multiselect_utils",
    "hqwebapp/js/crud_paginated_list_init", // needed to initialize the page
], function ($, multiselectUtils) {
    $(function () {
        multiselectUtils.createFullMultiselectWidget('keyword-selector', {
            selectableHeaderTitle: gettext("Keywords"),
            selectedHeaderTitle: gettext("Keywords to copy"),
            searchItemTitle: gettext("Search keywords"),
        });

        multiselectUtils.createFullMultiselectWidget('domain-selector', {
            selectableHeaderTitle: gettext("Linked Project Spaces"),
            selectedHeaderTitle: gettext("Projects to copy to"),
            searchItemTitle: gettext("Search projects"),
        });
    });
});
