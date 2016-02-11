/*
 Legacy, should deal with replacing these soon?
 */
var COMMCAREHQ = (function () {
    'use strict';
    return {
        initBlock: function ($elem) {
            $('.post-link').click(function (e) {
                e.preventDefault();
                $.postGo($(this).attr('href'), {});
            });
        },
        makeHqHelp: function (opts, wrap) {
            wrap = wrap === undefined ? true : wrap;
            var el = $(
                '<div class="hq-help">' +
                    '<a href="#">' +
                        '<i class="icon-question-sign fa fa-question-circle" data-trigger="focus"></i></a></div>'
                ),
                attrs = ['content', 'title', 'placement'];

            attrs.map(function (attr) {
                $('a', el).data(attr, opts[attr]);
            });
            if (wrap) {
                el.hqHelp();
            }
            return el;
        },
        transformHelpTemplate: function ($template, wrap) {
            var $help = COMMCAREHQ.makeHqHelp($template.data(), wrap);
            $help.insertAfter($template);
            $template.remove();
        },
        updateDOM: function (update) {
            var key;
            for (key in update) {
                if (update.hasOwnProperty(key)) {
                    $(key).text(update[key]);
                }
            }
        },
        SaveButton: _makeSaveButton({SAVE: 'Save', SAVING: 'Saving...', SAVED: 'Saved', RETRY: 'Try Again',
    ERROR_SAVING: 'There was an error saving'}, 'btn btn-success'),
        DeleteButton: _makeSaveButton({SAVE: 'Delete', SAVING: 'Deleting...', SAVED: 'Deleted', RETRY: 'Try Again',
    ERROR_SAVING: 'There was an error deleting'}, 'btn btn-danger')
    };
}());

var eventize = function (that) {
    'use strict';
    var events = {};
    that.on = function (tag, callback) {
        if (events[tag] === undefined) {
            events[tag] = [];
        }
        events[tag].push(callback);
        return that;
    };
    that.fire = function (tag, e) {
        var i;
        if (events[tag] !== undefined) {
            for (i = 0; i < events[tag].length; i += 1) {
                events[tag][i].apply(that, [e]);
            }
        }
        return that;
    };
    return that;
};

function _makeSaveButton(messageStrings, cssClass) {
    var SaveButton = {
        /*
         options: {
         save: "Function to call when the user clicks Save",
         unsavedMessage: "Message to display when there are unsaved changes and the user leaves the page"
         }
         */
        init: function (options) {
            var button = {
                $save: $('<span/>').text(SaveButton.message.SAVE).click(function () {
                    button.fire('save');
                }).addClass(cssClass),
                $retry: $('<span/>').text(SaveButton.message.RETRY).click(function () {
                    button.fire('save');
                }).addClass(cssClass),
                $saving: $('<span/>').text(SaveButton.message.SAVING).addClass('btn btn-default disabled'),
                $saved: $('<span/>').text(SaveButton.message.SAVED).addClass('btn btn-default disabled'),
                ui: $('<div/>').css({float: 'right'}),
                setStateWhenReady: function (state) {
                    if (this.state === 'saving') {
                        this.nextState = state;
                    } else {
                        this.setState(state);
                    }
                },
                setState: function (state) {
                    if (this.state === state) {
                        return;
                    }
                    this.state = state;
                    this.$save.detach();
                    this.$saving.detach();
                    this.$saved.detach();
                    this.$retry.detach();
                    if (state === 'save') {
                        this.ui.append(this.$save);
                    } else if (state === 'saving') {
                        this.ui.append(this.$saving);
                    } else if (state === 'saved') {
                        this.ui.append(this.$saved);
                    } else if (state === 'retry') {
                        this.ui.append(this.$retry);
                    }
                },
                ajax: function (options) {
                    var beforeSend = options.beforeSend || function () {},
                        success = options.success || function () {},
                        error = options.error || function () {},
                        that = this;
                    options.beforeSend = function (jqXHR, settings) {
                        that.setState('saving');
                        that.nextState = 'saved';
                        $.ajaxSettings.beforeSend(jqXHR, settings);
                        beforeSend.apply(this, arguments);
                    };
                    options.success = function (data) {
                        that.setState(that.nextState);
                        success.apply(this, arguments);
                    };
                    options.error = function (data) {
                        that.nextState = null;
                        that.setState('retry');
                        alert(SaveButton.message.ERROR_SAVING);
                        error.apply(this, arguments);
                    };
                    var jqXHR = $.ajax(options);
                    if (!jqXHR) {
                        // request was aborted
                        that.setState('save');
                    }
                }
            };
            eventize(button);
            button.setState('saved');
            button.on('change', function () {
                this.setStateWhenReady('save');
            });
            if (options.save) {
                button.on('save', options.save);
            }
            $(window).bind('beforeunload', function () {
                var stillAttached = button.ui.parents()[button.ui.parents().length - 1].tagName.toLowerCase() == 'html';
                if (button.state !== 'saved' && stillAttached) {
                    return options.unsavedMessage || "";
                }
            });
            return button;
        },
        initForm: function ($form, options) {
            var url = $form.attr('action'),
                button = SaveButton.init({
                    unsavedMessage: options.unsavedMessage,
                    save: function () {
                        this.ajax({
                            url: url,
                            type: 'POST',
                            dataType: 'json',
                            data: $form.serialize(),
                            success: options.success
                        });
                    }
                }),
                fireChange = function () {
                    button.fire('change');
                };
            $form.find('*').change(fireChange);
            $form.find('input, textarea').bind('textchange', fireChange);
            return button;
        },
        message: messageStrings
    };

    return SaveButton;
}
