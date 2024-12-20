hqDefine("hqmedia/js/media_reference_models", [
    'jquery',
    'knockout',
    'underscore',
    'hqwebapp/js/assert_properties',
    'hqmedia/js/uploaders',
    'hqwebapp/js/initial_page_data',
], function (
    $,
    ko,
    _,
    assertProperties,
    mediaUploaders,
    initialPageData
) {
    function BaseMediaReference(ref, uploaderSlug) {
        'use strict';
        let self = {};

        self.media_class = ref.media_class;
        self.media_type = ref.media_type;
        self.module = ref.module;
        self.form = ref.form;
        self.is_menu_media = ref.is_menu_media;
        self.path = ref.path;
        self.type_icon = ref.icon_class;

        self.slug = uploaderSlug;
        self.upload_controller = null;
        if (self.slug) {
            self.upload_controller = mediaUploaders.uploaderPreset(self.slug);
        }

        // for matching
        self.is_matched = ko.observable(false);
        self.m_id = ko.observable();
        self.uid = ko.observable();
        self.url = ko.observable();
        self.humanized_content_length = ko.observable();
        self.image_size = ko.observable();

        self.upload_button_class = ko.computed(function () {
            return (self.is_matched()) ? "btn btn-success" : "btn btn-danger";
        }, self);

        // Link to module or form
        self.app_url = "";
        if (self.form.unique_id) {
            self.app_url = initialPageData.reverse("form_source", self.form.unique_id);
        } else if (self.module.unique_id) {
            self.app_url = initialPageData.reverse("view_module", self.module.unique_id);
        }

        self.preview_template = null; // override

        // for searching
        self.query = ko.observable();
        self.searching = ko.observable(0);
        self.searched = ko.observable(false);
        self.searchOptions = ko.observableArray();

        self.setObjReference = function (objRef) {
            if (objRef) {
                self.m_id(objRef.m_id);
                self.uid(objRef.uid);
                self.url(objRef.url);
                self.humanized_content_length(objRef.humanized_content_length);
                self.image_size(objRef.image_size);
                $('.media-totals').trigger('refMediaAdded', self);
                self.is_matched(true);
            }
        };

        self.search = function () {
            throw new Error("This functionality is currently broken");
        };

        self.triggerUpload = function () {
            self.upload_controller.currentReference = self;
            if (self.upload_controller) {
                self.upload_controller.uploadParams = {
                    path: self.path,
                    originalPath: self.path,
                    media_type: self.media_class,
                    old_ref: self.m_id || "",
                    replace_attachment: true,
                };
            }
            self.upload_controller.updateUploadFormUI();
        };

        // Needed for Upload Controller

        // we don't want to be dependent on a knockout structure (vellum)
        self.getUrl = function () {
            return self.url();
        };

        self.isMediaMatched = function () {
            return self.is_matched();
        };

        // bound to event mediaUploadComplete
        self.uploadComplete = function (trigger, event, data) {
            if (data && !data.errors.length) {
                self.setObjReference(data.ref);
                self.upload_controller.updateUploadFormUI();
            }
        };

        return self;
    }

    function ImageReference(ref, uploaderSlug) {
        'use strict';
        let self = {};
        self = BaseMediaReference(ref, uploaderSlug || "hqimage");
        self.preview_template = "image-preview-template";
        self.thumb_url = ko.computed(function () {
            return (self.url()) ? self.url() + "?thumb=50" : "";
        }, self);

        return self;
    }

    ImageReference.prototype = Object.create(BaseMediaReference.prototype);
    ImageReference.prototype.constructor = ImageReference;

    function AudioReference(ref, uploaderSlug) {
        'use strict';
        let self = {};
        self = BaseMediaReference(ref, uploaderSlug || "hqaudio");
        self.preview_template = "audio-preview-template";
        return self;
    }

    AudioReference.prototype = Object.create(BaseMediaReference.prototype);
    AudioReference.prototype.constructor = AudioReference;

    function VideoReference(ref, uploaderSlug) {
        'use strict';
        let self = {};
        self = BaseMediaReference(ref, uploaderSlug || "hqvideo");
        self.preview_template = "video-preview-template";
        return self;
    }

    VideoReference.prototype = Object.create(BaseMediaReference.prototype);
    VideoReference.prototype.constructor = VideoReference;


    return {
        'BaseMediaReference': BaseMediaReference,
        'ImageReference': ImageReference,
        'AudioReference': AudioReference,
        'VideoReference': VideoReference,
    };
});
