hqDefine("cloudcare/js/form_entry/utils", function () {
    var module = {
        resourceMap: undefined,
    };

    module.touchformsError = function (message) {
        return hqImport("cloudcare/js/formplayer/errors").GENERIC_ERROR + message;
    };

    module.reloginErrorHtml = function () {
        var FormplayerFrontend = hqImport("cloudcare/js/formplayer/app");
        var isWebApps = FormplayerFrontend.getChannel().request('currentUser').environment === hqImport("cloudcare/js/formplayer/constants").WEB_APPS_ENVIRONMENT;
        if (isWebApps) {
            var url = hqImport("hqwebapp/js/initial_page_data").reverse('login_new_window');
            return _.template(gettext("Looks like you got logged out because of inactivity, but your work is safe. " +
                                      "<a href='<%= url %>' target='_blank'>Click here to log back in.</a>"))({url: url});
        } else {
            // target=_blank doesn't work properly within an iframe
            return gettext("You have been logged out because of inactivity.");
        }
    };

    /**
     * Compares the equality of two answer sets.
     * @param {(string|string[])} answer1 - A string of answers or a single answer
     * @param {(string|string[])} answer2 - A string of answers or a single answer
     */
    module.answersEqual = function (answer1, answer2) {
        if (answer1 instanceof Array && answer2 instanceof Array) {
            return _.isEqual(answer1, answer2);
        } else if (answer1 === answer2) {
            return true;
        }
        return false;
    };

    /**
     * Initializes a new form to be used by the formplayer.
     * @param {Object} formJSON - The json representation of the form
     * @param {Object} resourceMap - Function for resolving multimedia paths
     * @param {Object} $div - The jquery element that the form will be rendered in.
     */
    module.initialRender = function (formJSON, resourceMap, $div) {
        var form = new Form(formJSON),
            $debug = $('#cloudcare-debugger'),
            CloudCareDebugger = hqImport('cloudcare/js/debugger/debugger').CloudCareDebuggerFormEntry,
            cloudCareDebugger;
        module.resourceMap = resourceMap;
        ko.cleanNode($div[0]);
        $div.koApplyBindings(form);

        if ($debug.length) {
            cloudCareDebugger = new CloudCareDebugger({
                baseUrl: formJSON.xform_url,
                formSessionId: formJSON.session_id,
                username: formJSON.username,
                restoreAs: formJSON.restoreAs,
                domain: formJSON.domain,
            });
            ko.cleanNode($debug[0]);
            $debug.koApplyBindings(cloudCareDebugger);
        }

        return form;
    };

    return module;
});
