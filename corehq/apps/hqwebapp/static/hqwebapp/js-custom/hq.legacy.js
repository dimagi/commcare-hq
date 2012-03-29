/*
 Legacy, should deal with replacing these soon?
 */
var COMMCAREHQ = (function () {
    'use strict';
    return {
        icons: {
            GRIP:   'ui-icon ui-icon-arrowthick-2-n-s',
            ADD:    'ui-icon ui-icon-plusthick',
            COPY:   'ui-icon ui-icon-copy',
            DELETE: 'ui-icon ui-icon-closethick'
        },
        initBlock: function ($elem) {
            $('.submit_on_click', $elem).click(function (e) {
                e.preventDefault();
                $(this).closest('form').submit();
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

            $('.help-link', $elem).each(function () {
                var HELP_KEY_ATTR = "data-help-key",
                    $help_link = $(this),
                    help_key = $help_link.attr(HELP_KEY_ATTR),
                    $help_text = $('.help-text[' + HELP_KEY_ATTR + '="' + help_key + '"]');
                if (!$help_text.length) {
                    $help_text = $('<div class="help-text" />').insertAfter($help_link);
                }
                $help_text.addClass('shadow');
                new InlineHelp($help_link, $help_text, help_key).init();
            });
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
                    $(key).text(update[key]);
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
        SaveButton: SaveButton
    };
}());

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
            }).button(),
            $retry: $('<span/>').text(SaveButton.message.RETRY).click(function () {
                button.fire('save');
            }).button(),
            $saving: $('<span/>').text(SaveButton.message.SAVING).button().button('disable'),
            $saved: $('<span/>').text(SaveButton.message.SAVED).button().button('disable'),
            ui: $('<div/>').css({textAlign: 'right'}),
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
                $.ajax(options);
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
            if (button.state !== 'saved') {
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
    message: {
        SAVE: 'Save',
        SAVING: 'Saving...',
        SAVED: 'Saved',
        RETRY: 'Try Again',
        ERROR_SAVING: 'There was an error saving'
    }
};