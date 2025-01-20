hqDefine("app_manager/js/settings/app_logos", [
    "jquery",
    "hqwebapp/js/initial_page_data",
    "hqmedia/js/media_reference_models",
], function (
    $,
    initialPageData,
    mediaReferenceModels,
) {
    let self = {};
    const refs = initialPageData.get('media_refs'),
        mediaInfo = initialPageData.get('media_info');

    var imageRefs = {};
    for (var slug in refs) {
        imageRefs[slug] = mediaReferenceModels.ImageReference(refs[slug], slug);
        imageRefs[slug].setObjReference(mediaInfo[slug]);
    }

    self.urlFromLogo = function (slug) {
        return imageRefs[slug].url;
    };

    self.thumbUrlFromLogo = function (slug) {
        return imageRefs[slug].thumb_url;
    };

    self.triggerUploadForLogo = function (slug) {
        if (imageRefs[slug]) {
            imageRefs[slug].triggerUpload();
        }
    };

    self.uploadCompleteForLogo = function (slug, response) {
        if (imageRefs[slug]) {
            imageRefs[slug].uploadComplete(null, null, response);
        }
    };

    self.getPathFromSlug = function (slug) {
        return imageRefs[slug].path;
    };

    self.removeLogo = function (slug) {
        $.post(
            initialPageData.reverse("hqmedia_remove_logo"),
            {
                logo_slug: slug,
            },
            function (data, status) {
                if (status === 'success') {
                    imageRefs[slug].url("");
                }
            },
        );
    };

    return {
        LogoManager: self,
    };
});
