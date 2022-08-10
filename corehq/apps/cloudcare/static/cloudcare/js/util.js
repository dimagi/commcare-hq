/* global NProgress */
hqDefine('cloudcare/js/util', [
    'jquery',
    'hqwebapp/js/initial_page_data',
    'integration/js/hmac_callout',
], function (
    $,
    initialPageData,
    HMACCallout
) {
    if (!String.prototype.startsWith) {
        String.prototype.startsWith = function (searchString, position) {
            position = position || 0;
            return this.indexOf(searchString, position) === position;
        };
    }

    NProgress.configure({
        showSpinner: false,
    });

    var getFormUrl = function (urlRoot, appId, moduleId, formId, instanceId) {
        var url = urlRoot + "view/" + appId + "/modules-" + moduleId + "/forms-" + formId + "/context/";
        if (instanceId) {
            url += '?instance_id=' + instanceId;
        }
        return url;
    };

    var getSubmitUrl = function (urlRoot, appId) {
        // deprecated but still called from "touchforms-inline"
        // which is used to fill out forms from within case details view
        // use app.getSubmitUrl instead
        // todo: replace and remove
        return urlRoot + "/" + appId + "/";
    };

    var showError = function (message, $el, reportToHq) {
        if (message === undefined) {
            message = gettext("Sorry, an error occurred while processing that request.");
        }
        _show(message, $el, null, "alert alert-danger");
        if (reportToHq === undefined || reportToHq) {
            reportFormplayerErrorToHQ({
                type: 'show_error_notification',
                message: message,
            });
        }
    };

    var showWarning = function (message, $el) {
        if (message === undefined) {
            return;
        }
        _show(message, $el, null, "alert alert-danger");
    };

    var showHTMLError = function (message, $el, autoHideTime, reportToHq) {
        var htmlMessage = message = message || gettext("Sorry, an error occurred while processing that request.");
        var $container = _show(message, $el, autoHideTime, "alert alert-danger", true);
        try {
            message = $container.text();  // pull out just the text the user sees
            message = message.replace(/\s+/g, ' ').trim();
        } catch (e) {
            // leave the message as at came in if there's an issue parsing text from the container
        }
        if (reportToHq === undefined || reportToHq) {
            reportFormplayerErrorToHQ({
                type: 'show_error_notification',
                message: message,
                htmlMessage: htmlMessage,
            });
        }
    };

    var showSuccess = function (message, $el, autoHideTime, isHTML) {
        if (message === undefined) {
            message = "Success";
        }
        return _show(message, $el, autoHideTime, "alert alert-success", isHTML);
    };

    var _show = function (message, $el, autoHideTime, classes, isHTML) {
        var $container = $("<div />"),
            $alertDialog;
        $container.addClass(classes);
        if (isHTML) {
            $container.html(message);
        } else {
            $container.text(message);
        }
        // HTML errors may already have an alert dialog
        $alertDialog = $container.hasClass("alert") ? $container : $container.find('.alert');
        try {
            $alertDialog
                .prepend(
                    $("<a />")
                        .addClass("close")
                        .attr("data-dismiss", "alert")
                        .html("&times;")
                );
        } catch (e) {
            // escaping a DOM-related error from running mocha tests using grunt
            // in the command line. This passes just fine in the browser but
            // breaks only when travis runs it.
        }
        $el.append($container);
        if (autoHideTime) {
            $container.delay(autoHideTime).fadeOut(500);
        }
        return $container;
    };

    var showLoading = function () {
        NProgress.start();
    };

    var formplayerLoading = function () {
        showLoading();
    };

    var formplayerLoadingComplete = function (isError, message) {
        hideLoading();
        if (isError) {
            showError(message || gettext('Error saving!'), $('#cloudcare-notifications'));
        }
    };

    var formplayerSyncComplete = function (isError) {
        hideLoading();
        if (isError) {
            showError(
                gettext('Could not sync user data. Please report an issue if this persists.'),
                $('#cloudcare-notifications')
            );
        } else {
            showSuccess(gettext('User Data successfully synced.'), $('#cloudcare-notifications'), 5000);
        }
    };

    var clearUserDataComplete = function (isError) {
        hideLoading();
        if (isError) {
            showError(
                gettext('Could not clear user data. Please report an issue if this persists.'),
                $('#cloudcare-notifications')
            );
        } else {
            showSuccess(gettext('User data successfully cleared.'), $('#cloudcare-notifications'), 5000);
        }
    };

    var breakLocksComplete = function (isError, message) {
        hideLoading();
        if (isError) {
            showError(
                gettext('Error breaking locks. Please report an issue if this persists.'),
                $('#cloudcare-notifications')
            );
        } else {
            showSuccess(message, $('#cloudcare-notifications'), 5000);
        }
    };

    var hideLoading = function () {
        NProgress.done();
    };

    var reportFormplayerErrorToHQ = function (data) {
        hqRequire(["cloudcare/js/formplayer/app"], function (FormplayerFrontend) {
            try {
                var cloudcareEnv = FormplayerFrontend.getChannel().request('currentUser').environment;
                if (!data.cloudcareEnv) {
                    data.cloudcareEnv = cloudcareEnv || 'unknown';
                }
                $.ajax({
                    type: 'POST',
                    url: initialPageData.reverse('report_formplayer_error'),
                    data: JSON.stringify(data),
                    contentType: "application/json",
                    dataType: "json",
                    success: function () {
                        window.console.info('Successfully reported error: ' + JSON.stringify(data));
                    },
                    error: function () {
                        window.console.error('Failed to report error: ' + JSON.stringify(data));
                    },
                });
            } catch (e) {
                window.console.error(
                    "reportFormplayerErrorToHQ failed hard and there is nowhere " +
                    "else to report this error: " + JSON.stringify(data),
                    e
                );
            }
        });
    };

    function chainedRenderer(matcher, transform, target) {
        return function (tokens, idx, options, env, self) {
            var hIndex = tokens[idx].attrIndex('href');
            var matched = false;
            if (hIndex >= 0) {
                var href =  tokens[idx].attrs[hIndex][1];
                if (matcher(href)) {
                    transform(href, hIndex, tokens[idx]);
                    matched = true;
                }
            }
            if (matched) {
                var aIndex = tokens[idx].attrIndex('target');

                if (aIndex < 0) {
                    tokens[idx].attrPush(['target', target]); // add new attribute
                } else {
                    tokens[idx].attrs[aIndex][1] = target;    // replace value of existing attr
                }
            }
            return matched;
        };
    }

    var addDelegatedClickDispatch = function (linkTarget, linkDestination) {
        document.addEventListener('click', function (event) {
            if (event.target.target === linkTarget) {
                linkDestination(event.target);
                event.preventDefault();
            }
        }, true);
    };

    var injectMarkdownAnchorTransforms = function () {
        if (window.mdAnchorRender) {
            var renderers = [];

            if (initialPageData.get('dialer_enabled')) {
                renderers.push(chainedRenderer(
                    function (href) { return href.startsWith("tel://"); },
                    function (href, hIndex, anchor) {
                        var callout = href.substring("tel://".length);
                        var url = initialPageData.reverse("dialer_view");
                        anchor.attrs[hIndex][1] = url + "?callout_number=" + callout;
                    },
                    "dialer"
                ));
            }

            if (initialPageData.get('gaen_otp_enabled')) {
                renderers.push(chainedRenderer(
                    function (href) { return href.startsWith("cchq://passthrough/gaen_otp/"); },
                    function (href, hIndex, anchor) {
                        var params = href.substring("cchq://passthrough/gaen_otp/".length);
                        var url = initialPageData.reverse("gaen_otp_view");
                        anchor.attrs[hIndex][1] = url + params;
                    },
                    "gaen_otp"
                ));
                addDelegatedClickDispatch('gaen_otp',
                    function (element) {
                        HMACCallout.unsignedCallout(element, 'otp_view', true);
                    });
            }

            if (initialPageData.get('hmac_root_url')) {
                renderers.push(chainedRenderer(
                    function (href) { return href.startsWith(initialPageData.get('hmac_root_url')); },
                    function () {},
                    "hmac_callout"
                ));
                addDelegatedClickDispatch('hmac_callout',
                    function (element) {
                        HMACCallout.signedCallout(element);
                    });
            }

            window.mdAnchorRender = function (tokens, idx, options, env, self) {
                renderers.forEach(function (r) {
                    r(tokens, idx, options, env, self);
                });
                return self.renderToken(tokens, idx, options);
            };
        }
    };

    var dateTimePickerOptions = function () {
        return {
            useCurrent: false,
            showClear: true,
            showClose: true,
            showTodayButton: true,
            debug: true,
            extraFormats: ["MM/DD/YYYY"],
            icons: {
                today: 'glyphicon glyphicon-calendar',
            },
            tooltips: {     // use default text, but enable translations
                today: gettext('Go to today'),
                clear: gettext('Clear selection'),
                close: gettext('Close the picker'),
                selectMonth: gettext('Select Month'),
                prevMonth: gettext('Previous Month'),
                nextMonth: gettext('Next Month'),
                selectYear: gettext('Select Year'),
                prevYear: gettext('Previous Year'),
                nextYear: gettext('Next Year'),
                selectDecade: gettext('Select Decade'),
                prevDecade: gettext('Previous Decade'),
                nextDecade: gettext('Next Decade'),
                prevCentury: gettext('Previous Century'),
                nextCentury: gettext('Next Century'),
                pickHour: gettext('Pick Hour'),
                incrementHour: gettext('Increment Hour'),
                decrementHour: gettext('Decrement Hour'),
                pickMinute: gettext('Pick Minute'),
                incrementMinute: gettext('Increment Minute'),
                decrementMinute: gettext('Decrement Minute'),
                pickSecond: gettext('Pick Second'),
                incrementSecond: gettext('Increment Second'),
                decrementSecond: gettext('Decrement Second'),
                togglePeriod: gettext('Toggle Period'),
                selectTime: gettext('Select Time'),
            },
        };
    };

    return {
        dateTimePickerOptions: dateTimePickerOptions,
        getFormUrl: getFormUrl,
        getSubmitUrl: getSubmitUrl,
        showError: showError,
        showWarning: showWarning,
        showHTMLError: showHTMLError,
        showSuccess: showSuccess,
        clearUserDataComplete: clearUserDataComplete,
        breakLocksComplete: breakLocksComplete,
        formplayerLoading: formplayerLoading,
        formplayerLoadingComplete: formplayerLoadingComplete,
        formplayerSyncComplete: formplayerSyncComplete,
        reportFormplayerErrorToHQ: reportFormplayerErrorToHQ,
        injectMarkdownAnchorTransforms: injectMarkdownAnchorTransforms,
    };
});
