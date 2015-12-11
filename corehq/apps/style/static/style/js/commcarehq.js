var COMMCAREHQ = {};

COMMCAREHQ.icons = {
    GRIP:   'icon-resize-vertical icon-blue',
    ADD:    'icon-plus icon-blue',
    COPY:   'icon-copy icon-blue',
    DELETE: 'icon-remove icon-blue',
    PAPERCLIP: 'icon-paper-clip'
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

COMMCAREHQ.makeHqHelp = function (opts, wrap) {
    'use strict';
    wrap = wrap === undefined ? true : wrap;
    var el = $(
        '<div class="hq-help">' + 
            '<a href="#">' +
                '<i class="icon-question-sign"></i></a></div>'
    );
    for (var attr in ['content', 'title', 'html']) {
        $('a', el).data(attr, opts[attr]);
    }
    if (wrap) {
        el.hqHelp();
    }
    return el;
};

COMMCAREHQ.transformHelpTemplate = function ($template, wrap) {
    'use strict';
    var $help = COMMCAREHQ.makeHqHelp($template.data(), wrap);
    $help.insertAfter($template);
    $template.remove();
};

COMMCAREHQ.initBlock = function ($elem) {
    'use strict';
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
};

COMMCAREHQ.updateDOM = function (update) {
    'use strict';
    var key;
    for (key in update) {
        if (update.hasOwnProperty(key)) {
            $(key).text(update[key]).val(update[key]);
        }
    }
};

COMMCAREHQ.confirm = function (options) {
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
};

COMMCAREHQ.makeSaveButton = function(messageStrings, cssClass) {
    'use strict';
    var SaveButton = {
        /*
         options: {
         save: "Function to call when the user clicks Save",
         unsavedMessage: "Message to display when there are unsaved changes and the user leaves the page"
         }
         */
        init: function (options) {
            var button = {
                $save: $('<div/>').text(SaveButton.message.SAVE).click(function () {
                    button.fire('save');
                }).addClass(cssClass),
                $retry: $('<div/>').text(SaveButton.message.RETRY).click(function () {
                    button.fire('save');
                }).addClass(cssClass),
                $saving: $('<div/>').text(SaveButton.message.SAVING).addClass('btn btn-default disabled'),
                $saved: $('<div/>').text(SaveButton.message.SAVED).addClass('btn btn-default disabled'),
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
                },
                ajax: function (options) {
                    var beforeSend = options.beforeSend || function () {},
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
};

COMMCAREHQ.beforeUnload = [];

COMMCAREHQ.bindBeforeUnload = function (callback) {
    COMMCAREHQ.beforeUnload.push(callback);
};

COMMCAREHQ.beforeUnloadCallback = function () {
    for (var i = 0; i < COMMCAREHQ.beforeUnload.length; i++) {
        var message = COMMCAREHQ.beforeUnload[i]();
        if (message !== null && message !== undefined) {
            return message;
        }
    }
};

$(function () {
    'use strict';
    COMMCAREHQ.initBlock($("body"));
    $(window).bind('beforeunload', COMMCAREHQ.beforeUnloadCallback);
});
