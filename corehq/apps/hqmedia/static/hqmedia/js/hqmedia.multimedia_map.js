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
        var modal_id = 'hqm-'+params.type+'-modal-'+params.uid;

        $(element).addClass("btn");
        $(element).attr('data-toggle', 'modal');
        $(element).attr('href', '#'+modal_id);
    },
    update: function(element, valueAccessor, allBindingsAccessor) {
        var has_ref = valueAccessor()() || false;
        var params = allBindingsAccessor().uploadMediaButtonParams;

        $(element).removeClass("btn-primary btn-success");
        if (has_ref) {
            $(element).text("Replace "+params.type);
            $(element).addClass("btn-primary");
        } else {
            $(element).text("Upload "+params.type);
            $(element).addClass("btn-success");
        }

    }
};

ko.bindingHandlers.uploadMediaModal = {
    init: function(element, valueAccessor, allBindingsAccessor) {
        var params = allBindingsAccessor().uploadMediaModalParams;
        var modal_id = 'hqm-'+params.type+'-modal-'+params.uid;
        $(element).attr('id', modal_id);
        $(element).on('show', function () {
            var $uploadForm = $('#hqmedia-upload-'+params.type);
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
        self.image_refs.push(new HQMediaRef(ref, "Image"));
    });

    _.each(data.audio, function(ref) {
        self.audio_refs.push(new HQMediaRef(ref, "Audio"));
    });
},
HQMediaRef = function(mediaRef, type) {
    var self = this;
    self.type = type;
    self.path = mediaRef.path;
    self.uid = mediaRef.uid;

    self.m_id = ko.observable(mediaRef.m_id || "");
    self.url = ko.observable(mediaRef.url || "");
    self.has_ref = ko.observable(!!mediaRef.url);

    self.uploadNewImage = function () {
        if (hqimage_uploader) {
            hqimage_uploader.uploadParams = {
                path: self.path,
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
                path: self.path,
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
};