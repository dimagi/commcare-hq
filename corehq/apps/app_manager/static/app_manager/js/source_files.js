hqDefine('app_manager/js/source_files', [
    'jquery',
    'underscore',
    'knockout',
    'hqwebapp/js/initial_page_data',
    'app_manager/js/multimedia_size_util',
    'app_manager/js/widgets',       // version dropdown
], function ($, _, ko, initialPageData, multimediaSizeUtil) {
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
        if ($('#multimedia-sizes-diff-container').length) {
            var firstAppID = initialPageData.get('first_app_id');
            var secondAppID = initialPageData.get('second_app_id');
            var multimediaSizes1 = multimediaSizeUtil.multimediaSizesView(
                initialPageData.reverse("get_multimedia_sizes", firstAppID));
            multimediaSizes1.load();
            $("#multimedia-sizes-container-1").koApplyBindings(multimediaSizes1);
            var multimediaSizes2 = multimediaSizeUtil.multimediaSizesView(
                initialPageData.reverse("get_multimedia_sizes", secondAppID));
            multimediaSizes2.load();
            $("#multimedia-sizes-container-2").koApplyBindings(multimediaSizes2);
            var multimediaSizesDiff = multimediaSizeUtil.multimediaSizesView(
                initialPageData.reverse("compare_multimedia_sizes"));
            multimediaSizesDiff.load();
            $("#multimedia-sizes-diff").koApplyBindings(multimediaSizesDiff);
        }
    });
});
