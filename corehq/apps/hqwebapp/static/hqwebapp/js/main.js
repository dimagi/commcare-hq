hqDefine('hqwebapp/js/main', [
    "jquery",
    "underscore",
    "hqwebapp/js/alert_user",
], function(
    $,
    _,
    alertUser
) {
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

    var makeHqHelp = function (opts, wrap) {
        'use strict';
        wrap = wrap === undefined ? true : wrap;
        var el = $(
            '<div class="hq-help">' + 
                '<a href="#" tabindex="-1">' +
                    '<i class="fa fa-question-circle icon-question-sign"></i></a></div>'
        );
        _.each(['content', 'title', 'html', 'placement', 'container'], function(attr) {
            $('a', el).data(attr, opts[attr]);
        });
        if (wrap) {
            el.hqHelp();
        }
        return el;
    };

    var transformHelpTemplate = function ($template, wrap) {
        'use strict';
        if ($template.data()) {
            var $help = makeHqHelp($template.data(), wrap);
            $help.insertAfter($template);
            $template.remove();
        }
    };

    var initBlock = function ($elem) {
        'use strict';

        $('.submit').click(function (e) {
            var $form = $(this).closest('.form, form'),
                data = $form.find('[name]').serialize(),
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

        $('.hq-help-template').each(function () {
            transformHelpTemplate($(this), true);
        });
    };

    var updateDOM = function (update) {
        'use strict';
        var key;
        for (key in update) {
            if (update.hasOwnProperty(key)) {
                $(key).text(update[key]).val(update[key]);
            }
        }
    };

    var makeSaveButton = function(messageStrings, cssClass, barClass) {
        'use strict';
        var BAR_STATE = {
            SAVE: 'savebtn-bar-save',
            SAVING: 'savebtn-bar-saving',
            SAVED: 'savebtn-bar-saved',
            RETRY: 'savebtn-bar-retry',
        };
        barClass = barClass || '';
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
                    ui: $('<div/>').addClass('pull-right savebtn-bar ' + barClass),
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
                        var buttonUi = this.ui;
                        _.each(BAR_STATE, function (v, k) {
                            buttonUi.removeClass(v);
                        });
                        if (state === 'save') {
                            this.ui.addClass(BAR_STATE.SAVE);
                            this.ui.append(this.$save);
                        } else if (state === 'saving') {
                            this.ui.addClass(BAR_STATE.SAVING);
                            this.ui.append(this.$saving);
                        } else if (state === 'saved') {
                            this.ui.addClass(BAR_STATE.SAVED);
                            this.ui.append(this.$saved);
                        } else if (state === 'retry') {
                            this.ui.addClass(BAR_STATE.RETRY);
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
                            var customError = ((data.responseJSON && data.responseJSON.message) ? data.responseJSON.message : data.responseText);
                            if (customError.indexOf('<head>') > -1) {
                                // this is sending back a full html page, likely login, so no error message.
                                customError = null;
                            }
                            alertUser.alert_user(customError || SaveButton.message.ERROR_SAVING, 'danger');
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
                $(window).on('beforeunload', function () {
                    var lastParent = button.ui.parents()[button.ui.parents().length - 1];
                    if (lastParent) {
                        var stillAttached = lastParent.tagName.toLowerCase() == 'html';
                        if (button.state !== 'saved' && stillAttached) {
                            if ($('.js-unhide-on-unsaved').length > 0) $('.js-unhide-on-unsaved').removeClass('hide');
                            return options.unsavedMessage || "";
                        }
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
                _.defer(function () {
                    $form.find('*').change(fireChange);
                    $form.find('input, textarea').on('textchange', fireChange);
                });
                return button;
            },
            message: messageStrings
        };

        return SaveButton;
    };

    var SaveButton = makeSaveButton({
        SAVE: django.gettext("Save"),
        SAVING: django.gettext("Saving..."),
        SAVED: django.gettext("Saved"),
        RETRY: django.gettext("Try Again"),
        ERROR_SAVING: django.gettext("There was an error saving")
    }, 'btn btn-success');

    var DeleteButton = makeSaveButton({
        SAVE: django.gettext("Delete"),
        SAVING: django.gettext("Deleting..."),
        SAVED: django.gettext("Deleted"),
        RETRY: django.gettext("Try Again"),
        ERROR_SAVING: django.gettext("There was an error deleting")
    }, 'btn btn-danger', 'savebtn-bar-danger');

    var beforeUnload = [];
    var bindBeforeUnload = function (callback) {
        beforeUnload.push(callback);
    };
    var beforeUnloadCallback = function () {
        for (var i = 0; i < beforeUnload.length; i++) {
            var message = beforeUnload[i]();
            if (message !== null && message !== undefined) {
                return message;
            }
        }
    };

    $(function () {
        'use strict';
        $(window).on('beforeunload', beforeUnloadCallback);
        initBlock($("body"));

        $('#modalTrial30Day').modal('show');

        $(document).on('click', '.track-usage-link', function(e) {
            var $link = $(e.currentTarget),
                data = $link.data();
            window.analytics.trackUsageLink($link, data.category, data.action, data.label, data.value);
        });

        $(document).on('click', '.mainmenu-tab a', function(e) {
            if (typeof(ga) !== 'undefined') {
                var data = $(e.currentTarget).closest(".mainmenu-tab").data();
                if (data.category && data.action) {
                    ga('send', 'event', data.category, data.action, data.label);
                }
            }
        });

        // EULA and CDA modals
        _.each($(".remote-modal"), function(modal) {
            var $modal = $(modal);
            $modal.on("show show.bs.modal", function() {
                $(this).find(".fetched-data").load($(this).data("url"));
            });
            if ($modal.data("showOnPageLoad")) {
                $modal.modal('show');
            }
        });
    });

    var capitalize = function(string) {
        return string.charAt(0).toUpperCase() + string.substring(1).toLowerCase();
    };

    return {
        beforeUnloadCallback: beforeUnloadCallback,
        eventize: eventize,
        icons: {
            GRIP: 'icon-resize-vertical icon-blue fa fa-arrows-v',
            ADD: 'icon-plus icon-blue fa fa-plus',
            DELETE: 'icon-remove icon-blue fa fa-remove',
        },
        initBlock: initBlock,
        initDeleteButton: DeleteButton.init,
        initSaveButton: SaveButton.init,
        makeSaveButton: makeSaveButton,
        SaveButton: SaveButton,
        initSaveButtonForm: SaveButton.initForm,
        makeHqHelp: makeHqHelp,
        transformHelpTemplate: transformHelpTemplate,
        updateDOM: updateDOM,
        capitalize: capitalize,
    };
});
