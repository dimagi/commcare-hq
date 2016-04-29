/*global $:false, jQuery:false, window:false, document:false */

$.prototype.iconify = function (icon) {
    'use strict';
    var $icon = $("<i/>").addClass(icon).css('float', 'left');
    $(this).css('width', "16px").prepend($icon);
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


var _SaveButton = {
    /*
        options: {
            save: "Function to call when the user clicks Save",
            unsavedMessage: "Message to display when there are unsaved changes and the user leaves the page"
        }
    */
    init: function (options) {
        var button = {
            disabled: false,
            $save: $('<span/>').text(_SaveButton.message.SAVE).click(function () {
                button.fire('save');
            }).addClass('btn btn-success'),
            $retry: $('<span/>').text(_SaveButton.message.RETRY).click(function () {
                button.fire('save');
            }).addClass('btn btn-success'),
            $saving: $('<span/>').text(_SaveButton.message.SAVING).prepend('<i class="icon-refresh icon-spin"></i> ').addClass('btn btn-default disabled'),
            $saved: $('<span/>').text(_SaveButton.message.SAVED).addClass('btn btn-default disabled'),
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
                    responseText = data.responseText || '';
                    alert(_SaveButton.message.ERROR_SAVING + '\n' +  data.responseText);
                    error.apply(this, arguments);
                };
                return options;
            },
            ajax: function (options) {
                var jqXHR = $.ajax(button.ajaxOptions(options));
                if (!jqXHR) {
                    // request was aborted
                    this.setState('save');
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
        button.on('save', function () {
            if (button.disabled){
                return;
            } else if (options.save) {
                options.save();
            } else if (options.saveRequest){
                var o = button.ajaxOptions();
                o.beforeSend();
                options.saveRequest()
                    .success(o.success)
                    .error(o.error)
                ;
            }
        });

        var beforeunload = function () {
            var parentEl = button.ui.parents()[button.ui.parents().length - 1];
            var stillAttached = parentEl ? parentEl.tagName.toLowerCase() == 'html' : false;
            if (button.state !== 'saved' && stillAttached) {
                return options.unsavedMessage || "";
            }
        };
        COMMCAREHQ.bindBeforeUnload(beforeunload);
        return button;
    },
    initForm: function ($form, options) {
        var url = $form.attr('action'),
            button = _SaveButton.init({
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


var COMMCAREHQ = (function () {
    'use strict';
    return {
        icons: {
            GRIP:   'fa fa-sort icon-resize-vertical icon-blue',
            ADD:    'fa fa-plus icon-plus icon-blue',
            COPY:   'fa fa-copy icon-copy icon-blue',
            DELETE: 'fa fa-remove icon-remove icon-blue',
            PAPERCLIP: 'fa fa-paperclip icon-paper-clip'
        },
        makeHqHelp: function (opts, wrap) {
            wrap = wrap === undefined ? true : wrap;
            var iconClass = "icon-question-sign";
            var containerStyle = '';
            if (opts.bootstrap3) {
                iconClass = "fa fa-question-circle";
                containerStyle = 'height: 0; width: auto;';
            }

            var el = $(
                '<div style="' + containerStyle + '" class="hq-help">' +
                    '<a href="#" tabindex="-1">' +
                        '<i class="' + iconClass + '"></i></a></div>'
                ),
                attrs = ['content', 'title', 'placement'];
            attrs.map(function (attr) {
                el.find('a').attr("data-"+attr, opts[attr]);
            });
            if (wrap) {
                el.hqHelp();
            }
            return el;
        },
        transformHelpTemplate: function ($template, wrap) {
            if ($template.data()) {
                var $help = COMMCAREHQ.makeHqHelp($template.data(), wrap);
                $help.insertAfter($template);
                $template.remove();
            }
        },
        initBlock: function ($elem) {
            $('.submit_on_click', $elem).on("click", function (e) {
                e.preventDefault();
                if (!$(this).data('clicked')) {
                    $(this).prev('form').submit();
                    $(this).data('clicked', 'true').children('i').removeClass().addClass("fa fa-refresh fa-spin icon-refresh icon-spin");
                }
            });

            $('.submit').click(function (e) {
                var $form = $(this).closest('.form, form'),
                    data = $form.my_serialize(),
                    action = $form.attr('action') || $form.data('action');

                e.preventDefault();
                $.postGo(action, $.unparam(data));
            });
            $('.post-link').click(function (e) {
                e.preventDefault();
                $.postGo($(this).attr('href'), {});
            });

            $(".button", $elem).button().wrap('<span />');
            $("input[type='submit']", $elem).button();
            $("input[type='text'], input[type='password'], textarea", $elem);
            $('.container', $elem).addClass('ui-widget ui-widget-content');
            $('.config', $elem).wrap('<div />').parent().addClass('container block ui-corner-all');
        },
        updateDOM: function (update) {
            var key;
            for (key in update) {
                if (update.hasOwnProperty(key)) {
                    $(key).text(update[key]).val(update[key]);
                }
            }
        },
        SaveButton: _SaveButton,
        beforeUnload: [],
        bindBeforeUnload: function (callback) {
            COMMCAREHQ.beforeUnload.push(callback);
        },
        beforeUnloadCallback: function () {
            for (var i = 0; i < COMMCAREHQ.beforeUnload.length; i++) {
                var message = COMMCAREHQ.beforeUnload[i]();
                if (message !== null && message !== undefined) {
                    return message;
                }
            }
        }
    };
}());

$(function () {
    'use strict';
    $('.delete_link').iconify('fa fa-remove icon-remove');
    $('.new_link').iconify('fa fa-plus icon-plus');
    $('.edit_link').iconify('fa fa-pencil icon-pencil');

    $(".message").addClass('ui-state-highlight ui-corner-all').addClass("shadow");

    COMMCAREHQ.initBlock($("body"));

    $(window).bind('beforeunload', COMMCAREHQ.beforeUnloadCallback);

});
