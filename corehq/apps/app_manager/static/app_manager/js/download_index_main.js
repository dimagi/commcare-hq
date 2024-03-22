"use strict";
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
            var multimediaSizesContainer = multimediaSizeUtil.multimediaSizesContainer(initialPageData.get('build_profiles'));
            $("#build-profile-select-for-multimedia").koApplyBindings(multimediaSizesContainer);
            var multimediaSizes = multimediaSizeUtil.multimediaSizeView(initialPageData.get('app_id'));
            $("#multimedia-sizes-container").koApplyBindings(multimediaSizes);
            multimediaSizesContainer.views = [multimediaSizes];
        }
    });
});
