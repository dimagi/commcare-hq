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

        var $form = $("#compare-form"),
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
            var multimediaSizesContainer = multimediaSizeUtil.multimediaSizesContainer(initialPageData.get('build_profiles'));
            $("#build-profile-select-for-multimedia").koApplyBindings(multimediaSizesContainer);

            var multimediaSizeApp1 = multimediaSizeUtil.multimediaSizeView(firstAppID);
            $("#multimedia-sizes-container-1").koApplyBindings(multimediaSizeApp1);

            var multimediaSizeApp2 = multimediaSizeUtil.multimediaSizeView(secondAppID);
            $("#multimedia-sizes-container-2").koApplyBindings(multimediaSizeApp2);

            var multimediaSizesDiff = multimediaSizeUtil.multimediaSizeView(firstAppID, secondAppID);
            $("#multimedia-sizes-diff").koApplyBindings(multimediaSizesDiff);

            multimediaSizesContainer.views = [multimediaSizeApp1, multimediaSizeApp2, multimediaSizesDiff];
        }
    });
});
