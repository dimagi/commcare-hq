function MultimediaReferenceController (references, obj_map, totals) {
    'use strict';
    var self = this;
    self.obj_map = obj_map;
    self.modules = [];
    self.showMissingReferences = ko.observable(false);
    self.totals = ko.observable(totals);
    
    self.toggleRefsText = ko.computed(function () {
        return (self.showMissingReferences()) ? "Show All References" : "Show Only Missing References";
    }, self);

    self.render = function () {
        _.each(references, function (ref) {
            if (!self.modules[ref.module.id]) {
                self.modules[ref.module.id] = new ModuleReferences(ref.module.name, self.obj_map, ref.module.id);
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
            if (media.media_type == data.media_type && media.paths.indexOf(data.path) < 0) {
                media = _.clone(media);
                media.paths.push(data.path);
                media.matched = media.paths.length;
            }
            return media;
        });
        self.totals(newTotals);
    };

}

function BaseReferenceGroup (name, obj_map, group_id) {
    'use strict';
    var self = this;
    self.name = name;
    self.id = group_id;
    self.obj_map = obj_map;
    self.menu_references = ko.observableArray();
    self.showOnlyMissing = ko.observable(false);

    self.active_menu_references = ko.computed(function () {
        return (self.showOnlyMissing()) ? self.getMissingRefs(self.menu_references()) : self.menu_references();
    }, self);

    self.showMenuRefs = ko.computed(function () {
        return self.active_menu_references().length > 0;
    }, self);

    self.createReferenceObject = function (ref) {
        var obj_ref =  self.obj_map[ref.path];
        if (ref.media_class == "CommCareImage") {
            var imageRef = new ImageReference(ref);
            imageRef.setObjReference(obj_ref);
            return imageRef;
        } else if (ref.media_class == "CommCareAudio" ) {
            var audioRef = new AudioReference(ref);
            audioRef.setObjReference(obj_ref);
            return audioRef;
        } else if (ref.media_class == "CommCareVideo" ) {
            var videoRef = new VideoReference(ref);
            videoRef.setObjReference(obj_ref);
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
}

function ModuleReferences (name, obj_map, group_id) {
    'use strict';
    BaseReferenceGroup.call(this, name, obj_map, group_id);
    var self = this;
    self.forms = [];
    self.id = "module-" + self.id;

    self.processReference = function (ref) {
        if (ref.form.id) {
            if (!self.forms[ref.form.order]) {
                self.forms[ref.form.order] = new FormReferences(ref.form.name, self.obj_map, ref.form.id);
            }
            self.forms[ref.form.order].processReference(ref);
        } else if (ref.is_menu_media) {
            self.menu_references.push(self.createReferenceObject(ref));
        }
    };
}

ModuleReferences.prototype = Object.create( BaseReferenceGroup.prototype );
ModuleReferences.prototype.constructor = ModuleReferences;


function FormReferences (name, obj_map, group_id) {
    'use strict';
    BaseReferenceGroup.call(this, name, obj_map, group_id);
    var self = this;
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
        var ref_obj = self.createReferenceObject(ref);
        if (ref.is_menu_media) {
            self.menu_references.push(ref_obj);
        } else if (ref.media_class == "CommCareImage") {
            self.images.push(ref_obj);
        } else if (ref.media_class == "CommCareAudio") {
            self.audio.push(ref_obj);
        } else if (ref.media_class == "CommCareVideo") {
            self.video.push(ref_obj);
        }
    }
}

FormReferences.prototype = Object.create( BaseReferenceGroup.prototype );
FormReferences.prototype.constructor = FormReferences;


function BaseMediaReference (ref) {
    'use strict';
    var self = this;

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

    self.status_icon = ko.computed(function () {
        return (self.is_matched()) ? "icon-ok" : "icon-warning-sign";
    }, self);

    self.upload_button_class = ko.computed(function () {
        return (self.is_matched()) ? "btn btn-success" : "btn btn-warning";
    }, self);

    self.upload_button_text = ko.computed(function () {
        return ((self.is_matched()) ? "Replace " : "Upload ") + self.media_type;
    }, self);

    self.preview_template =  null; // override

    // for searching
    self.query = ko.observable();
    self.searching = ko.observable(0);
    self.searched = ko.observable(false);
    self.searchOptions = ko.observableArray();

    self.setObjReference = function (obj_ref) {
        if (obj_ref) {
            self.m_id(obj_ref.m_id);
            self.uid(obj_ref.uid);
            self.url(obj_ref.url);
            $('.media-totals').trigger('refMediaAdded', self);
            self.is_matched(true);
        }
    };

    self.search = function () {
        throw new Error("This functionality is currently broken");
        // leftovers from Tim. todo: fix
//        if (self.query()) {
//            self.searched(true);
//            self.searching(self.searching() + 1);
//            $.getJSON(searchUrl, {q: self.query(), t: self.type()}, function (res) {
//                self.searching(self.searching() - 1);
//                self.searchOptions([]);
//                for (var i = 0; i < res.length; i++) {
//                    self.searchOptions.push(new MediaOption(self, res[i]))
//                }
//            });
//        }
    };

    self.triggerUpload = function () {
        self.upload_controller.resetUploader();
        self.upload_controller.currentReference = self;
        if (self.upload_controller) {
            self.upload_controller.uploadParams = {
                path: self.path,
                media_type : self.media_class,
                old_ref: self.m_id || "",
                replace_attachment: true
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
}

function ImageReference (ref) {
    'use strict';
    BaseMediaReference.call(this, ref);
    var self = this;
    self.upload_controller = HQMediaUploaders['hqimage'];
    self.preview_template = "image-preview-template";
    self.thumb_url = ko.computed(function () {
        return (self.url()) ? self.url() + "?thumb=50" : "";
    }, self);
}

ImageReference.prototype = Object.create( BaseMediaReference.prototype );
ImageReference.prototype.constructor = ImageReference;


function AudioReference (ref) {
    'use strict';
    BaseMediaReference.call(this, ref);
    var self = this;
    self.upload_controller = HQMediaUploaders['hqaudio'];
    self.preview_template = "audio-preview-template";
}

AudioReference.prototype = Object.create( BaseMediaReference.prototype );
AudioReference.prototype.constructor = AudioReference;


function VideoReference (ref) {
    'use strict';
    BaseMediaReference.call(this, ref);
    var self = this;
    self.upload_controller = HQMediaUploaders['hqvideo'];
    self.preview_template = "video-preview-template";
}

VideoReference.prototype = Object.create( BaseMediaReference.prototype );
VideoReference.prototype.constructor = VideoReference;


// Kept from Tim, you might want to fix it up a bit
function MediaOption (mediaRef, data) {
    var self = this;
    self.mediaRef = mediaRef;
    self.title = data.title;
    self.license = data.licenses.join(", ");
    self.licenses = data.licenses;
    self.url = ko.observable(data.url); // so we can preview it; we never change .url
    self.m_id = data.m_id;
    self.uid = '';
    self.tags = data.tags;

    self.choose = function() {
        $.post(chooseImageUrl, {media_type: self.mediaRef.type(), path: self.mediaRef.path(), id: self.m_id}, function (res) {
            if (self.mediaRef.type() == "Image")
                self.mediaRef.foundNewImage(null, res);
            else if (self.mediaRef.type() == "Audio")
                self.mediaRef.foundNewAudio(null, res);
        }, 'json');
    }
}
