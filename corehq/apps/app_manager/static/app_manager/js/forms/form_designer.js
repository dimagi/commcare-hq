/* globals hqDefine, hqImport, define, require, form_tour_start, WS4Redis, django */
hqDefine("app_manager/js/forms/form_designer", function() {
    var initial_page_data = hqImport("hqwebapp/js/initial_page_data").get,
        FORM_TYPES = {
            REGISTRATION: "registration",
            SURVEY: "survey",
            FOLLOWUP: "followup",
        },
        formType = function () {
            if (initial_page_data("is_registration_form")) {
                return FORM_TYPES.REGISTRATION;
            }
            if (initial_page_data("is_survey")) {
                return FORM_TYPES.SURVEY;
            }
            return FORM_TYPES.FOLLOWUP;
        },
        popupFormPreviewTimeout;

    $(function() {
        var VELLUM_OPTIONS = _.extend({}, initial_page_data("vellum_options"), {
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
            formLoadingCallback: function() {
                $('#formdesigner').addClass('loading');
            },
            formLoadedCallback: function() {
                $('#formdesigner').removeClass('loading');
                $('#formdesigner .fd-content-left .fd-head-text').before(
                    $('#fd-hq-edit-formname-button').html()
                );
            },
        });
        VELLUM_OPTIONS.core = _.extend(VELLUM_OPTIONS.core, {
            onFormSave: function(data) {
                var app_manager = hqImport('app_manager/js/app_manager');
                app_manager.updateDOM(data.update);
                $('.js-preview-toggle').removeAttr('disabled');
                if (initial_page_data("days_since_created") === 0) {
                    hqImport('analytix/js/kissmetrix').track.event('Saved the Form Builder within first 24 hours');
                }
                var appcues = hqImport('analytix/js/appcues');
                appcues.trackEvent(
                    appcues.EVENT_TYPE.FORM_SAVE, { formType: formType() }
                );
            },
            onReady: function() {
                if (initial_page_data('vellum_debug') === 'dev') {
                    var less_error_id = "#less-error-message\\:static-style-less-hqstyle-core",
                        less_error = $(less_error_id);
                    if (less_error.length) {
                        console.log("hiding less error:", less_error_id);
                        console.log(less_error.text());
                        less_error.hide();
                    }
                }
                if (initial_page_data('guided_tour')) {
                    form_tour_start();
                }
                var kissmetrixTrack = function() {};
                if (initial_page_data('days_since_created') === 0) {
                    kissmetrixTrack = function() {
                        hqImport('analytix/js/kissmetrix').track.event(
                            'Added question in Form Builder within first 24 hours'
                        );
                    };
                }
                $("#formdesigner").vellum("get").data.core.form.on("question-create", function() {
                    kissmetrixTrack();
                    var appcues = hqImport('analytix/js/appcues');
                    appcues.trackEvent(
                        appcues.EVENT_TYPE.QUESTION_CREATE, { formType: formType() }
                    );
                });
            },
        });

        CKEDITOR_BASEPATH = initial_page_data('CKEDITOR_BASEPATH');

        define("jquery", [], function () { return window.jQuery; });
        define("jquery.bootstrap", ["jquery"], function () {});
        define("underscore", [], function () { return window._; });
        define("moment", [], function () { return window.moment; });
        define("vellum/hqAnalytics", [], function () {
            function workflow(message) {
                hqImport('analytix/js/kissmetrix').track.event(message);
            }

            function usage(label, group, message) {
                hqImport('analytix/js/google').track.event(label, group, message);
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

        require.config({
            /* to use non-built files in HQ:
                * clone Vellum into submodules/formdesigner
                * Run make in that directory (requires node.js)
                * set settings.VELLUM_DEBUG to "dev" or "dev-min"
            */
            baseUrl: initial_page_data('requirejs_url'),
            // handle very bad connections
            waitSeconds: 60,
            urlArgs: initial_page_data('requirejs_args'),
            paths: {
                'jquery.vellum': 'main',
            },
        });

        require(["jquery", "jquery.vellum", "moment"], function ($) {
            $(function () {
                $("#edit").hide();
                $('#hq-footer').hide();
                $('#formdesigner').vellum(VELLUM_OPTIONS);

                var notification_options = initial_page_data("notification_options");
                if (notification_options) {
                    var notifications = hqImport('app_manager/js/forms/app_notifications'),
                        vellum = $("#formdesigner").vellum("get");
                    // initialize redis
                    WS4Redis({
                        uri: notification_options.WEBSOCKET_URI + notification_options.notify_facility + '?subscribe-broadcast',
                        receive_message: notifications.alertUser(notification_options.user_id, vellum.alertUser, vellum),
                        heartbeat_msg: notification_options.WS4REDIS_HEARTBEAT,
                    });
                }
            });
        });
        hqImport('analytix/js/kissmetrix').track.event('Entered the Form Builder');

        hqImport('app_manager/js/app_manager').setAppendedPageTitle(django.gettext("Edit Form"));

        if (initial_page_data('form_uses_cases')) {
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
                $('#js-fd-manage-case').html(),
                0,
                function () {
                }
            );
        }

        var reverse = hqImport("hqwebapp/js/initial_page_data").reverse,
            editDetails = hqImport('app_manager/js/forms/edit_form_details');
        editDetails.initName(
            initial_page_data("form_name"),
            reverse("edit_form_attr", "name")
        );
        editDetails.initComment(
            initial_page_data("form_comment").replace(/\\n/g, "\n"),
            reverse("edit_form_attr", "comment")
        );
        editDetails.setUpdateCallbackFn(function (name) {
            $('#formdesigner .fd-content-left .fd-head-text').text(name);
            $('.variable-form_name').text(name);
            hqImport('app_manager/js/app_manager').updatePageTitle(name);
            $('#edit-form-name-modal').modal('hide');
            $('#edit-form-name-modal').find('.disable-on-submit').enableButton();
        });
        $('#edit-form-name-modal').koApplyBindings(editDetails);
        $("#edit-form-name-modal button[type='submit']").click(function() {
            hqImport('analytix/js/kissmetrix').track.event("Renamed form from form builder");
        });

        // if they are in the guided tour, the preview should pop out after 3 minutes
        // TODO: improve usage.
        // Should perhaps be 3 minutes in session rather than 3 minutes on page?
        if (initial_page_data("guided_tour")) {
            popupFormPreviewTimeout = setTimeout(function () {
                hqImport("app_manager/js/preview_app").forceShowPreview();
                var appcues = hqImport('analytix/js/appcues');
                appcues.trackEvent(appcues.EVENT_TYPES.POPPED_OUT_PREVIEW);
            }, 1000 * 60 * 3);  // 3 minutes
        }
    });
});
