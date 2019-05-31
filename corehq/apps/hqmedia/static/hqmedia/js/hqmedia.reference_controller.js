hqDefine("hqmedia/js/hqmedia.reference_controller",[
    'jquery',
    'knockout',
    'underscore',
    'hqwebapp/js/assert_properties',
    'hqmedia/js/hqmediauploaders',
],function (
    $,
    ko,
    _,
    assertProperties,
    mediaUploaders
) {
    var HQMediaUploaders = mediaUploaders.get();

    function MultimediaReferenceController(options) {
        assertProperties.assert(options, ['references', 'objectMap', 'totals']);
        var self = {};
        self.objectMap = options.objectMap;
        self.modules = [];
        self.showMissingReferences = ko.observable(false);
        self.totals = ko.observable(options.totals);

        self.toggleRefsText = ko.computed(function () {
            return (self.showMissingReferences()) ? gettext("Show All References") : gettext("Show Only Missing References");
        }, self);

        self.render = function () {
            _.each(options.references, function (ref) {
                if (!self.modules[ref.module.id]) {
                    self.modules[ref.module.id] = ModuleReferences(ref.module.name, self.objectMap, ref.module.id);
                }
                self.modules[ref.module.id].processReference(ref);
            });
            self.modules = _.compact(self.modules);
            _.each(self.modules, function (mod) {
                mod.forms = _.compact(mod.forms);
            });
        };

        self.toggleMissingRefs = function (sender, event) {
            var showMissing = !self.showMissingReferences();
            self.showMissingReferences(showMissing);
            for (var m = 0; m < self.modules.length; m++) {
                var module = self.modules[m];
                if (module) {
                    module.showOnlyMissing(showMissing);
                    for (var f = 0; f < module.forms.length; f++) {
                        var form = module.forms[f];
                        if (form) {
                            form.showOnlyMissing(showMissing);
                        }
                    }
                }
            }
            event.preventDefault();
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

        return self;
    }

    function BaseReferenceGroup(name, objectMap, groupId) {
        'use strict';
        var self = {};
        self.name = name;
        self.id = groupId;
        self.objectMap = objectMap;
        self.menu_references = ko.observableArray();
        self.showOnlyMissing = ko.observable(false);

        self.active_menu_references = ko.computed(function () {
            return (self.showOnlyMissing()) ? self.getMissingRefs(self.menu_references()) : self.menu_references();
        }, self);

        self.showMenuRefs = ko.computed(function () {
            return self.active_menu_references().length > 0;
        }, self);

        self.createReferenceObject = function (ref) {
            var objRef = self.objectMap[ref.path];
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
            return null;
        };

        self.getMissingRefs = function (refs) {
            var missing = [];
            for (var r = 0; r < refs.length; r++) {
                var ref = refs[r];
                if (!ref.is_matched()) {
                    missing.push(ref);
                }
            }
            return missing;
        };
        return self;
    }

    function ModuleReferences(name, objectMap, groupId) {
        'use strict';
        var self = BaseReferenceGroup(name, objectMap, groupId);
        self.forms = [];
        self.id = "module-" + self.id;

        self.processReference = function (ref) {
            if (ref.form.id) {
                if (!self.forms[ref.form.order]) {
                    self.forms[ref.form.order] = FormReferences(ref.form.name, self.objectMap, ref.form.id);
                }
                self.forms[ref.form.order].processReference(ref);
            } else if (ref.is_menu_media) {
                self.menu_references.push(self.createReferenceObject(ref));
            }
        };
        return self;
    }

    ModuleReferences.prototype = Object.create(BaseReferenceGroup.prototype);
    ModuleReferences.prototype.constructor = ModuleReferences;


    function FormReferences(name, objectMap, groupId) {
        'use strict';
        var self = BaseReferenceGroup(name, objectMap, groupId);

        self.images = ko.observableArray();
        self.audio = ko.observableArray();
        self.video = ko.observableArray();

        self.active_images = ko.computed(function () {
            return (self.showOnlyMissing()) ? self.getMissingRefs(self.images()) : self.images();
        }, self);
        self.active_audio = ko.computed(function () {
            return (self.showOnlyMissing()) ? self.getMissingRefs(self.audio()) : self.audio();
        }, self);
        self.active_video = ko.computed(function () {
            return (self.showOnlyMissing()) ? self.getMissingRefs(self.video()) : self.video();
        }, self);

        self.showImageRefs = ko.computed(function () {
            return self.active_images().length > 0;
        }, self);
        self.showAudioRefs = ko.computed(function () {
            return self.active_audio().length > 0;
        }, self);
        self.showVideoRefs = ko.computed(function () {
            return self.active_video().length > 0;
        }, self);

        self.showForm = ko.computed(function () {
            return self.showImageRefs() || self.showAudioRefs() || self.showVideoRefs() || self.showMenuRefs();
        });

        self.processReference = function (ref) {
            var refObj = self.createReferenceObject(ref);
            if (ref.is_menu_media) {
                self.menu_references.push(refObj);
            } else if (ref.media_class === "CommCareImage") {
                self.images.push(refObj);
            } else if (ref.media_class === "CommCareAudio") {
                self.audio.push(refObj);
            } else if (ref.media_class === "CommCareVideo") {
                self.video.push(refObj);
            }
        };

        return self;
    }

    FormReferences.prototype = Object.create(BaseReferenceGroup.prototype);
    FormReferences.prototype.constructor = FormReferences;


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

        self.status_icon = ko.computed(function () {
            return (self.is_matched()) ? "fa fa-check text-success" : "fa fa-exclamation-triangle text-danger";
        }, self);

        self.upload_button_class = ko.computed(function () {
            return (self.is_matched()) ? "btn btn-success" : "btn btn-danger";
        }, self);

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


