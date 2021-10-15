/*global Backbone, DOMPurify */
hqDefine("cloudcare/js/formplayer/utils/util", function () {
    var Util = {};

    /**
     * confirmationModal
     *
     * Takes an options hash that specifies options for a confirmation modal.
     *
     * @param options - Object
     *      {
     *          'title': <title> | 'Confirm?',
     *          'message': <message>,
     *          'confirmText': <confirmText> | 'OK',
     *          'cancelText': <cancelText> | 'Cancel',
     *          'onConfirm': function() {},
     *      }
     */
    Util.confirmationModal = function (options) {
        options = _.defaults(options, {
            title: gettext('Confirm?'),
            message: '',
            confirmText: gettext('OK'),
            cancelText: gettext('Cancel'),
            onConfirm: function () {},
        });
        var $modal = $('#js-confirmation-modal');
        $modal.find('.js-modal-title').text(options.title);
        $modal.find('.js-modal-body').html(DOMPurify.sanitize(options.message));
        $modal.find('#js-confirmation-confirm').text(options.confirmText);
        $modal.find('#js-confirmation-cancel').text(options.cancelText);

        var $confirmationButton = $modal.find('#js-confirmation-confirm');
        $confirmationButton.off('.confirmationModal');
        $confirmationButton.on('click.confirmationModal', function (e) {
            options.onConfirm(e);
        });
        $modal.modal('show');
    };

    Util.encodedUrlToObject = function (encodedUrl) {
        return decodeURIComponent(encodedUrl);
    };

    Util.objectToEncodedUrl = function (object) {
        return encodeURIComponent(object);
    };

    Util.currentUrlToObject = function () {
        var url = Backbone.history.getFragment();
        try {
            return Util.CloudcareUrl.fromJson(Util.encodedUrlToObject(url));
        } catch (e) {
            // This means that we're on the homepage
            return new Util.CloudcareUrl({});
        }
    };

    Util.setUrlToObject = function (urlObject, replace) {
        replace = replace || false;
        var encodedUrl = Util.objectToEncodedUrl(urlObject.toJson());
        hqImport("cloudcare/js/formplayer/app").navigate(encodedUrl, { replace: replace });
    };

    Util.doUrlAction = function (actionCallback) {
        var currentObject = Util.CurrentUrlToObject();
        actionCallback(currentObject);
        Util.setUrlToObject(currentObject);
    };

    Util.setCrossDomainAjaxOptions = function (options) {
        options.type = 'POST';
        options.dataType = "json";
        options.crossDomain = {crossDomain: true};
        options.xhrFields = {withCredentials: true};
        options.contentType = "application/json;charset=UTF-8";
    };

    Util.saveDisplayOptions = function (displayOptions) {
        var displayOptionsKey = Util.getDisplayOptionsKey();
        localStorage.setItem(displayOptionsKey, JSON.stringify(displayOptions));
    };

    Util.getSavedDisplayOptions = function () {
        var displayOptionsKey = Util.getDisplayOptionsKey();
        try {
            return JSON.parse(localStorage.getItem(displayOptionsKey));
        } catch (e) {
            window.console.warn('Unabled to parse saved display options');
            return {};
        }
    };

    Util.getDisplayOptionsKey = function () {
        var user = hqImport("cloudcare/js/formplayer/app").getChannel().request('currentUser');
        return [
            user.environment,
            user.domain,
            user.username,
            'displayOptions',
        ].join(':');
    };

    Util.pagesToShow = function (selectedPage, totalPages, limit) {
        var limitHalf = Math.floor(limit / 2);
        if (totalPages < limit) {
            return {
                start: 0,
                end: totalPages,
            };
        }

        if (selectedPage < limitHalf) {
            return {
                start: 0,
                end: limit,
            };
        }

        if (selectedPage > totalPages - limitHalf) {
            return {
                start: totalPages - limit,
                end: totalPages,
            };
        }

        return {
            start: selectedPage - limitHalf,
            end: selectedPage + limitHalf,
        };
    };

    Util.getCurrentQueryInputs = function () {
        var queryData = Util.currentUrlToObject().queryData[sessionStorage.queryKey];
        if (queryData) {
            return queryData.inputs || {};
        }
        return {};
    };

    Util.getStickyQueryInputs = function () {
        if (!hqImport("hqwebapp/js/toggles").toggleEnabled('WEBAPPS_STICKY_SEARCH')) {
            return {};
        }
        if (!this.stickyQueryInputs) {
            return {};
        }
        return this.stickyQueryInputs[sessionStorage.queryKey] || {};
    };

    Util.setStickyQueryInputs = function (inputs) {
        if (!this.stickyQueryInputs) {
            this.stickyQueryInputs = {};
        }
        this.stickyQueryInputs[sessionStorage.queryKey] = inputs;
    };

    Util.CloudcareUrl = function (options) {
        this.appId = options.appId;
        this.copyOf = options.copyOf;
        this.sessionId = options.sessionId;
        this.selections = options.selections;
        this.endpointId = options.endpointId;
        this.endpointArgs = options.endpointArgs;
        this.page = options.page;
        this.search = options.search;
        this.smartLinkTemplate = options.smartLinkTemplate;
        this.casesPerPage = options.casesPerPage;
        this.queryData = options.queryData;
        this.singleApp = options.singleApp;
        this.sortIndex = options.sortIndex;
        this.forceLoginAs = options.forceLoginAs;
        this.forceManualAction = options.forceManualAction;

        this.setSelections = function (selections) {
            this.selections = selections;
        };

        this.addSelection = function (selection) {
            if (!this.selections) {
                this.selections = [];
            }

            // Selections only deal with strings, because formplayer will send them back as strings
            this.selections.push(String(selection));

            // clear out pagination and search when we navigate
            this.page = null;
            this.search = null;
        };

        this.setPage = function (page) {
            this.page = page;
        };

        this.setCasesPerPage = function (casesPerPage) {
            this.casesPerPage = casesPerPage;
            this.page = null;
            this.sortIndex = null;
        };

        this.setSort = function (sortIndex) {
            this.sortIndex = sortIndex;
        };

        this.setSearch = function (search) {
            this.search = search;
            //clear out pagination on search
            this.page = null;
            this.sortIndex = null;
        };

        this.setSmartLinkTemplate = function (smartLinkTemplate) {
            this.smartLinkTemplate = smartLinkTemplate;
        };

        this.setQueryData = function (queryDict, execute) {
            if (!this.queryData) {
                this.queryData = {};
            }
            var selections = hqImport("cloudcare/js/formplayer/utils/util").currentUrlToObject().selections;
            this.queryData[sessionStorage.queryKey] = {
                inputs: queryDict,
                execute: execute,
                selections: selections,
            };
            this.page = null;
            this.search = null;
        };

        this.setForceManualAction = function (force) {
            this.forceManualAction = force;
        };

        this.replaceEndpoint = function (selections) {
            delete this.endpointId;
            delete this.endpointArgs;
            this.selections = selections || [];
        };

        this.clearExceptApp = function () {
            this.sessionId = null;
            this.selections = null;
            this.page = null;
            this.sortIndex = null;
            this.search = null;
            this.queryData = null;
            this.forceManualAction = null;
        };

        this.onSubmit = function () {
            this.page = null;
            this.sortIndex = null;
            this.search = null;
            this.queryData = null;
            this.forceManualAction = null;
        };

        this.spliceSelections = function (index) {
            // null out the session if we clicked the root (home)
            if (index === 0) {
                this.selections = null;
                this.sessionId = null;
            } else {
                this.selections = this.selections.splice(0, index);
                var key = this.selections.join(",");
                // Query data is necessary to formplayer navigation, so keep it,
                // but only for the selections that are still relevant to the session.
                this.queryData = _.pick(this.queryData, function (value) {
                    var valueKey = value.selections.join(",");
                    return key.startsWith(valueKey) && key !== valueKey;
                });
            }
            this.page = null;
            this.search = null;
            this.sortIndex = null;
            this.queryData = null;
            this.forceManualAction = null;
        };
    };

    Util.CloudcareUrl.prototype.toJson = function () {
        var self = this;
        var dict = {
            appId: self.appId,
            copyOf: self.copyOf,
            endpointId: self.endpointId,
            endpointArgs: self.endpointArgs,
            sessionId: self.sessionId,
            selections: self.selections,
            page: self.page,
            search: self.search,
            smartLinkTemplate: self.smartLinkTemplate,
            queryData: self.queryData || {},    // formplayer can't handle a null
            singleApp: self.singleApp,
            sortIndex: self.sortIndex,
            forceLoginAs: self.forceLoginAs,
            forceManualAction: self.forceManualAction,
        };
        return JSON.stringify(dict);
    };

    Util.CloudcareUrl.fromJson = function (json) {
        var data = JSON.parse(json);
        var options = {
            'appId': data.appId,
            'copyOf': data.copyOf,
            'endpointId': data.endpointId,
            'endpointArgs': data.endpointArgs,
            'sessionId': data.sessionId,
            'selections': data.selections,
            'page': data.page,
            'search': data.search,
            'queryData': data.queryData,
            'singleApp': data.singleApp,
            'smartLinkTemplate': data.smartLinkTemplate,
            'sortIndex': data.sortIndex,
            'forceLoginAs': data.forceLoginAs,
            'forceManualAction': data.forceManualAction,
        };
        return new Util.CloudcareUrl(options);
    };

    if (!String.prototype.startsWith) {
        String.prototype.startsWith = function (searchString, position) {
            position = position || 0;
            return this.substr(position, searchString.length) === searchString;
        };
    }

    if (!String.prototype.endsWith) {
        String.prototype.endsWith = function (searchString, position) {
            var subjectString = this.toString();
            if (typeof position !== 'number' || !isFinite(position) || Math.floor(position) !== position || position > subjectString.length) {
                position = subjectString.length;
            }
            position -= searchString.length;
            var lastIndex = subjectString.lastIndexOf(searchString, position);
            return lastIndex !== -1 && lastIndex === position;
        };
    }

    if (!String.prototype.includes) {
        String.prototype.includes = function (search, start) {
            'use strict';
            if (typeof start !== 'number') {
                start = 0;
            }
            if (start + search.length > this.length) {
                return false;
            } else {
                return this.indexOf(search, start) !== -1;
            }
        };
    }

    if (!String.prototype.repeat) {
        String.prototype.repeat = function (count) {
            var result = "",
                string = this.valueOf();
            while (count > 0) {
                result += string;
                count -= 1;
            }
            return result;
        };
    }

    Util.savePerPageLimitCookie = function (name, perPageLimit) {
        var savedPath = window.location.pathname;
        var initialPageData = hqImport("hqwebapp/js/initial_page_data");
        $.cookie(name + '-per-page-limit', perPageLimit, {
            expires: 365,
            path: savedPath,
            secure: initialPageData.get('secure_cookies'),
        });
    };

    return Util;
});
