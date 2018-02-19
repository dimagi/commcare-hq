hqDefine("app_manager/js/settings/app_logos", function() {
    var self = {};
    var HQMediaUploaders = hqImport("hqmedia/js/hqmediauploaders").get(),
        initial_page_data = hqImport("hqwebapp/js/initial_page_data").get;
    var refs = initial_page_data('media_refs');
    var media_info = initial_page_data('media_info');

    var image_refs = {};
    for (var slug in refs) {
        image_refs[slug] = new ImageReference(refs[slug]);
        image_refs[slug].upload_controller = HQMediaUploaders[slug];
        image_refs[slug].setObjReference(media_info[slug]);
    }

    self.urlFromLogo = function(slug) {
        return image_refs[slug].url;
    };

    self.thumbUrlFromLogo = function(slug) {
        return image_refs[slug].thumb_url;
    };

    self.triggerUploadForLogo = function(slug) {
        if (image_refs[slug]) {
            image_refs[slug].triggerUpload();
        }
    };

    self.uploadCompleteForLogo = function(slug, response) {
        if (image_refs[slug]) {
            image_refs[slug].uploadComplete(null, null, response);
        }
    };

    self.getPathFromSlug = function(slug) {
        return image_refs[slug].path;
    };

    self.removeLogo = function(slug) {
        $.post(
            hqImport("hqwebapp/js/initial_page_data").reverse("hqmedia_remove_logo"),
            {
                logo_slug: slug
            },
            function(data, status) {
                if (status === 'success') {
                    image_refs[slug].url("");
                }
            }
        );
    };

    return {
        LogoManager: self,
    };
});
