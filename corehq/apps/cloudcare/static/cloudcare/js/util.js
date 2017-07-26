hqDefine('cloudcare/js/util.js', function () {
    if (!String.prototype.startsWith) {
        String.prototype.startsWith = function (searchString, position) {
            position = position || 0;
            return this.indexOf(searchString, position) === position;
        };
    }

    NProgress.configure({
        showSpinner: false
    });

    var getFormUrl = function(urlRoot, appId, moduleId, formId, instanceId) {
        // TODO: make this cleaner
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

    var isParentField = function(field) {
        return field ? field.startsWith('parent/') : false;
    };

    var showError = function (message, $el) {
        if (message === undefined) {
            message = gettext("Sorry, an error occurred while processing that request.");
        }
        _show(message, $el, null, "alert alert-danger");
    };

    var showHTMLError = function (message, $el, autoHideTime) {
        message = message || gettext("Sorry, an error occurred while processing that request.");
        _show(message, $el, autoHideTime, "", true);
    };

    var showSuccess = function (message, $el, autoHideTime) {
        if (message === undefined) {
            message = "Success";
        }
        _show(message, $el, autoHideTime, "alert alert-success");
    };

    var _show = function (message, $el, autoHideTime, classes, isHTML) {
        var $container = $("<div />"),
            $alertDialog;
        $container.addClass(classes);
        if (isHTML) {
            $container.html(message);
            // HTML errors already have an alert dialog
            $alertDialog = $container.find('.alert');
        } else {
            $container.text(message);
            $alertDialog = $container;
        }
        $alertDialog
            .prepend(
                $("<a />")
                .addClass("close")
                .attr("data-dismiss", "alert")
                .html("&times;")
            );
        $el.append($container);
        if (autoHideTime) {
            $container.delay(autoHideTime).fadeOut(500);
        }
    };

    var showLoading = function (selector) {
        NProgress.start();
    };

    var tfLoading = function (selector) {
        showLoading();
    };

    var tfLoadingComplete = function (isError, message) {
        hideLoading();
        if (isError) {
            showError(message || gettext('Error saving!'), $('#cloudcare-notifications'));
        }
    };

    var tfSyncComplete = function (isError) {
        hideLoading();
        if (isError) {
            showError(
                gettext('Could not sync user data. Please try again and report a bug if issue persists.'),
                $('#cloudcare-notifications')
            );
        } else {
            showSuccess(gettext('User Data successfully synced.'), $('#cloudcare-notifications'), 5000);
        }
    };

    var clearUserDataComplete = function(isError) {
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

    var hideLoading = function (selector) {
        NProgress.done();
    };

    var hideLoadingCallback = function () {
        hideLoading();
    };
    return {
        getFormUrl: getFormUrl,
        getSubmitUrl: getSubmitUrl,
        isParentField: isParentField,
        showError: showError,
        showHTMLError: showHTMLError,
        showSuccess: showSuccess,
        showLoading: showLoading,
        clearUserDataComplete: clearUserDataComplete,
        tfLoading: tfLoading,
        tfLoadingComplete: tfLoadingComplete,
        tfSyncComplete: tfSyncComplete,
        hideLoading: hideLoading,
        hideLoadingCallback: hideLoadingCallback
    };
});
