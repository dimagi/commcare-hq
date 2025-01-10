'use strict';
hqDefine('cloudcare/js/utils', [
    'jquery',
    'underscore',
    'backbone.marionette',
    'moment',
    'hqwebapp/js/initial_page_data',
    'hqwebapp/js/tempus_dominus',
    "hqwebapp/js/toggles",
    "cloudcare/js/formplayer/constants",
    "cloudcare/js/formplayer/layout/views/progress_bar",
    'nprogress/nprogress',
    'sentry_browser',
    "cloudcare/js/formplayer/users/models",
], function (
    $,
    _,
    Marionette,
    moment,
    initialPageData,
    hqTempusDominus,
    toggles,
    constants,
    ProgressBar,
    NProgress,
    Sentry,
    UsersModels
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

    var showError = function (message, $el, reportToHq, additionalData) {
        message = getErrorMessage(message);
        // Make message more user friendly since html isn't useful here
        if (message.includes('500') && message.includes('<!DOCTYPE html>')) {
            message = 'Sorry, something went wrong. Please try again in a few minutes. ' +
            'If this problem persists, please report it to CommCare Support.';
        }
        _show(message, $el, null, "alert-danger");
        if (reportToHq === undefined || reportToHq) {
            reportFormplayerErrorToHQ(Object.assign({
                type: 'show_error_notification',
                message: message,
            }, (additionalData || {})));
        }
    };

    var showWarning = function (message, $el) {
        if (message === undefined) {
            return;
        }
        _show(message, $el, null, "alert-danger");
    };

    var showHTMLError = function (message, $el, autoHideTime, reportToHq) {
        var htmlMessage = message = getErrorMessage(message);
        var $container = _show(message, $el, autoHideTime, "alert-danger", true);
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

    var getErrorMessage = function (message) {
        message = message || constants.GENERIC_ERROR;
        const originalLen = message.length;
        message = message.substr(0, 500);
        if (message.length < originalLen) {
            message += " ...";
        }
        return message;
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
        $container.addClass("alert");
        $container.addClass("alert-dismissible");
        $container.addClass(classes);
        if (isHTML) {
            $container.html(message);
        } else {
            $container.text(message);
        }
        // HTML errors may already have an alert dialog
        $alertDialog = $container.hasClass("alert") ? $container : $container.find('.alert');
        try {
            $alertDialog.append($("<button />").addClass("btn-close").attr("data-bs-dismiss", "alert").attr("aria-label", gettext("Close")));
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

    var shouldShowLoading = function () {
        const answerInProgress = (sessionStorage.answerQuestionInProgress && JSON.parse(sessionStorage.answerQuestionInProgress));
        const validationInProgress = (sessionStorage.validationInProgress && JSON.parse(sessionStorage.validationInProgress));
        return !answerInProgress && !validationInProgress;
    };

    var getRegionContainer = function () {
        const RegionContainer = Marionette.View.extend({
            el: "#main-container",

            regions: {
                main: "#menu-region",
                loadingProgress: "#formplayer-progress-container",
                breadcrumb: "#breadcrumb-region",
                persistentCaseTile: "#persistent-case-tile",
                restoreAsBanner: '#restore-as-region',
                mobileRestoreAsBanner: '#mobile-restore-as-region',
                sidebar: '#sidebar-region',
                persistentMenu: "#persistent-menu-region",
            },
        });

        return new RegionContainer();
    };

    var showProminentLoading = function () {
        import("cloudcare/js/formplayer/app").then(function (FormplayerFrontend) {
            setTimeout(function () {
                const formplayerQueryInProgress = sessionStorage.formplayerQueryInProgress && JSON.parse(sessionStorage.formplayerQueryInProgress);
                if (formplayerQueryInProgress) {
                    const progressView = new ProgressBar({
                        progressMessage: gettext("Loading..."),
                    });
                    if (!FormplayerFrontend.regions) {
                        FormplayerFrontend.regions = getRegionContainer();
                    }
                    $('#breadcrumb-region').css('z-index', '0');
                    const loadingElement = FormplayerFrontend.regions.getRegion('loadingProgress');
                    loadingElement.show(progressView);
                    let currentProgress = 10;
                    progressView.progressEl.find('.progress').css("height", "12px");
                    progressView.progressEl.find('.progress-container').css("width", "50%");
                    progressView.progressEl.find('.progress-title h1').css("font-size", "25px");
                    progressView.progressEl.find('#formplayer-progress ').css("background-color", "rgba(255, 255, 255, 0.7)");
                    progressView.setProgress(currentProgress, 100, 200);
                    sessionStorage.progressIncrementInterval = setInterval(function () {
                        if (currentProgress <= 100) {
                            progressView.setProgress(currentProgress, 100, 200);
                            currentProgress += 1;
                        }
                    }, 250);
                }
            }, constants.MILLIS_BEFORE_SHOW_LOADING);
        });
    };

    var showLoading = function () {
        if (toggles.toggleEnabled('USE_PROMINENT_PROGRESS_BAR')) {
            showProminentLoading();
        } else {
            NProgress.start();
        }
    };

    var formplayerLoading = function () {
        sessionStorage.formplayerQueryInProgress = true;
        if (shouldShowLoading()) {
            showLoading();
        }
    };

    var formplayerLoadingComplete = function (isError, message) {
        sessionStorage.formplayerQueryInProgress = false;
        hideLoading();
        if (isError) {
            showError(message || gettext('Error saving!'), $('#cloudcare-notifications'));
        }
    };

    var updateScreenReaderNotification = function (notificationText) {
        $('#sr-notification-region').html("<p>" + notificationText + "</p>");
    };

    var formplayerSyncComplete = function (isError) {
        hideLoading();
        if (isError) {
            const notificationText = gettext('Could not sync user data. Please report an issue if this persists.');
            showError(notificationText, $('#cloudcare-notifications'));
            updateScreenReaderNotification(notificationText);
        } else {
            const notificationText = gettext('User Data successfully synced.');
            showSuccess(notificationText, $('#cloudcare-notifications'), 5000);
            updateScreenReaderNotification(notificationText);
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
        if (toggles.toggleEnabled('USE_PROMINENT_PROGRESS_BAR')) {
            $('#breadcrumb-region').css('z-index', '');
            clearInterval(sessionStorage.progressIncrementInterval);
            import("cloudcare/js/formplayer/app").then(function (FormplayerFrontend) {
                const progressView = FormplayerFrontend.regions.getRegion('loadingProgress').currentView;
                if (progressView) {
                    progressView.setProgress(100, 100, 200);
                    setTimeout(function () {
                        FormplayerFrontend.regions.getRegion('loadingProgress').empty();
                    }, 250);
                }
            });
        } else {
            NProgress.done();
        }
    };

    function getSentryMessage(data) {
        // replace IDs with a placeholder
        let message = data.message;
        if (message) {
            message = message.replace("/[a-f0-9-]{7,}/gi", "[...]");
        } else {
            message = "Unknown Error";
        }
        return "[WebApps] " + message;
    }

    var reportFormplayerErrorToHQ = function (data) {
        try {
            var cloudcareEnv = UsersModels.getCurrentUser().environment;
            if (!data.cloudcareEnv) {
                data.cloudcareEnv = cloudcareEnv || 'unknown';
            }

            const sentryData = _.omit(data, "type", "htmlMessage");
            Sentry.captureMessage(getSentryMessage(data), {
                tags: {
                    errorType: data.type,
                },
                extra: sentryData,
                level: "error",
            });

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
    };

    /**
     *  Convert two-digit year to four-digit year.
     *  Differs from JavaScript's two-year parsing to better match CommCare,
     *  where most dates are either DOBs or EDDs.
     *
     *  Input is a string. If input looks like it has a two-digit year (MM.DD.YY, D/M/YY, etc.),
     *  replace the year with a four-digit year that is within the range:
     *    currentYear - 90 <= inputYear <= currentYear + 10
     *  Otherwise, return the input string.
     */
    var convertTwoDigitYear = function (inputDate) {
        var parts = inputDate.split(/\D/);
        if (parts.length === 3 && parts.join("").length <= 6) {
            let [month, day, year] = parts;
            if (year.length === 2) {
                year = Math.floor(new Date().getFullYear() / 100) + year;
                if (year > new Date().getFullYear() + 10) {
                    year -= 100;
                }
                inputDate = [month, day, year].join("/");
            }
        }
        return inputDate;
    };

    var dateFormat = 'M/D/YYYY';
    var dateFormats = ['MM/DD/YYYY', 'M/DD/YYYY', 'MM/D/YYYY',  'YYYY-MM-DD', 'M/D/YYYY', 'M/D/YY', 'M-D-YYYY', 'M-D-YY', moment.defaultFormat];

    // Annoyingly, moment and tempus dominus use different formats.
    // Moment: https://momentjs.com/docs/#/parsing/string-format/
    // TD: https://getdatepicker.com/6/plugins/customDateFormat.html
    // TD does have a plugin to integrate with moment, but since other usages of TD in HQ
    // don't need it, instead of enabling that, hack around this.
    const _momentFormatToTempusFormat = function (momentFormat) {
        return momentFormat.replaceAll("D", "d").replaceAll("Y", "y").replaceAll("A", "T");
    };

    /** Coerce an input date string to a moment object */
    var parseInputDate = function (dateString) {
        if (!moment.isMoment(dateString)) {
            dateString = convertTwoDigitYear(dateString);
        }
        let dateObj = moment(dateString, dateFormats, true);
        return dateObj.isValid() ? dateObj : null;
    };

    var initDatePicker = function ($el, selectedDate) {
        if (!$el.length) {
            return;
        }

        let options = {
            display: {
                buttons: {
                    clear: true,
                    close: true,
                    today: true,
                },
            },
            localization: {
                format: _momentFormatToTempusFormat(dateFormat),
            },
            useCurrent: false,
        };
        if (selectedDate) {
            options.viewDate = new hqTempusDominus.tempusDominus.DateTime(selectedDate);
        }
        let picker = hqTempusDominus.createDatePicker($el.get(0), options);

        $el.attr("placeholder", dateFormat);
        $el.attr("pattern", "[0-9\\-\\/]+");

        return picker;
    };

    var initTimePicker = function ($el, selectedTime, timeFormat) {
        if (!$el.length) {
            return;
        }

        let date = moment(selectedTime, timeFormat);
        const tempusTimeFormat = _momentFormatToTempusFormat(timeFormat);
        let options = {
            display: {
                buttons: {
                    clear: true,
                    close: true,
                },
            },
            localization: {
                format: tempusTimeFormat,
                hourCycle: tempusTimeFormat.indexOf('T') === -1 ? 'h23' : 'h12',
            },
            useCurrent: true,
        };
        if (date.isValid()) {
            options.viewDate = new hqTempusDominus.tempusDominus.DateTime(date);
        }
        return hqTempusDominus.createTimePicker($el.get(0), options);
    };

    var smallScreenIsEnabled = function () {
        return window.innerWidth < constants.SMALL_SCREEN_WIDTH_PX;
    };

    /**
     *  Listen for screen size changes to enable or disable small screen functionality.
     *  Accepts a callback function that should take in the new value of smallScreenEnabled.
     *  Callback runs once initially, then every time the small screen threshold is passed.
     *  Returns an object with two methods:
     *      listen() initiates a jQuery event listener and runs callback once
     *      stopListening() removes the jQuery event listener
     */
    var smallScreenListener = function (callback) {
        var smallScreenEnabled = smallScreenIsEnabled();
        var handleSmallScreenChange = () => {
            var shouldEnableSmallScreen = window.innerWidth < constants.SMALL_SCREEN_WIDTH_PX;
            if (smallScreenEnabled !== shouldEnableSmallScreen) {
                smallScreenEnabled = shouldEnableSmallScreen;
                callback(smallScreenEnabled);
            }
        };

        return {
            listen: function () {
                $(window).on('resize', handleSmallScreenChange);
                callback(smallScreenEnabled);
            },
            stopListening: function () {
                $(window).off('resize', handleSmallScreenChange);
            },
        };
    };

    return {
        dateFormat: dateFormat,
        convertTwoDigitYear: convertTwoDigitYear,
        parseInputDate: parseInputDate,
        initDatePicker: initDatePicker,
        initTimePicker: initTimePicker,
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
        smallScreenIsEnabled: smallScreenIsEnabled,
        smallScreenListener: smallScreenListener,
        getRegionContainer: getRegionContainer,
    };
});
