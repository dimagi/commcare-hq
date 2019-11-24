hqDefine('app_manager/js/download_index_main',[
    'jquery',
    'underscore',
    'knockout',
    'hqwebapp/js/base_ace',
    'hqwebapp/js/initial_page_data',
    'app_manager/js/multimedia_size_util',
    'app_manager/js/download_async_modal',
    'app_manager/js/source_files',
], function ($, _, ko, baseAce, initialPageData, multimediaSizeUtil) {
    $(function () {
        var elements = $('.prettyprint');
        _.each(elements, function (elem) {
            var fileName = $(elem).data('filename'),
                mode = fileName.endsWith('json') ? 'ace/mode/json' : 'ace/mode/xml';
            baseAce.initAceEditor(elem, mode, {});
        });
        if ($('#multimedia-sizes-container').length) {
            var appID = initialPageData.get('app_id');
            var multimediaSizes = multimediaSizeUtil.multimediaSizesView(
                initialPageData.reverse("get_multimedia_sizes", appID, 'default'));
            multimediaSizes.load();
            $("#multimedia-sizes-container").koApplyBindings(multimediaSizes);
            if ($('#build-profile-select-for-multimedia').length) {
                $('#build-profile-select-for-multimedia').on('change', function () {
                    var buildProfileId = $(this).val();
                    multimediaSizes.url = initialPageData.reverse("get_multimedia_sizes", appID, buildProfileId);
                    multimediaSizes.load();
                });
            }
        }
    });
});
