import _ from "underscore";
import initialPageData from "hqwebapp/js/initial_page_data";
import uploadersModule from "hqmedia/js/uploaders";

let uploaders = {};

_.each(initialPageData.get("multimedia_upload_managers"), function (uploader, type) {
    uploaders[type] = uploadersModule.uploader(
        uploader.slug,
        uploader.options,
    );
});

export default {
    audioUploader: uploaders.audio,
    iconUploader: uploaders.icon,
};
