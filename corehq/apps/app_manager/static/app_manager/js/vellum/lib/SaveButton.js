// EXTRACTED FROM COMMCAREHQ main.js
var SaveButton = {
    /*
        options: {
            save: "Function to call when the user clicks Save",
            unsavedMessage: "Message to display when there are unsaved changes and the user leaves the page"
            csrftoken: "Token required in headers of AJAX request to prevent CSRF"
        }
    */
    init: function (options) {
        var button = {
            disabled: false,
            csrftoken: options.csrftoken,
            $save: $('<span/>').text(SaveButton.message.SAVE).click(function (e) {
                button.fire('save', e);
            }).addClass('btn btn-info'),
            $retry: $('<span/>').text(SaveButton.message.RETRY).click(function (e) {
                button.fire('save', e);
            }).addClass('btn btn-info'),
            $saving: $('<span/>').text(SaveButton.message.SAVING).prepend('<i class="fa fa-refresh icon-spin"></i> ').addClass('btn btn-info disabled'),
            $saved: $('<span/>').text(SaveButton.message.SAVED).addClass('btn btn-info disabled'),
            ui: $('<div/>').addClass('pull-right'),
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
                this.fire('state:change');
            },
            ajaxOptions: function (options) {
                var options = options || {},
                    beforeSend = options.beforeSend || function () {},
                    success = options.success || function () {},
                    error = options.error || function () {},
                    that = this;
                options.beforeSend = function (xhr) {
                    if (that.csrftoken && !this.crossDomain) {
                        xhr.setRequestHeader("X-CSRFToken", that.csrftoken);
                    }
                    that.setState('saving');
                    that.nextState = 'saved';
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
                return options;
            },
            ajax: function (options) {
                options = button.ajaxOptions(options);

                if (typeof options.url === 'function') {
                    options.beforeSend();
                    var result = options.url(options.data);
                    options.success(result || {});
                } else {
                    $.ajax(options);
                }
            },
            beforeunload: function () {
                var stillAttached = button.ui.parents()[button.ui.parents().length - 1].tagName.toLowerCase() == 'html';
                if (button.state !== 'saved' && stillAttached) {
                    return options.unsavedMessage || "";
                }
            }
        };
        eventize(button);
        button.setState('saved');
        button.on('change', function () {
            this.setStateWhenReady('save');
        });
        button.on('disable', function () {
            this.disabled = true;
            this.$save.addClass('disabled');
            this.$saving.addClass('disabled');
            this.$retry.addClass('disabled');
        });
        button.on('enable', function () {
            this.disabled = false;
            this.$save.removeClass('disabled');
            this.$saving.removeClass('disabled');
            this.$retry.removeClass('disabled');
        });
        button.on('save', function (event) {
            if (button.disabled){
                return;
            } else if (options.save) {
                options.save(event);
            } else if (options.saveRequest){
                var o = button.ajaxOptions();
                o.beforeSend();
                options.saveRequest(event)
                    .success(o.success)
                    .error(o.error)
                ;
            }
        });
        return button;
    },
    initForm: function ($form, options) {
        var url = $form.attr('action'),
            button = SaveButton.init({
                unsavedMessage: options.unsavedMessage,
                save: function () {
                    button.ajax({
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
//        $form.on('textchange', 'input, textarea', fireChange);
        $form.find('input, textarea').bind('textchange', fireChange);
        return button;
    },
    message: {
        SAVE: 'Save',
        SAVING: 'Saving',
        SAVED: 'Saved',
        RETRY: 'Try Again',
        ERROR_SAVING: 'There was an error saving'
    }
};

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

exports.init = SaveButton.init;
