ko.bindingHandlers.mediaStatus = {
    init: function(element, valueAccessor, allBindingsAccessor) {
        var $icon = $('<i class="icon icon-white"></i>');
        $(element).addClass('label');
        $(element).append($icon);
    },
    update: function(element, valueAccessor, allBindingsAccessor) {
        var value = valueAccessor()() || false,
            $icon = $(element).find('i');

        $(element).removeClass('label-success label-important');
        $icon.removeClass('icon-ok icon-remove');

        if (value) {
            $(element).text(' Found');
            $(element).addClass('label-success');
            $icon.addClass('icon-ok');
        } else {
            $(element).text(' Missing');
            $(element).addClass('label-important');
            $icon.addClass('icon-remove');
        }
        $(element).prepend($icon);
    }
};

ko.bindingHandlers.previewHQImageButton = {
    update: function(element, valueAccessor) {
        var url = valueAccessor()() || "";
        $(element).text('');
        if (!_.isEmpty(url)) {
            var $previewButton = $('<a target="_blank" class="btn btn-info" />');
            $previewButton.attr('href', url);
            $previewButton.text('Preview Image');
            $previewButton.popover({
                title: 'Click to open in new window',
                content: '<img src="'+url+'" alt="preview image" />',
                placement: 'bottom'
            });
            $(element).append($previewButton);
        }
    }
};

ko.bindingHandlers.previewHQAudioButton = {
    update: function(element, valueAccessor, allBindingsAccessor) {
        var url = valueAccessor()() || "",
            params = allBindingsAccessor().previewHQAudioParams,
            is_playing = allBindingsAccessor().HQAudioIsPlaying;



        $(element).text('');
        if (!_.isEmpty(url)) {
            var $previewButton = $('<a target="_blank" class="btn btn-info" />');
            $previewButton.attr('href', url);
            $previewButton.text('Preview Audio');
            $previewButton.tooltip({
                placement: 'right',
                title: 'Open audio file in new tab.'
            });
//            var $jplayer = $("#jquery_jplayer");
//            $(element).unbind('click');

//            $(element).on('click', function () {
//                if(is_playing())
//                    is_playing(false);
//                $(this).find('.btn').text("Stop Audio");
//                is_playing(true);
//                return false;
//            });

            $(element).append($previewButton);
        }
    }
};

ko.bindingHandlers.HQAudioIsPlaying = {
    update: function (element, valueAccessor) {
        var is_playing = valueAccessor()() || false,
            $jplayer = $("#jquery_jplayer");

//        var $playLink = $(element).find('.btn');
//        if ($playLink.text() == "Stop Audio" && !is_playing)
//            $playLink.text("Play Audio");
    }
};

ko.bindingHandlers.previewHQImage = {
    update: function (element, valueAccessor) {
        var url = valueAccessor()() || "";
        var $newImage;
        if (!_.isEmpty(url)) {
            $newImage = $('<img alt="Uploaded Image" />');
            $newImage.attr('src', url);
            $(element).find('.controls').html($newImage);
            $newImage.fadeIn();
            $(element).removeClass('hide');
        } else {
            $(element).addClass('hide');
        }
    }
};

ko.bindingHandlers.uploadMediaButton = {
    init: function(element, valueAccessor, allBindingsAccessor) {
        var params = allBindingsAccessor().uploadMediaButtonParams;
        var modal_id = 'hqm-'+params.type()+'-modal-'+params.uid();

        $(element).addClass("btn");
        $(element).attr('data-toggle', 'modal');
        $(element).attr('href', '#'+modal_id);
    },
    update: function(element, valueAccessor, allBindingsAccessor) {
        var has_ref = valueAccessor()() || false;
        var params = allBindingsAccessor().uploadMediaButtonParams;

        $(element).removeClass("btn-primary btn-success");
        if (has_ref) {
            $(element).text("Replace "+params.type());
            $(element).addClass("btn-primary");
        } else {
            $(element).text("Upload or select "+params.type());
            $(element).addClass("btn-success");
        }

    }
};

ko.bindingHandlers.uploadMediaModal = {
    init: function(element, valueAccessor, allBindingsAccessor) {
        var params = allBindingsAccessor().uploadMediaModalParams;
        var modal_id = 'hqm-'+params.type()+'-modal-'+params.uid();
        $(element).attr('id', modal_id);
        $(element).on('show', function () {
            var $uploadForm = $('#hqmedia-upload-'+params.type());
            $uploadForm.remove();
            $uploadForm.removeClass('hide');
            $(this).find('.upload-form-placeholder').append($uploadForm);
        });
    },
    update: function(element, valueAccessor) {
        var has_ref = valueAccessor()() || false;
        if (has_ref)
            $(element).find('.upload-state').text('Replace');
        else
            $(element).find('.upload-state').text('Upload');
    }
};

var MultimediaMap = function (data, jplayerSwfPath) {
    var self = this;
    self.image_refs = ko.observableArray();
    self.audio_refs = ko.observableArray();
    self.by_path = {};
    self.has_ref = false;

    self.is_audio_playing = ko.observable(false);

    var _jplayer = $("#jquery_jplayer");

    _jplayer.jPlayer({
        swfPath: jplayerSwfPath,
        supplied: "mp3",
        wmode: "window",
        error: function(e) {
            console.log("jPlayer error", e);
        },
        ready: function(e) {
//                    _jplayer_trigger.click(function(e) {
//                        if (_jplayer_is_playing && $(this).text() == _jplayer_stop_text) {
//                            _jplayer.jPlayer("stop");
//                        } else {
//                            _jplayer.jPlayer("setMedia", {
//                                mp3: $(this).attr("href")
//                            });
//                            _jplayer_is_playing = true;
//                            _jplayer.jPlayer("play");
//                            _jplayer_trigger.find('span').text(_jplayer_play_text);
//                            $(this).find('span').text(_jplayer_stop_text);
//                        }
//                        return false;
//                    }).find('span').text(_jplayer_play_text);
        },
        ended: function(e) {
            self.is_audio_playing(false);
        },
        pause: function(e) {
            self.is_audio_playing(false);
        }
    });


    _.each(data.images, function(ref) {
        var refObj = new HQMediaRef(ref, "Image")
;        self.image_refs.push(refObj);
        self.by_path[ref.uid] = refObj;
    });

    _.each(data.audio, function(ref) {
        var refObj = new HQMediaRef(ref, "Audio");
        self.audio_refs.push(refObj);
        self.by_path[ref.uid] = refObj;
    });
},

HQMediaRef = function(mediaRef, type) {
    var self = this;
    self.type = ko.observable(type);
    self.path = ko.observable(mediaRef.path);
    self.uid = ko.observable(mediaRef.uid);

    self.m_id = ko.observable(mediaRef.m_id || "");
    self.url = ko.observable(mediaRef.url || "");
    self.has_ref = ko.observable(!!mediaRef.url);

    self.searching = ko.observable(0);
    self.searched = ko.observable(false);
    self.imageOptions = ko.observableArray();
    self.audioOptions = ko.observableArray();
    self.query = ko.observable();

    self.searchForImages = function() {
        if (self.query()) {
            self.searched(true);
            self.searching(self.searching() + 1);
            $.getJSON(searchUrl, {q: self.query(), t: self.type()}, function (res) {
                self.searching(self.searching() - 1);
                self.imageOptions([]);
                for (var i = 0; i < res.length; i++) {
                    self.imageOptions.push(new MediaOption(self, res[i]))
                }
            });
        }
    };

    self.searchForAudio = function() {
        if (self.query()) {
            self.searched(true);
            self.searching(self.searching() + 1);
            $.getJSON(searchUrl, {q: self.query(), t: self.type()}, function (res) {
                self.searching(self.searching() - 1);
                self.audioOptions([]);
                for (var i = 0; i < res.length; i++) {
                    self.audioOptions.push(new MediaOption(self, res[i]))
                }
            });
        }
    };

    self.uploadNewImage = function () {
        if (hqimage_uploader) {
            hqimage_uploader.uploadParams = {
                path: self.path(),
                media_type : "CommCareImage",
                old_ref: self.m_id || "",
                replace_attachment: true
            };
            hqimage_uploader.onSuccess = self.foundNewImage;
        }
    };

    self.foundNewImage = function (event, data) {
        if (data.match_found) {
            self.has_ref(true);
            self.m_id(data.image.m_id);
            self.url(data.image.url);
        }
    };

    self.uploadNewAudio = function () {
        if (hqaudio_uploader) {
            hqaudio_uploader.uploadParams = {
                path: self.path(),
                media_type : "CommCareAudio",
                old_ref: self.m_id || "",
                replace_attachment: true
            };
            hqaudio_uploader.onSuccess = self.foundNewAudio;
        }
    };
    self.foundNewAudio = function (event, data) {
        if (data.match_found) {
            self.has_ref(true);
            self.m_id(data.audio.m_id);
            self.url(data.audio.url);
        }
    };
},

MediaOption = function(mediaRef, data) {
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
};