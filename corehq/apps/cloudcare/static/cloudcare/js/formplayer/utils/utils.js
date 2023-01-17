'use strict';
hqDefine("cloudcare/js/formplayer/utils/utils", [
    'jquery',
    'underscore',
    'backbone',
    'DOMPurify/dist/purify.min',
    'hqwebapp/js/initial_page_data',
    'hqwebapp/js/toggles',
    "cloudcare/js/formplayer/users/models",
], function (
    $,
    _,
    Backbone,
    DOMPurify,
    initialPageData,
    toggles,
    UsersModels
) {
    var Utils = {};

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
    Utils.confirmationModal = function (options) {
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

    Utils.encodedUrlToObject = function (encodedUrl) {
        return decodeURIComponent(encodedUrl);
    };

    Utils.objectToEncodedUrl = function (object) {
        return encodeURIComponent(object);
    };

    Utils.currentUrlToObject = function () {
        var url = Backbone.history.getFragment();
        try {
            const cloudcareUrl = Utils.CloudcareUrl.fromJson(Utils.encodedUrlToObject(url));
            for (const queryKey in cloudcareUrl.queryData) {
                // retrieve query inputs from Utils object
                cloudcareUrl.queryData[queryKey].inputs = Utils.getCurrentQueryInputs(queryKey);
            }
            return cloudcareUrl;
        } catch (e) {
            // This means that we're on the homepage
            return new Utils.CloudcareUrl({});
        }
    };

    Utils.setUrlToObject = function (urlObject, replace) {
        replace = replace || false;
        for (const queryKey in urlObject.queryData) {
            // don't store query inputs in url
            delete urlObject.queryData[queryKey].inputs;
        }
        var encodedUrl = Utils.objectToEncodedUrl(urlObject.toJson());
        Utils.navigate(encodedUrl, { replace: replace });
    };

    Utils.navigate = function (route, options) {
        options || (options = {});
        Backbone.history.navigate(route, options);
    };

    /**
     * Helper function to update the URL
     *
     * @param actionCallback Function called with the current URL Object as an argument.
     *                       Return 'false' to prevent updating the URL.
     * @param replace        Set to 'true' to update the URL without creating an entry in
     *                       the browser's history
     * @returns              The updated URL Object
     */
    Utils.doUrlAction = function (actionCallback, replace) {
        var currentObject = Utils.currentUrlToObject();
        const update = actionCallback(currentObject);
        if (update !== false) {
            Utils.setUrlToObject(currentObject, replace);
        }
        return currentObject;
    };


    Utils.setCrossDomainAjaxOptions = function (options) {
        options.type = 'POST';
        options.dataType = "json";
        options.crossDomain = {crossDomain: true};
        options.xhrFields = {withCredentials: true};
        options.contentType = "application/json;charset=UTF-8";
    };

    Utils.saveDisplayOptions = function (displayOptions) {
        var displayOptionsKey = Utils.getDisplayOptionsKey();
        localStorage.setItem(displayOptionsKey, JSON.stringify(displayOptions));
    };

    Utils.getSavedDisplayOptions = function () {
        var displayOptionsKey = Utils.getDisplayOptionsKey();
        try {
            return JSON.parse(localStorage.getItem(displayOptionsKey));
        } catch (e) {
            window.console.warn('Unabled to parse saved display options');
            return {};
        }
    };

    Utils.getDisplayOptionsKey = function () {
        var user = UsersModels.getCurrentUser();
        return [
            user.environment,
            user.domain,
            user.username,
            'displayOptions',
        ].join(':');
    };

    // This method takes current page number on which user has clicked and total possible pages
    // and calculate the range of page numbers (start and end) that has to be shown on pagination widget.
    // totalItems can be either the total on the current page or across all pages.
    Utils.paginateOptions = function (currentPage, totalPages, totalItems) {
        var maxPages = 5;
        // ensure current page isn't out of range
        if (currentPage < 1) {
            currentPage = 1;
        } else if (currentPage > totalPages) {
            currentPage = totalPages;
        }
        var startPage, endPage;
        if (totalPages <= maxPages) {
            // total pages less than max so show all pages
            startPage = 1;
            endPage = totalPages;
        } else {
            // total pages more than max so calculate start and end pages
            var maxPagesBeforeCurrentPage = Math.floor(maxPages / 2);
            var maxPagesAfterCurrentPage = Math.ceil(maxPages / 2) - 1;
            if (currentPage <= maxPagesBeforeCurrentPage) {
                // current page near the start
                startPage = 1;
                endPage = maxPages;
            } else if (currentPage + maxPagesAfterCurrentPage >= totalPages) {
                // current page near the end
                startPage = totalPages - maxPages + 1;
                endPage = totalPages;
            } else {
                // current page somewhere in the middle
                startPage = currentPage - maxPagesBeforeCurrentPage;
                endPage = currentPage + maxPagesAfterCurrentPage;
            }
        }

        const rowRange = [5, 10, 25, 50, 100],
            hasMultiplePages = totalPages > 1,
            hasAtLeastMinimumItemsPerPage = totalItems > rowRange[0],
            showPagination = hasMultiplePages || hasAtLeastMinimumItemsPerPage;

        return {
            startPage: startPage,
            endPage: endPage,
            pageCount: totalPages,
            rowRange: rowRange,
            showPagination: showPagination,
            pageNumLabel: _.template(gettext("Page <%- num %>")),
        };
    };

    Utils.paginationGoPageNumber = function (pageNumber, pageCount) {
        if (pageNumber >= 1 && pageNumber <= pageCount) {
            return pageNumber;
        } else {
            return pageCount;
        }
    };

    Utils.getCurrentQueryInputs = function (queryKey) {
        queryKey = queryKey || sessionStorage.queryKey;
        const queryInputs = this.queryInputs || {};
        return queryInputs[queryKey];
    };

    Utils.setCurrentQueryInputs = function (inputs, queryKey) {
        queryKey = queryKey || sessionStorage.queryKey;
        if (queryKey && queryKey !== "null" && queryKey !== "undefined") {
            this.queryInputs = this.queryInputs || {};
            this.queryInputs[queryKey] = inputs;
        }
    };

    Utils.getStickyQueryInputs = function () {
        if (toggles.toggleEnabled('WEBAPPS_STICKY_SEARCH') && this.stickyQueryInputs) {
            return this.stickyQueryInputs[sessionStorage.queryKey] || {};
        }
        return {};
    };

    Utils.setStickyQueryInputs = function (inputs) {
        const queryKey = sessionStorage.queryKey;
        if (queryKey && queryKey !== "null" && queryKey !== "undefined") {
            this.stickyQueryInputs = this.stickyQueryInputs || {};
            this.stickyQueryInputs[queryKey] = inputs;
        }
    };

    Utils.setSelectedValues = function (selections) {
        if (selections !== undefined) {
            let selectedValues = (sessionStorage.selectedValues !== undefined) ? JSON.parse(sessionStorage.selectedValues) : {};
            selectedValues[sessionStorage.queryKey] = selections.join(',');
            sessionStorage.selectedValues = JSON.stringify(selectedValues);
        }
    };

    Utils.CloudcareUrl = function (options) {
        this.appId = options.appId;
        this.copyOf = options.copyOf;
        this.sessionId = options.sessionId;
        this.selections = options.selections;
        this.endpointId = options.endpointId;
        this.endpointArgs = options.endpointArgs;
        this.page = options.page;
        this.search = options.search;
        this.casesPerPage = options.casesPerPage;
        this.queryData = options.queryData;
        this.singleApp = options.singleApp;
        this.sortIndex = options.sortIndex;
        this.forceLoginAs = options.forceLoginAs;

        this.setSelections = function (selections) {
            this.selections = selections;
        };

        this.addSelection = function (selection) {
            if (!this.selections) {
                this.selections = [];
            }
            // Selections only deal with strings, because formplayer will send them back as strings
            if (_.isArray(selection)) {
                Utils.setSelectedValues(selection);
                this.selections.push(String('use_selected_values'));
            } else {
                this.selections.push(String(selection));
            }
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

        this.setQueryData = function ({ inputs, execute, forceManualSearch, initiatedBy}) {
            var selections = Utils.currentUrlToObject().selections;
            var queryKey = sessionStorage.queryKey;
            this.queryData = this.queryData || {};

            const queryDataEntry = _.defaults({
                inputs: inputs,
                execute: execute,
                force_manual_search: forceManualSearch,
                selections: selections,
            }, this.queryData[queryKey]);

            if (initiatedBy !== null && initiatedBy !== undefined) {
                queryDataEntry.initiatedBy = initiatedBy;
            }
            Utils.setCurrentQueryInputs(inputs, queryKey);
            this.queryData[queryKey] = queryDataEntry;

            this.page = null;
            this.search = null;
        };

        this.replaceEndpoint = function (selections) {
            delete this.endpointId;
            delete this.endpointArgs;
            this.selections = selections || [];
            sessionStorage.removeItem('selectedValues');
            this.sessionId = null;
        };

        this.clearExceptApp = function () {
            this.sessionId = null;
            this.selections = null;
            sessionStorage.removeItem('selectedValues');
            this.page = null;
            this.sortIndex = null;
            this.search = null;
            this.queryData = null;
            this.sessionId = null;
            sessionStorage.removeItem('submitPerformed');
            sessionStorage.removeItem('geocoderValues');
            sessionStorage.removeItem('validationInProgress');
            sessionStorage.removeItem('answerQuestionInProgress');
        };

        this.onSubmit = function () {
            sessionStorage.removeItem('selectedValues');
            sessionStorage.removeItem('geocoderValues');
            this.page = null;
            this.sortIndex = null;
            this.search = null;
            this.queryData = null;
            this.sessionId = null;
        };

        this.spliceSelections = function (index) {
            // null out the session if we clicked the root (home)
            if (index === 0) {
                this.selections = null;
                this.sessionId = null;
                this.queryData = null;
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
            sessionStorage.removeItem('selectedValues');
            sessionStorage.removeItem('geocoderValues');
            this.sessionId = null;
        };

    };

    Utils.CloudcareUrl.prototype.toJson = function () {
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
            queryData: self.queryData || {},    // formplayer can't handle a null
            singleApp: self.singleApp,
            sortIndex: self.sortIndex,
            forceLoginAs: self.forceLoginAs,
        };
        return JSON.stringify(dict);
    };

    Utils.CloudcareUrl.fromJson = function (json) {
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
            'sortIndex': data.sortIndex,
            'forceLoginAs': data.forceLoginAs,
        };
        return new Utils.CloudcareUrl(options);
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

    Utils.savePerPageLimitCookie = function (name, perPageLimit) {
        var savedPath = window.location.pathname;
        $.cookie(name + '-per-page-limit', perPageLimit, {
            expires: 365,
            path: savedPath,
            secure: initialPageData.get('secure_cookies'),
        });
    };

    return Utils;
});
