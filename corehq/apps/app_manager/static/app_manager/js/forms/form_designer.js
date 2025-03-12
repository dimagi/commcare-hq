hqDefine("app_manager/js/forms/form_designer", [
    "jquery",
    "underscore",
    "hqwebapp/js/initial_page_data",
    "analytix/js/appcues",
    "app_manager/js/app_manager",
    "analytix/js/kissmetrix",
    "analytix/js/google",
    "app_manager/js/forms/app_notifications",
    "app_manager/js/forms/edit_form_details",
    //"js/ws4redis",    // TODO: fix or remove, webpack doesn't know where this is
    "commcarehq",
], function (
    $,
    _,
    initialPageData,
    appcues,
    appManager,
    kissmetrix,
    google,
    appNotifications,
    editFormDetails,
) {
    const FORM_TYPES = {
            REGISTRATION: "registration",
            SURVEY: "survey",
            FOLLOWUP: "followup",
        },
        trackFormEvent = function (eventType) {
            var formType = FORM_TYPES.FOLLOWUP;
            if (initialPageData.get("is_registration_form")) {
                formType = FORM_TYPES.REGISTRATION;
            } else if (initialPageData.get("is_survey")) {
                formType = FORM_TYPES.SURVEY;
            }
            appcues.trackEvent(eventType + " (" + formType + ")");
        };

    $(function () {
        var VELLUM_OPTIONS = _.extend({}, initialPageData.get("vellum_options"), {
            itemset: {
                dataSourcesFilter: function (sources) {
                    return _.filter(sources, function (source) {
                        return !source.uri || /^jr:\/\/fixture\//.test(source.uri);
                    });
                },
            },
            windowManager: {
                leftOffset: function () {
                    return $('#hq-sidebar').outerWidth() + 2;
                },
                topOffset: function () {
                    return $('#hq-navigation').outerHeight();
                },
                toggleFullScreenCallback: function (isFullscreen) {
                    var $preview = $('#js-appmanager-preview');
                    if (isFullscreen) {
                        $preview.addClass('fullscreen');
                    } else {
                        $preview.removeClass('fullscreen');
                    }
                },
            },
            csrftoken: $("#csrfTokenContainer").val(),
        });

        // Add callbacks to core, which has already been provided by the server
        VELLUM_OPTIONS.core = _.extend(VELLUM_OPTIONS.core, {
            formLoadingCallback: function () {
                $('#formdesigner').addClass('loading');
            },
            formLoadedCallback: function () {
                $('#formdesigner').removeClass('loading');
                // This code takes control of the top-left box with the form name.
                $('#formdesigner .fd-content-left .fd-head-text').before(
                    // We add an edit button that opens a modal:
                    $('#fd-hq-edit-formname-button').html()
                // and we replace the form name Vellum put there
                // with one that's translated to the app builder's currently selected language:
                ).text(initialPageData.get('form_name'));
            },
        });
        VELLUM_OPTIONS.core = _.extend(VELLUM_OPTIONS.core, {
            onFormSave: function (data) {
                appManager.updateDOM(data.update);
                $('.js-preview-toggle').removeAttr('disabled');
                if (initialPageData.get("days_since_created") === 0) {
                    kissmetrix.track.event('Saved the Form Builder within first 24 hours');
                }
                trackFormEvent(appcues.EVENT_TYPES.FORM_SAVE);
            },
            onReady: function () {
                if (initialPageData.get('vellum_debug') === 'dev') {
                    var lessErrorId = "#less-error-message\\:static-style-less-hqstyle-core",
                        lessError = $(lessErrorId);
                    if (lessError.length) {
                        console.log("hiding less error:", lessErrorId);     // eslint-disable-line no-console
                        console.log(lessError.text());                      // eslint-disable-line no-console
                        lessError.hide();
                    }
                }

                var kissmetrixTrack = function () {};
                if (initialPageData.get('days_since_created') === 0) {
                    kissmetrixTrack = function () {
                        kissmetrix.track.event(
                            'Added question in Form Builder within first 24 hours'
                        );
                    };
                }
                $("#formdesigner").vellum("get").data.core.form.on("question-create", function () {
                    kissmetrixTrack();
                    trackFormEvent(appcues.EVENT_TYPES.QUESTION_CREATE);
                });

                trackFormEvent(appcues.EVENT_TYPES.FORM_LOADED);
            },
        });

        window.CKEDITOR_BASEPATH = initialPageData.get('CKEDITOR_BASEPATH');     // eslint-disable-line no-unused-vars, no-undef

        // This unfortunate chain of import callbacks was required because
        // appcues appears to make an attempt to use the same requirejs
        // as the host app. Because we only use requirejs for some parts
        // of the app, appcues gets very confused and throws errors, likely
        // corrupting or invalidating the data in some way. By requiring
        // appcues to have completed its init prior to importing requirejs
        // or using it to incorporate vellum, these issues disappear.
        var initFormBuilder = function () {
            $.getScript(initialPageData.get("requirejs_static_url"), function () {
                define("jquery", [], function () { return window.jQuery; });
                define("jquery.bootstrap", ["jquery"], function () {});
                define("underscore", [], function () { return window._; });
                define("moment", [], function () { return window.moment; });
                define("vellum/hqAnalytics", [], function () {
                    function workflow(message) {
                        kissmetrix.track.event(message);
                    }

                    function usage(label, group, message) {
                        google.track.event(label, group, message);
                    }

                    function fbUsage(group, message) {
                        usage("Form Builder", group, message);
                    }

                    return {
                        fbUsage: fbUsage,
                        usage: usage,
                        workflow: workflow,
                    };
                });

                // TODO: deal with this
                /*require.config({
                    /* to use non-built files in HQ:
                        * clone Vellum into submodules/formdesigner
                        * Run make in that directory (requires node.js)
                        * set settings.VELLUM_DEBUG to "dev" or "dev-min"
                    */
                    /*baseUrl: initialPageData.get('requirejs_url'),
                    // handle very bad connections
                    waitSeconds: 60,
                    urlArgs: initialPageData.get('requirejs_args'),
                    paths: {
                        'jquery.vellum': 'main',
                    },
                });*/

                // TODO: deal with this
                /*require(["jquery", "jquery.vellum", "moment"], function ($) {
                    $(function () {
                        $("#edit").hide();
                        $('#hq-footer').hide();
                        $('#formdesigner').vellum(VELLUM_OPTIONS);
                        var notificationOptions = initialPageData.get("notification_options");
                        if (notificationOptions) {
                            var vellum = $("#formdesigner").vellum("get");
                            // initialize redis
                            WS4Redis({
                                uri: notificationOptions.WEBSOCKET_URI + notificationOptions.notify_facility + '?subscribe-broadcast',
                                receive_message: appNotifications.alertUser(notificationOptions.user_id, vellum.alertUser, vellum),
                                heartbeat_msg: notificationOptions.WS4REDIS_HEARTBEAT,
                            });
                        }
                    });
                });*/
                kissmetrix.track.event('Entered the Form Builder');

                appManager.setPrependedPageTitle("\u270E ", true);
                appManager.setAppendedPageTitle(gettext("Edit Form"));

                if (initialPageData.get('form_uses_cases')) {
                    // todo make this a more broadly used util, perhaps? actually add buttons to formplayer?
                    var _prependTemplateToSelector = function (selector, layout, attempts, callback) {
                        attempts = attempts || 0;
                        if ($(selector).length) {
                            var $toggleParent = $(selector);
                            $toggleParent.prepend(layout);
                            callback();
                        } else if (attempts <= 30) {
                            // give up appending element after waiting 30 seconds to load
                            setTimeout(function () {
                                _prependTemplateToSelector(selector, layout, attempts++, callback);
                            }, 1000);
                        }
                    };
                    _prependTemplateToSelector(
                        '.fd-form-actions',
                        $('#js-fd-form-actions').html(),
                        0,
                        function () {
                        }
                    );
                }

                appManager.updatePageTitle(initialPageData.get("form_name"));
                editFormDetails.initName(
                    initialPageData.get("form_name"),
                    initialPageData.reverse("edit_form_attr", "name")
                );
                editFormDetails.initComment(
                    initialPageData.get("form_comment").replace(/\\n/g, "\n"),
                    initialPageData.reverse("edit_form_attr", "comment")
                );
                editFormDetails.setUpdateCallbackFn(function (name) {
                    $('#formdesigner .fd-content-left .fd-head-text').text(name);
                    $('.variable-form_name').text(name);
                    appManager.updatePageTitle(name);
                    $('#edit-form-name-modal').modal('hide');
                    $('#edit-form-name-modal').find('.disable-on-submit').enableButton();
                });
                $('#edit-form-name-modal').koApplyBindings(editFormDetails);
                $("#edit-form-name-modal button[type='submit']").click(function () {
                    kissmetrix.track.event("Renamed form from form builder");
                });
            });
        };
        appcues.then(initFormBuilder, initFormBuilder);
    });
});
