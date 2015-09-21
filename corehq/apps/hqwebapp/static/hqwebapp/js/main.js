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

var SaveButton = {
    /*
        options: {
            save: "Function to call when the user clicks Save",
            unsavedMessage: "Message to display when there are unsaved changes and the user leaves the page"
        }
    */
    init: function (options) {
        var button = {
            disabled: false,
            $save: $('<span/>').text(SaveButton.message.SAVE).click(function () {
                button.fire('save');
            }).addClass('btn btn-success'),
            $retry: $('<span/>').text(SaveButton.message.RETRY).click(function () {
                button.fire('save');
            }).addClass('btn btn-success'),
            $saving: $('<span/>').text(SaveButton.message.SAVING).prepend('<i class="icon-refresh icon-spin"></i> ').addClass('btn disabled'),
            $saved: $('<span/>').text(SaveButton.message.SAVED).addClass('btn disabled'),
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
                options.beforeSend = function () {
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
                    responseText = data.responseText || '';
                    alert(SaveButton.message.ERROR_SAVING + '\n' +  data.responseText);
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


var COMMCAREHQ = (function () {
    'use strict';
    return {
        icons: {
            GRIP:   'icon-resize-vertical icon-blue',
            ADD:    'icon-plus icon-blue',
            COPY:   'icon-copy icon-blue',
            DELETE: 'icon-remove icon-blue',
            PAPERCLIP: 'icon-paper-clip'
        },
        makeHqHelp: function (opts, wrap) {
            wrap = wrap === undefined ? true : wrap;
            var el = $(
                '<div class="hq-help">' + 
                    '<a href="#">' +
                        '<i class="icon-question-sign"></i></a></div>'
                ),
                attrs = ['content', 'title', 'placement'];

            attrs.map(function (attr) {
                el.find('a').data(attr, opts[attr]);
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
        initBlock: function ($elem) {
            $('.submit_on_click', $elem).on("click", function (e) {
                e.preventDefault();
                if (!$(this).data('clicked')) {
                    $(this).prev('form').submit();
                    $(this).data('clicked', 'true').children('i').removeClass().addClass("icon-refresh icon-spin");
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

            // trick to give a select menu an initial value
            $('select[data-value]', $elem).each(function () {
                var val = $(this).attr('data-value');
                if (val) {
                    $(this).find('option').removeAttr('selected');
                    $(this).find('option[value="' + val + '"]').attr('selected', 'true');
                }
            });

            $(".button", $elem).button().wrap('<span />');
            $("input[type='submit']", $elem).button();
            $("input[type='text'], input[type='password'], textarea", $elem);
            $('.container', $elem).addClass('ui-widget ui-widget-content');
            $('.config', $elem).wrap('<div />').parent().addClass('container block ui-corner-all');

            $('.confirm-submit', $elem).click(function () {
                var $form = $(this).closest('form'),
                    message = $form.data('message') || function () {
                        $(this).append($form.find('.dialog-message').html());
                    },
                    title = $form.data('title');
                COMMCAREHQ.confirm({
                    title: title,
                    message: message,
                    ok: function () {
                        $form.submit();
                    }
                });
                return false;
            });
        },
        updateDOM: function (update) {
            var key;
            for (key in update) {
                if (update.hasOwnProperty(key)) {
                    $(key).text(update[key]).val(update[key]);
                }
            }
        },
        confirm: function (options) {
            var title = options.title,
                message = options.message || "",
                onOpen = options.open || function () {},
                onOk = options.ok,
                $dialog = $('<div/>');

            if (typeof message === "function") {
                message.apply($dialog);
            } else if (message) {
                $dialog.text(message);
            }
            $dialog.dialog({
                title: title,
                modal: true,
                resizable: false,
                open: function () {
                    onOpen.apply($dialog);
                },
                buttons: [{
                    text: "Cancel",
                    click: function () {
                        $(this).dialog('close');
                    }
                }, {
                    text: "OK",
                    click: function () {
                        $(this).dialog('close');
                        onOk.apply($dialog);
                    }
                }]
            });
        },
        SaveButton: SaveButton,
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
    $('.delete_link').iconify('icon-remove');
    $(".delete_link").addClass("dialog_opener");
    $(".delete_dialog").addClass("dialog");
    $('.new_link').iconify('icon-plus');
    $('.edit_link').iconify('icon-pencil');

    $(".message").addClass('ui-state-highlight ui-corner-all').addClass("shadow");

    COMMCAREHQ.initBlock($("body"));

    $(window).bind('beforeunload', COMMCAREHQ.beforeUnloadCallback);

});

// thanks to http://stackoverflow.com/questions/1149454/non-ajax-get-post-using-jquery-plugin
// thanks to http://stackoverflow.com/questions/1131630/javascript-jquery-param-inverse-function#1131658

(function () {
    'use strict';
    $.extend({
        getGo: function (url, params) {
            document.location = url + '?' + $.param(params);
        },
        postGo: function (url, params) {
            var $form = $("<form>")
                .attr("method", "post")
                .attr("action", url);
            $.each(params, function (name, value) {
                $("<input type='hidden'>")
                    .attr("name", name)
                    .attr("value", value)
                    .appendTo($form);
            });
            $form.appendTo("body");
            $form.submit();
        },
        unparam: function (value) {
            var
            // Object that holds names => values.
                params = {},
            // Get query string pieces (separated by &)
                pieces = value.split('&'),
            // Temporary variables used in loop.
                pair, i, l;

            // Loop through query string pieces and assign params.
            for (i = 0, l = pieces.length; i < l; i += 1) {
                pair = pieces[i].split('=', 2);
                // Repeated parameters with the same name are overwritten. Parameters
                // with no value get set to boolean true.
                params[decodeURIComponent(pair[0])] = (pair.length === 2 ?
                    decodeURIComponent(pair[1].replace(/\+/g, ' ')) : true);
            }

            return params;
        }
    });

    $.fn.closest_form = function () {
        return this.closest('form, .form');
    };
    $.fn.my_serialize = function () {
        var data = this.find('[name]').serialize();
        return data;
    };

}());
