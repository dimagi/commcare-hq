hqDefine('app_manager/js/app_manager_media', function () {
    var appMenuMediaManager = function (o) {
        /* This interfaces the media reference for a form or module menu
        (as an icon or image) with the upload manager.*/
        'use strict';
        var initialPageData = hqImport("hqwebapp/js/initial_page_data").get,
            self = {
                isDefaultLanguage: initialPageData('current_language') === initialPageData('default_language'),
            };

        self.enabled = ko.observable(
            o.ref.use_default_media ? self.isDefaultLanguage : true
        );
        self.ref = ko.observable(new MenuMediaReference(o.ref));
        self.refHasPath = ko.computed(function () {
            return self.ref().path.length > 0;
        });
        self.objectMap = ko.observable(o.objectMap);
        self.defaultPath = o.defaultPath;
        self.inputElement = o.inputElement;

        self.uploadController = o.uploadController;

        self.customPath = ko.observable(o.ref.path || '');
        self.useCustomPath = ko.observable(self.customPath() !== self.defaultPath && self.refHasPath());

        self.showCustomPath = ko.computed(function () {
            return self.useCustomPath();
        });

        self.showDefaultPath = ko.computed(function () {
            return !self.showCustomPath();
        });

        self.savedPath = ko.computed(function () {
            if (self.useCustomPath()) {
                return self.customPath();
            }
            return self.ref().path;
        });

        self.currentPath = ko.computed(function () {
            if (self.savedPath().length === 0) {
                return self.defaultPath;
            }
            return self.savedPath();
        });

        self.altText = ko.observable(o.ref.alt_text);

        self.multimediaObject = ko.computed(function () {
            return self.objectMap()[self.currentPath()];
        });

        self.isMediaMatched = ko.computed(function () {
            return !!self.multimediaObject() && self.refHasPath();
        });

        self.isMediaUnmatched = ko.computed(function () {
            return !self.isMediaMatched();
        });

        self.url = ko.computed(function () {
            if (self.multimediaObject()) {
                return self.multimediaObject().url;
            }
        });

        self.thumbnailUrl = ko.computed(function () {
            if (self.multimediaObject()) {
                return self.url() + "?thumb=50";
            }
            return '#';
        });

        self.objectId = ko.computed(function () {
            if (self.multimediaObject()) {
                return self.multimediaObject().m_id;
            }
        });

        self.languagesLinked = ko.observable(o.ref.use_default_media);

        self.setCustomPath = function () {
            self.useCustomPath(true);
            if (self.customPath().length === 0) {
                self.customPath(self.defaultPath);
            }
            self.updateResource();
        };

        self.setDefaultPath = function () {
            self.useCustomPath(false);
            var newRef = self.ref();
            newRef.path = self.defaultPath;
            self.ref(newRef);
            self.updateResource();
        };

        self.removeMedia = function () {
            self.ref(new MenuMediaReference({}));
            self.useCustomPath(false);
            self.customPath('');
            self.updateResource();
        };

        self.getUploadParams = function () {
            return {
                path: interpolatePath(self.currentPath()),
                media_type: self.ref().mediaType,
                replace_attachment: true,
            };
        };

        self.getControllerRef = function () {
            return {
                path: self.currentPath(),
                isMediaMatched: self.isMediaMatched,
                getUrl: self.url,
                m_id: self.objectId,
            };
        };

        self.passToUploadController = function () {
            self.uploadController.resetUploader();
            self.uploadController.currentReference = self.getControllerRef();
            self.uploadController.uploadParams = self.getUploadParams();
            self.uploadController.updateUploadFormUI();
        };

        self.uploadComplete = function (trigger, event, data) {
            if (data.ref) {
                var ref = data.ref,
                    objMap = self.objectMap();
                objMap[ref.path] = ref;
                self.ref(new MenuMediaReference(ref));
                self.objectMap(objMap);
                self.updateResource();
                if (self.currentPath() !== data.ref.path) {
                    //CurrentPath has a different filetype to the
                    //uploaded file
                    self.customPath(data.ref.path);
                }
            }
        };

        self.updateResource = function () {
            self.inputElement.trigger('change');
        };

        return self;
    };

    var MenuMediaReference = function (ref) {
        'use strict';
        var self = {};
        self.path = ref.path || '';
        self.iconType = ref.icon_class || '';
        self.mediaType = ref.media_class || '';
        self.module = ref.module;
        self.form = ref.form;
        self.altText = ref.alt_text || '';

        return self;
    };

    function initNavMenuMedia(qualifier, imageRef, audioRef, objectMap, defaultFileName) {
        var uploaders = hqImport("app_manager/js/nav_menu_media_common");
        var $mediaImage = $('#' + qualifier + 'media_image'),
            $mediaAudio = $('#' + qualifier + 'media_audio');

        var menuImage = appMenuMediaManager({
            ref: imageRef,
            objectMap: objectMap,
            uploadController: uploaders.iconUploader,
            defaultPath: 'jr://file/commcare/image/' + defaultFileName + '.png',
            inputElement: $mediaImage,
        });

        var menuAudio = appMenuMediaManager({
            ref: audioRef,
            objectMap: objectMap,
            uploadController: uploaders.audioUploader,
            defaultPath: 'jr://file/commcare/audio/' + defaultFileName + '.mp3',
            inputElement: $mediaAudio,
        });

        if ($mediaImage.length) {
            $mediaImage.koApplyBindings(menuImage);
        }
        if ($mediaAudio.length) {
            $mediaAudio.koApplyBindings(menuAudio);
        }
        return {
            menuImage: menuImage,
            menuAudio: menuAudio,
        };
    }

    return {
        initNavMenuMedia: initNavMenuMedia,
        appMenuMediaManager: appMenuMediaManager,
    };

    function interpolatePath(path) {
        // app media attributes are interpolated on server side, media uploads should also be interpolated
        // See corehq.apps.app_manager.views.media_utils.process_media_attribute
        if (!path) {
            return path;
        }

        if (path.startsWith('jr://')) {
            return path;
        } else if (path.startsWith('/file/')) {
            path = 'jr:/' + path;
        } else if (path.startsWith('file/')) {
            path = 'jr://' + path;
        } else if (path.startsWith('/')) {
            path = 'jr://file' + path;
        } else {
            path = 'jr://file/' + path;
        }
        return path;
    }
});
