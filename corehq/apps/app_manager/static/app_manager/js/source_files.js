hqDefine('app_manager/js/source_files', [
    'jquery',
    'underscore',
    'hqwebapp/js/initial_page_data',
    'app_manager/js/widgets',       // version dropdown
], function ($, _, initialPageData) {
    $(function () {
        $('.toggle-next').click(function (e) {
            e.preventDefault();
            $(this).parents('tr').next('tr').toggleClass("hide");
        });

        var currentVersion = initialPageData.get('current_version'),
            $form = $("#compare-form"),
            $select = $form.find("select");

        $form.find("button").click(function () {
            var buildId = $select.val();
            if (!buildId) {
                alert(gettext("Please enter a version to compare"));
                return;
            }
            window.location = initialPageData.reverse('diff', buildId);
        });
    });
});
