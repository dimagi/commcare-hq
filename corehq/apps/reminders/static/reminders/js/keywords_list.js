hqDefine('reminders/js/keywords_list', [
    "jquery",
    "hqwebapp/js/multiselect_utils",
    "hqwebapp/js/crud_paginated_list_init", // needed to initialize the page
], function ($, multiselectUtils) {
    $(function () {
        multiselectUtils.createFullMultiselectWidget(
            'keyword-selector',
            gettext("Keywords"),
            gettext("Keywords to copy"),
            gettext("Search keywords")
        );
        multiselectUtils.createFullMultiselectWidget(
            'domain-selector',
            gettext("Linked Project Spaces"),
            gettext("Projects to copy to"),
            gettext("Search projects")
        );

    });
});
