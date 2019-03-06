hqDefine("translations/js/app_translations", [
    "jquery",
    "hqwebapp/js/initial_page_data",
    "app_manager/js/widgets_v4",
    "hqwebapp/js/widgets_v4",   // .ko-select2
], function (
    $,
    initialPageData,
    appManagerWidgets
) {
    $(function () {
        // Application version select2: pagination, display comment
        $("[name='version']").each(function () {
            var $select = $(this);
            appManagerWidgets.initVersionDropdown($select, {
                url: function () {
                    var $form = $select.closest("form"),
                        appId = $form.find("[name='app_id']").val();
                    return initialPageData.reverse("paginate_releases", appId);
                },
                width: '100%',
            });
        });

        // Clear version when application changes
        $("[name='app_id']").change(function () {
            var $form = $(this).closest("form");
            $form.find("[name='version']").val('').trigger('change');
        });
    });
});
