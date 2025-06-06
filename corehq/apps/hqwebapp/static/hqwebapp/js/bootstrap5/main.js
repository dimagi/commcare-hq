import $ from "jquery";
import ko from "knockout";
import _ from "underscore";
import modernizr from "hqwebapp/js/lib/modernizr";
import initialPageData from "hqwebapp/js/initial_page_data";
import alertUser from "hqwebapp/js/bootstrap5/alert_user";
import googleAnalytics from "analytix/js/google";
import { Modal } from "bootstrap5";
import "hqwebapp/js/hq_extensions.jquery";
import "jquery.cookie/jquery.cookie";
import "jquery-textchange/jquery.textchange";

var eventize = function (that) {
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
    wrap = wrap === undefined ? true : wrap;
    var el = $(
        '<div class="hq-help">' +
            '<a href="#" tabindex="-1" data-bs-toggle="popover">' +
                '<i class="fa fa-question-circle icon-question-sign"></i></a></div>',
    );
    _.each(['content', 'title', 'html', 'placement', 'container'], function (attr) {
        $('a', el).attr('data-bs-' + attr, opts[attr]);
    });
    if (wrap) {
        el.hqHelp();
    }
    return el;
};

var transformHelpTemplate = function ($template, wrap) {
    if ($template.data()) {
        var $help = makeHqHelp($template.data(), wrap);
        $help.insertAfter($template);
        $template.remove();
    }
};

ko.bindingHandlers.makeHqHelp = {
    update: function (element, valueAccessor) {
        var opts = valueAccessor(),
            name = ko.utils.unwrapObservable(opts.name || $(element).data('title')),
            description = ko.utils.unwrapObservable(opts.description || $(element).data('content')),
            placement = ko.utils.unwrapObservable(opts.placement || $(element).data('placement')),
            format = ko.utils.unwrapObservable(opts.format);
        $(element).find('.hq-help').remove();
        makeHqHelp({
            title: name,
            content: description,
            html: format === 'html',
            placement: placement || 'right',
        }).appendTo(element);
    },
};

ko.bindingHandlers.runOnInit = {
    // suggestion from https://github.com/knockout/knockout/issues/2446 to use
    // instead of an anonymous template
    init: function (elem, valueAccessor) {
        valueAccessor();
    },
};
ko.virtualElements.allowedBindings.runOnInit = true;

ko.bindingHandlers.allowDescendantBindings = {
    // fixes an issue where we try to apply bindings to a parent element
    // that has a child element with existing bindings.
    // see: https://github.com/knockout/knockout/issues/1922
    init: function (elem, valueAccessor) {
        // Let bindings proceed as normal *only if* my value is false
        var shouldAllowBindings = ko.unwrap(valueAccessor());
        return { controlsDescendantBindings: !shouldAllowBindings };
    },
};
ko.virtualElements.allowedBindings.allowDescendantBindings = true;

var initBlock = function ($elem) {

    $('.submit').click(function (e) {
        var $form = $(this).closest('.form, form'),
            data = $form.find('[name]').serialize(),
            action = $form.attr('action') || $form.data('action');

        e.preventDefault();
        $.postGo(action, $.unparam(data));
    });

    $("input[type='text'], input[type='password'], textarea", $elem);
    $('.config', $elem).wrap('<div />').parent().addClass('container block ui-corner-all');

    $('.hq-help-template').each(function () {
        transformHelpTemplate($(this), true);
    });
};

var updateDOM = function (update) {
    var key;
    for (key in update) {
        if (Object.prototype.hasOwnProperty.call(update, key)) {
            $(key).text(update[key]).val(update[key]);
        }
    }
};

var makeSaveButton = function (messageStrings, cssClass, barClass) {
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
                $saving: $('<div/>').text(SaveButton.message.SAVING).addClass('btn btn-primary disabled'),
                $saved: $('<div/>').text(SaveButton.message.SAVED).addClass('btn btn-primary disabled'),
                ui: $('<div/>').addClass('float-end savebtn-bar ' + barClass),
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
                    _.each(BAR_STATE, function (v) {
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
                    options.success = function () {
                        that.setState(that.nextState);
                        success.apply(this, arguments);
                    };
                    options.error = function (data) {
                        that.nextState = null;
                        that.setState('retry');
                        var customError = data.responseText;
                        if (data.responseJSON) {
                            if (data.responseJSON.message) {
                                customError = data.responseJSON.message;
                            } else if (data.responseJSON.messages && data.responseJSON.messages.length) {
                                if (data.responseJSON.messages.length === 1) {
                                    customError = _.template("<%- m %>")({m: data.responseJSON.messages[0]});
                                } else {
                                    customError = _.template("<ul><%= errors %></ul>")({
                                        errors: data.responseJSON.messages.map(function (m) {
                                            return _.template("<li><%- m %></li>")({m: m});
                                        }).join(""),
                                    });
                                }
                            }
                        }
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
                },
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
                    var stillAttached = lastParent.tagName.toLowerCase() === 'html';
                    if (button.state !== 'saved' && stillAttached) {
                        if ($('.js-unhide-on-unsaved').length > 0) {$('.js-unhide-on-unsaved').removeClass('hide');}
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
                            success: options.success,
                        });
                    },
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
        message: messageStrings,
    };

    return SaveButton;
};

var SaveButton = makeSaveButton({
    SAVE: gettext("Save"),
    SAVING: gettext("Saving..."),
    SAVED: gettext("Saved"),
    RETRY: gettext("Try Again"),
    ERROR_SAVING: gettext("There was an error saving"),
}, 'btn btn-primary');

var DeleteButton = makeSaveButton({
    SAVE: gettext("Delete"),
    SAVING: gettext("Deleting..."),
    SAVED: gettext("Deleted"),
    RETRY: gettext("Try Again"),
    ERROR_SAVING: gettext("There was an error deleting"),
}, 'btn btn-danger', 'savebtn-bar-danger');

ko.bindingHandlers.saveButton = {
    init: function (element, getSaveButton) {
        getSaveButton().ui.appendTo(element);
    },
};

ko.bindingHandlers.saveButton2 = {
    init: function (element, valueAccessor, allBindingsAccessor) {
        var saveOptions = allBindingsAccessor().saveOptions,
            state = valueAccessor(),
            saveButton;

        saveButton = SaveButton.init({
            save: function () {
                saveButton.ajax(saveOptions());
            },
        });
        $(element).css('vertical-align', 'top').css('display', 'inline-block');

        saveButton.ui.appendTo(element);
        element.saveButton = saveButton;
        saveButton.on('state:change', function () {
            state(saveButton.state);
        });
    },
    update: function (element, valueAccessor) {
        var state = ko.utils.unwrapObservable(valueAccessor());
        element.saveButton.setStateWhenReady(state);
    },
};

ko.bindingHandlers.deleteButton = {
    init: function (element, valueAccessor, allBindingsAccessor) {
        var saveOptions = allBindingsAccessor().saveOptions,
            state = valueAccessor(),
            deleteButton;

        deleteButton = DeleteButton.init({
            save: function () {
                deleteButton.ajax(saveOptions());
            },
        });
        $(element).css('vertical-align', 'top').css('display', 'inline-block');
        deleteButton.ui.appendTo(element);
        element.deleteButton = deleteButton;
        deleteButton.on('state:change', function () {
            state(deleteButton.state);
        });
    },
    update: function (element, valueAccessor) {
        var state = ko.utils.unwrapObservable(valueAccessor());
        element.deleteButton.setStateWhenReady(state);
    },
};

$(function () {
    initBlock($("body"));

    var trialModalElement = $('#modalTrial30Day'),
        trialModal;
    if (trialModalElement.length) {
        trialModal = new Modal(trialModalElement);
        trialModal.show();
    }

    $(document).on('click', '.track-usage-link', function (e) {
        var $link = $(e.currentTarget),
            data = $link.data();
        googleAnalytics.track.click($link, data.category, data.action, data.label, data.value);
    });

    $(document).on('click', '.mainmenu-tab a', function (e) {
        var data = $(e.currentTarget).closest(".mainmenu-tab").data();
        if (data.category && data.action) {
            googleAnalytics.track.event(data.category, data.action, data.label);
        }
    });

    $(document).on('click', '.post-link', function (e) {
        e.preventDefault();
        $.postGo($(this).attr('href'), {});
    });

    // Maintenance alerts
    var $maintenance = $('.alert-maintenance');
    if ($maintenance.length) {
        var alertCookie = 'alerts_maintenance';
        var closedAlerts = $.cookie(alertCookie) ? JSON.parse($.cookie(alertCookie)) : [];

        var viewedDomainAlertsCookie = 'viewed_domain_alerts';
        var viewedDomainAlerts = $.cookie(viewedDomainAlertsCookie) ? JSON.parse($.cookie(viewedDomainAlertsCookie)) : [];

        var setUpAlert = function (alert, alertList, alertCookieName) {
            var id = $(alert).data('id');
            if (!alertList.includes(id)) {
                $(alert).removeClass('hide');
                $(alert).on('click', '.close', function () {
                    alertList.push(id);
                    $.cookie(alertCookieName, JSON.stringify(alertList), { expires: 7, path: '/', secure: initialPageData.get('secure_cookies') });
                });
            }
        };
        _.each($maintenance,
            function (alert) {
                if ($(alert).data('created-by-domain')) {
                    setUpAlert(alert, viewedDomainAlerts, viewedDomainAlertsCookie);
                } else {
                    setUpAlert(alert, closedAlerts, alertCookie);
                }
            },
        );
    }

    function unsupportedBrowser() {
        // Try to filter out legacy browsers like Internet Explorer.
        // We don't explicitly rely on SVG SMIL animation,
        // but it's a decent test for avoiding legacy IE.
        // TODO: Find more granular tests for what the website requires
        return !modernizr.smil;
    }

    var $unsupportedBrowser = $("#unsupported-browser");
    if (unsupportedBrowser()) {
        $unsupportedBrowser.removeClass('hide'); // todo remove after bootstrap5 migration
        $unsupportedBrowser.removeClass('d-none');
    }

    // EULA modal
    var eulaCookie = "gdpr_rollout";
    if (!$.cookie(eulaCookie)) {
        var eulaModalElement = $("#eulaModal"),
            eulaModal;
        if (eulaModalElement.length) {
            eulaModal = new Modal(eulaModalElement, {
                keyboard: false,
                backdrop: 'static',
            });
            $("body").addClass("has-eula");
            $("#eula-agree").click(function () {
                $(this).disableButton();
                $.ajax({
                    url: initialPageData.reverse("agree_to_eula"),
                    method: "POST",
                    success: function () {
                        eulaModal.hide();
                        $("body").removeClass("has-eula");
                    },
                    error: function (xhr) {
                        // if we got a 403 it may be due to two-factor settings.
                        // force a page reload
                        // https://dimagi-dev.atlassian.net/browse/SAAS-10785
                        if (xhr.status === 403) {
                            location.reload();
                        } else {
                            // do nothing, user will get the popup again on next page load
                            $("body").removeClass("has-eula");
                        }
                    },
                });
            });
        }
    }

    // CDA modal
    _.each($(".remote-modal"), function (modal) {
        var remoteModalElement = $(modal),
            remoteModal;
        if (remoteModalElement.length === 0) {
            return;
        }
        remoteModal = new Modal(remoteModalElement);
        remoteModal.on("show.bs.modal", function () {
            $(this).find(".fetched-data").load($(this).data("url"));
        });
        if (remoteModalElement.data("showOnPageLoad")) {
            remoteModal.show();
        }
    });
});

var capitalize = function (string) {
    return string.charAt(0).toUpperCase() + string.substring(1).toLowerCase();
};

export default {
    eventize: eventize,
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
