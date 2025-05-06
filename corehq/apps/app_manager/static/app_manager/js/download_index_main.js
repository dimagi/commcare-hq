import "commcarehq";
import $ from "jquery";
import _ from "underscore";
import baseAce from "hqwebapp/js/base_ace";
import initialPageData from "hqwebapp/js/initial_page_data";
import multimediaSizeUtil from "app_manager/js/multimedia_size_util";
import "app_manager/js/download_async_modal";
import "app_manager/js/source_files";

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
