hqDefine("hqmedia/js/reference_controller",[
    'jquery',
    'knockout',
    'underscore',
    'hqwebapp/js/assert_properties',
    'hqmedia/js/hqmediauploaders',
], function (
    $,
    ko,
    _,
    assertProperties,
    mediaUploaders
) {
    var HQMediaUploaders = mediaUploaders.get();

    function MultimediaReferenceController() {
        var self = {};
        self.references = ko.observableArray();
        self.showMissingReferences = ko.observable(false);
        self.totals = ko.observableArray();

        self.isInitialLoad = ko.observable(true);
        self.showPaginationSpinner = ko.observable(false);
        self.itemsPerPage = ko.observable();
        self.totalItems = ko.computed(function () {
            // TODO: this isn't quite right because some files appear in multiple places and therefore have multiple rows
            return _.reduce(_.pluck(self.totals(), 'matched'), function (memo, num) {
                return memo + num;
            }, 0);
        });

        self.toggleRefsText = ko.computed(function () {
            return (self.showMissingReferences()) ? gettext("Show All References") : gettext("Show Only Missing References");
        }, self);

        self.goToPage = function (page) {
            self.showPaginationSpinner(true);
            $.ajax({
                url: hqImport("hqwebapp/js/initial_page_data").reverse('hqmedia_references'),
                data: {
                    json: 1,
                    page: page,
                    limit: self.itemsPerPage(),
                },
                success: function (data) {
                    self.isInitialLoad(false);
                    self.showPaginationSpinner(false);
                    self.references(_.compact(_.map(data.references, function (ref) {
                        var objRef = data.object_map[ref.path];
                        if (ref.media_class === "CommCareImage") {
                            var imageRef = ImageReference(ref);
                            imageRef.setObjReference(objRef);
                            return imageRef;
                        } else if (ref.media_class === "CommCareAudio") {
                            var audioRef = AudioReference(ref);
                            audioRef.setObjReference(objRef);
                            return audioRef;
                        } else if (ref.media_class === "CommCareVideo") {
                            var videoRef = VideoReference(ref);
                            videoRef.setObjReference(objRef);
                            return videoRef;
                        }
                        // Other multimedia, like HTML print templates, is ignored by the reference checker
                        return null;
                    })));
                    self.totals(data.totals);
                    $('.preview-media').tooltip();
                },
                error: function () {
                    self.showPaginationSpinner(false);
                    hqImport('hqwebapp/js/alert_user').alert_user(gettext("Error fetching multimedia, " +
                        "please try again or report an issue if the problem persists."), 'danger');
                },
            });
        };

        self.toggleMissingRefs = function (sender, event) {
            self.showMissingReferences(!self.showMissingReferences());
        };

        self.incrementTotals = function (trigger, event, data) {
            var newTotals = _.map(self.totals(), function (media) {
                if (media.media_type === data.media_type && media.paths.indexOf(data.path) < 0) {
                    media = _.clone(media);
                    media.paths.push(data.path);
                    media.matched = media.paths.length;
                }
                return media;
            });
            self.totals(newTotals);
        };

        self.goToPage(1);

        return self;
    }

    function BaseMediaReference(ref) {
        'use strict';
        var self = {};

        self.media_class = ref.media_class;
        self.media_type = ref.media_type;
        self.module = ref.module;
        self.form = ref.form;
        self.is_menu_media = ref.is_menu_media;
        self.path = ref.path;
        self.type_icon = ref.icon_class;

        self.upload_controller = null; // override

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
            self.app_url = hqImport("hqwebapp/js/initial_page_data").reverse("form_source", self.form.unique_id);
        } else if (self.module.unique_id) {
            self.app_url = hqImport("hqwebapp/js/initial_page_data").reverse("view_module", self.module.unique_id);
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
            self.upload_controller.resetUploader();
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
            }
        };

        return self;
    }

    function ImageReference(ref) {
        'use strict';
        var self = {};
        self = BaseMediaReference(ref);
        self.upload_controller = HQMediaUploaders['hqimage'];
        self.preview_template = "image-preview-template";
        self.thumb_url = ko.computed(function () {
            return (self.url()) ? self.url() + "?thumb=50" : "";
        }, self);

        return self;
    }

    ImageReference.prototype = Object.create(BaseMediaReference.prototype);
    ImageReference.prototype.constructor = ImageReference;


    function AudioReference(ref) {
        'use strict';
        var self = {};
        self = BaseMediaReference(ref);
        self.upload_controller = HQMediaUploaders['hqaudio'];
        self.preview_template = "audio-preview-template";
        return self;
    }

    AudioReference.prototype = Object.create(BaseMediaReference.prototype);
    AudioReference.prototype.constructor = AudioReference;


    function VideoReference(ref) {
        'use strict';
        var self = {};
        self = BaseMediaReference(ref);
        self.upload_controller = HQMediaUploaders['hqvideo'];
        self.preview_template = "video-preview-template";
        return self;
    }

    VideoReference.prototype = Object.create(BaseMediaReference.prototype);
    VideoReference.prototype.constructor = VideoReference;


    return {
        'MultimediaReferenceController': MultimediaReferenceController,
        'BaseMediaReference': BaseMediaReference,
        'ImageReference': ImageReference,
    };

});
