'use strict';
/*global Backbone, DOMPurify, Marionette */

hqDefine("cloudcare/js/formplayer/menus/views/query", function () {
    // 'hqwebapp/js/bootstrap3/hq.helpers' is a dependency. It needs to be added
    // explicitly when webapps is migrated to requirejs
    var kissmetrics = hqImport("analytix/js/kissmetrix"),
        cloudcareUtils = hqImport("cloudcare/js/utils"),
        markdown = hqImport("cloudcare/js/markdown"),
        formEntryConstants = hqImport("cloudcare/js/form_entry/const"),
        formplayerConstants = hqImport("cloudcare/js/formplayer/constants"),
        formEntryUtils = hqImport("cloudcare/js/form_entry/utils"),
        FormplayerFrontend = hqImport("cloudcare/js/formplayer/app"),
        formplayerUtils = hqImport("cloudcare/js/formplayer/utils/utils"),
        initialPageData = hqImport("hqwebapp/js/initial_page_data"),
        toggles = hqImport("hqwebapp/js/toggles"),
        Collection = hqImport("cloudcare/js/formplayer/menus/collections");

    var separator = " to ",
        serverSeparator = "__",
        serverPrefix = "__range__",
        dateFormat = cloudcareUtils.dateFormat,
        selectDelimiter = "#,#"; // Formplayer also uses this

    var toIsoDate = function (dateString) {
        return cloudcareUtils.parseInputDate(dateString).format('YYYY-MM-DD');
    };
    var toUiDate = function (dateString) {
        return cloudcareUtils.parseInputDate(dateString).format(dateFormat);
    };

    var getField = function (obj, fieldName) {
        return typeof obj.get === 'function' ?  obj.get(fieldName) : obj[fieldName];
    };

    var groupDisplays = function (displays, groupHeaders) {
        const groupedDisplays = [];
        let currentGroup = {
            groupKey: null,
            groupName: null,
            displays: [],
            required: false,
        };

        displays.forEach(display => {
            const groupKey = getField(display, 'groupKey');
            if (currentGroup.groupKey !== groupKey) {
                if (currentGroup.groupKey) {
                    groupedDisplays.push(currentGroup);
                }
                currentGroup = {
                    groupKey: groupKey,
                    groupName: groupHeaders[groupKey],
                    displays: [display],
                    required: getField(display, 'required'),
                };
            } else {
                currentGroup.displays.push(display);
                currentGroup.required = currentGroup.required || getField(display, 'required');
            }
        });
        groupedDisplays.push(currentGroup);

        return groupedDisplays;
    };

    var encodeValue = function (model, searchForBlank) {
            // transform value entered to that sent to CaseSearch API (and saved for sticky search)
            var value = model.get('value');
            if (value && model.get("input") === "date") {
                value = toIsoDate(value);
            } else if (value && model.get("input") === "daterange") {
                value = serverPrefix + value.split(separator).map(toIsoDate).join(serverSeparator);
            } else if (value && (model.get('input') === 'select' || model.get('input') === 'checkbox')) {
                value = value.join(selectDelimiter);
            }

            var queryProvided = _.isObject(value) ? !!value.length : !!value;
            if (searchForBlank && queryProvided) {
                return selectDelimiter + value;
            } else if (queryProvided) {
                return value;
            } else if (searchForBlank) {
                return "";
            }
        },
        decodeValue = function (model, value) {
            // transform default values from app config and sticky search values to UI values
            if (!_.isString(value)) {
                return [false, undefined];
            }
            var allValues = value.split(selectDelimiter),
                searchForBlank = _.contains(values, ""),
                values = _.without(allValues, "");

            if (model.get('input') === 'select' || model.get('input') === 'checkbox') {
                value = values;
            } else if (values.length === 1) {
                value = values[0];
                if (model.get("input") === "date") {
                    value = toUiDate(value);
                } else if (model.get("input") === "daterange") {
                    // Take sticky value ("__range__2023-02-14__2023-02-17")
                    // or default value ("2023-02-14 to 2023-02-17")
                    // coerce to "02/14/2023 to 02/17/2023", as used by the widget
                    value = (value.replace("__range__", "")
                        .replace(separator, serverSeparator)  // only used for default values
                        .split(serverSeparator)
                        .map(toUiDate)
                        .join(separator));
                }
            } else {
                value = undefined;
            }
            return [searchForBlank, value];
        },
        geocoderItemCallback = function (addressTopic, model) {
            return function (item) {
                kissmetrics.track.event("Accessibility Tracking - Geocoder Interaction in Case Search");
                model.set('value', item.place_name);
                initMapboxWidget(model);
                const geocoderValues = JSON.parse(sessionStorage.geocoderValues);
                geocoderValues[model.id] = item.place_name;
                sessionStorage.geocoderValues = JSON.stringify(geocoderValues);
                var broadcastObj = formEntryUtils.getBroadcastObject(item);
                $.publish(addressTopic, broadcastObj);
                return item.place_name;
            };
        },
        geocoderOnClearCallback = function (addressTopic) {
            return function () {
                kissmetrics.track.event("Accessibility Tracking - Geocoder Interaction in Case Search");
                $.publish(addressTopic, formEntryConstants.NO_ANSWER);
            };
        },
        updateReceiver = function (element) {
            return function (_event, broadcastObj) {
                // e.g. format is home-state, home-zipcode, home-us_state||country
                var receiveExpression = element.data().receive;
                var receiveField = receiveExpression.split("-")[1];
                var value = null;
                if (broadcastObj === undefined || broadcastObj === formEntryConstants.NO_ANSWER) {
                    value = formEntryConstants.NO_ANSWER;
                } else if (broadcastObj[receiveField]) {
                    value = broadcastObj[receiveField];
                } else {
                    // match home-us_state||country style
                    var fields = receiveField.split('||');
                    $.each(fields, function (i, field) {
                        if (broadcastObj[field] !== undefined) {
                            value = broadcastObj[field];
                            return false;
                        }
                    });
                }
                // lookup DOM element again, in case the element got rerendered
                var domElement = $('*[data-receive="' + receiveExpression + '"]');
                if (domElement.is('input')) {
                    domElement.val(value);
                    domElement.change();
                } else {
                    // Set lookup table option by label
                    var matchingOption = function (el) {
                        return el.find("option").filter(function () {
                            return $(this).text().trim() === value;
                        });
                    };
                    var option = matchingOption(domElement);
                    if (domElement[0].multiple === true) {
                        var val = option.val();
                        if (option.length === 1 && domElement.val().indexOf(val) === -1) {
                            domElement.val(
                                domElement.val().concat(val)
                            ).trigger("change");
                        }
                    } else {
                        if (option.length === 1) {
                            domElement.val(String(option.index() - 1)).trigger("change");
                        } else {
                            domElement.val("-1").trigger('change');
                        }
                    }
                }
            };
        },
        initMapboxWidget = function (model) {
            var id = model.get('id'),
                inputId = id + "_mapbox",
                $field = $("#" + inputId);
            $(function () {
                kissmetrics.track.event("Accessibility Tracking - Geocoder Seen in Case Search");
            });
            const queryKey = sessionStorage.queryKey;
            const storedGeocoderValues = sessionStorage.geocoderValues;
            const geoValues = storedGeocoderValues ? JSON.parse(storedGeocoderValues) : {};
            if (!("queryKey" in geoValues) || geoValues["queryKey"] !== queryKey) {
                geoValues["queryKey"] = queryKey;
                sessionStorage.geocoderValues = JSON.stringify(geoValues);
            }
            if ($field.find('.mapboxgl-ctrl-geocoder--input').length === 0) {
                if (!initialPageData.get("has_geocoder_privs")) {
                    $("#" + inputId).addClass('unsupported alert alert-warning');
                    $("#" + inputId).text(gettext(
                        "Sorry, this input is not supported because your project doesn't have a Geocoder privilege")
                    );
                    return true;
                }
                formEntryUtils.renderMapboxInput({
                    divId: inputId,
                    itemCallback: geocoderItemCallback(id, model),
                    clearCallBack: geocoderOnClearCallback(id),
                    responseDataTypes: 'address,region,place,postcode',
                    useBoundingBox: true,
                });
                var divEl = $field.find('.mapboxgl-ctrl-geocoder');
                divEl.css("max-width", "none");
                divEl.css("width", "100%");
            }

            const geocoderValues = JSON.parse(sessionStorage.geocoderValues);
            if (geocoderValues[id]) {
                $field.find('.mapboxgl-ctrl-geocoder--input').val(geocoderValues[id]);
            }
        };

    var QueryView = Marionette.View.extend({
        tagName: "tr",
        className: "formplayer-request",
        template: _.template($("#query-view-item-template").html() || ""),

        templateContext: function () {
            var imageUri = this.options.model.get('imageUri'),
                audioUri = this.options.model.get('audioUri'),
                appId = this.model.collection.appId,
                value = this.options.model.get('value'),
                itemsetChoicesDict = this.options.model.get('itemsetChoicesDict');

            return {
                imageUrl: imageUri ? FormplayerFrontend.getChannel().request('resourceMap', imageUri, appId) : "",
                audioUrl: audioUri ? FormplayerFrontend.getChannel().request('resourceMap', audioUri, appId) : "",
                value: value,
                errorMessage: this.errorMessage,
                itemsetChoicesDict: itemsetChoicesDict,
                contentTag: this.parentView.options.sidebarEnabled ? "div" : "td",
            };
        },

        initialize: function () {
            this.parentView = this.options.parentView;
            this.model = this.options.model;
            this.errorMessage = null;
            this._setItemset(this.model.attributes.itemsetChoices, this.model.attributes.itemsetChoicesKey);

            // initialize with default values or with sticky values if either is present
            var value = decodeValue(this.model, this.model.get('value'))[1],
                allStickyValues = formplayerUtils.getStickyQueryInputs(),
                stickyValueEncoded = allStickyValues[this.model.get('id')],
                [searchForBlank, stickyValue] = decodeValue(this.model, stickyValueEncoded);
            this.model.set('searchForBlank', searchForBlank);
            if (stickyValue && !value) {  // Sticky values don't override default values
                value = stickyValue;
            }
            this.model.set('value', value);
        },

        ui: {
            valueDropdown: 'select.query-field',
            hqHelp: '.hq-help',
            dateRange: 'input.daterange',
            date: 'input.date',
            queryField: '.query-field',
            searchForBlank: '.search-for-blank',
        },

        events: {
            'change @ui.queryField': 'changeQueryField',
            'change @ui.searchForBlank': 'notifyParentOfFieldChange',
            'dp.change @ui.queryField': 'changeDateQueryField',
            'click @ui.searchForBlank': 'toggleBlankSearch',
        },

        _setItemset: function (itemsetChoices, itemsetChoicesKey) {
            itemsetChoices = itemsetChoices || [];
            itemsetChoicesKey = itemsetChoicesKey || [];
            let itemsetChoicesDict = {};

            itemsetChoicesKey.forEach((key,i) => itemsetChoicesDict[key] = itemsetChoices[i]);
            this.model.set({
                itemsetChoicesKey: itemsetChoicesKey,
            });

            this.model.set({
                itemsetChoices: itemsetChoices,
                itemsetChoicesDict: itemsetChoicesDict,
            });
        },

        _render: function () {
            var self = this;
            _.defer(function () {
                self.render();
                if (self.model.get('input') === 'address') {
                    initMapboxWidget(self.model);
                }
            });
        },

        hasRequiredError: function () {
            if (!this.model.get('required')) {
                return false;
            }
            var answer = this.getEncodedValue();
            if (answer !== undefined && (answer === "" || answer.replace(/\s+/, "") !== "")) {
                return false;
            } else {
                return true;
            }

        },

        hasNonRequiredErrors: function () {
            if (this.model.get("error")) {
                return true;
            }
        },

        /**
         * Determines if model has either a server error or is required and missing.
         * Returns error message, or null if model is valid.
         */
        getError: function () {
            if (this.hasNonRequiredErrors()) {
                return this.model.get("error");
            }
            if (this.hasRequiredError()) {
                return this.model.get("required_msg");
            }
            return null;
        },

        isValid: function () {
            var newError = this.getError();
            if (newError !== this.errorMessage) {
                this.errorMessage = newError;
                this._render();
            }
            return !this.errorMessage;
        },

        clear: function () {
            var self = this;
            self.model.set('value', '');
            self.model.set('error', null);
            self.errorMessage = null;
            self.model.set('searchForBlank', false);
            sessionStorage.removeItem('geocoderValues');
            if (self.ui.date.length) {
                self.ui.date.data("DateTimePicker").clear();
            }
            self._render();
            FormplayerFrontend.trigger('clearNotifications');
        },

        getEncodedValue: function () {
            if (this.model.get('input') === 'address') {
                return;  // skip geocoder address
            }
            var searchForBlank = $(this.ui.searchForBlank).prop('checked');
            return encodeValue(this.model, searchForBlank);
        },

        changeQueryField: function (e) {
            if (this.model.get('input') === 'date') {
                // Skip because dates get handled by changeDateQueryField
                return;
            } else if (this.model.get('input') === 'select1' || this.model.get('input') === 'select') {
                this.model.set('value', $(e.currentTarget).val());
            } else if (this.model.get('input') === 'address') {
                // geocoderItemCallback sets the value on the model
            } else if (this.model.get('input') === 'checkbox') {
                var newValue = _.chain($(e.currentTarget).find('input[type=checkbox]'))
                    .filter(checkbox => checkbox.checked)
                    .map(checkbox => checkbox.value)
                    .value();
                this.model.set('value', newValue);
            } else {
                this.model.set('value', $(e.currentTarget).val());
            }
            this.notifyParentOfFieldChange(e);
            this.parentView.setStickyQueryInputs();
        },

        changeDateQueryField: function (e) {
            this.model.set('value', $(e.currentTarget).val());
            var useDynamicSearch = Date(this.model._previousAttributes.value) !== Date($(e.currentTarget).val());
            this.notifyParentOfFieldChange(e, useDynamicSearch);
            this.parentView.setStickyQueryInputs();
        },

        notifyParentOfFieldChange: function (e, useDynamicSearch = true) {
            if (this.model.get('input') === 'address') {
                // Geocoder doesn't have a real value, doesn't need to be sent to formplayer
                return;
            }
            this.parentView.notifyFieldChange(e, this, useDynamicSearch, formplayerConstants.requestInitiatedByTagsMapping.FIELD_CHANGE);
        },

        toggleBlankSearch: function (e) {
            var self = this,
                searchForBlank = $(e.currentTarget).prop('checked');
            self.model.set('searchForBlank', searchForBlank);

            // When checking the blank search box for a geocoder field, toggle all its receiver fields
            if (self.model.get('input') === 'address') {
                _.each(self.model.collection.models, function (relatedModel) {
                    if (relatedModel.get('receive') && relatedModel.get('receive').split("-")[0] === self.model.get('id')) {
                        relatedModel.set('searchForBlank', searchForBlank);
                    }
                });
                initMapboxWidget(this.model);
            }
            self.parentView.setStickyQueryInputs();
        },

        _initializeSelect2Dropdown: function () {
            let placeHolderText;
            switch (this.model.get('input')) {
                case 'select1':
                    placeHolderText = gettext('Please select one');
                    break;
                case 'select':
                    placeHolderText = gettext('Please select one or more');
                    break;
                default:
                    placeHolderText = ' ';
                    break;
            }

            this.ui.valueDropdown.select2({
                allowClear: true,
                placeholder: placeHolderText,   // required for allowClear to work
                escapeMarkup: function (m) { return DOMPurify.sanitize(m); },
            });
        },

        onRender: function () {
            this._initializeSelect2Dropdown();
            this.ui.hqHelp.hqHelp({
                placement: () => {
                    if (this.parentView.options.sidebarEnabled && this.parentView.smallScreenEnabled) {
                        return 'auto bottom';
                    } else {
                        return 'auto right';
                    }
                },
            });
            cloudcareUtils.initDatePicker(this.ui.date, this.model.get('value'));
            this.ui.dateRange.daterangepicker({
                locale: {
                    format: dateFormat,
                    separator: separator,
                },
                autoUpdateInput: false,
                "autoApply": true,
            });
            this.ui.dateRange.attr("placeholder", dateFormat + separator + dateFormat);
            let separatorChars = _.unique(separator).join("");
            this.ui.dateRange.attr("pattern", "^[\\d\\/\\-" + separatorChars + "]*$");
            this.ui.dateRange.on('cancel.daterangepicker', function () {
                $(this).val('').trigger('change');
            });
            this.ui.dateRange.on('apply.daterangepicker', function (ev, picker) {
                $(this).val(picker.startDate.format(dateFormat) + separator + picker.endDate.format(dateFormat)).trigger('change');
            });
            this.ui.dateRange.on('change', function () {
                // Validate free-text input
                var start, end,
                    $input = $(this),
                    oldValue = $input.val(),
                    parts = _.map(oldValue.split(separator), cloudcareUtils.parseInputDate),
                    newValue = '';

                if (_.every(parts, part => part !== null))  {
                    if (parts.length === 1) { // condition where only one valid date is typed in rather than a range
                        start = end = parts[0];
                    } else if (parts.length === 2) {
                        [start, end] = parts;
                    }
                    newValue = start.format(dateFormat) + separator + end.format(dateFormat);
                }
                if (oldValue !== newValue) {
                    $input.val(newValue).trigger('change');
                }
            });
            if (this.model.get('hidden') === 'true') {
                this.$el.hide();
            }
        },

    });

    var GroupedQueryView = Marionette.CollectionView.extend({
        tagName: "tr",
        template: _.template($("#query-view-group-template").html() || ""),
        childView: QueryView,
        childViewContainer: "#query-group-content",

        childViewOptions: function () {
            return {parentView: this.options.parentView};
        },

        ui: {
            groupHeader: '.search-query-group-header',
        },

        events: {
            'click @ui.groupHeader': 'updateArrow',
        },

        updateArrow: function (e) {
            const arrow = $(e.currentTarget).children('i');
            if (arrow.hasClass('fa-angle-double-down')) {
                arrow.removeClass('fa-angle-double-down');
                arrow.addClass('fa-angle-double-up');
            } else {
                arrow.removeClass('fa-angle-double-up');
                arrow.addClass('fa-angle-double-down');
            }
        },

        templateContext: function () {
            let groupName = this.options.groupName === undefined ?
                "" : markdown.render(this.options.groupName.trim());
            return {
                groupName: groupName,
                groupKey: this.options.groupKey,
                required: this.options.required,
                named: groupName.length > 0,
            };
        },
    });

    var QueryListView = Marionette.CollectionView.extend({
        tagName: "div",
        template: _.template($("#query-view-list-template").html() || ""),

        childView(item) {
            if (item.has("groupName")) {
                return GroupedQueryView;
            } else {
                return QueryView;
            }
        },

        buildChildView(child, ChildViewClass, childViewOptions) {
            let options = {};

            if (child.has("groupName")) {
                const childList = new Backbone.Collection(child.get('displays'));
                options = _.extend(
                    {
                        collection: childList,
                        groupName: child.get('groupName'),
                        groupKey: child.get('groupKey'),
                        required: child.get('required'),
                    },
                    childViewOptions
                );
            } else {
                options = _.extend({model: child}, childViewOptions);
            }

            return new ChildViewClass(options);
        },

        childViewContainer: "#query-properties",
        childViewOptions: function () { return {parentView: this}; },

        initialize: function (options) {
            this.parentModel = options.collection.models || [];
            this.dynamicSearchEnabled = options.hasDynamicSearch && this.options.sidebarEnabled;

            this.smallScreenListener = cloudcareUtils.smallScreenListener(smallScreenEnabled => {
                this.handleSmallScreenChange(smallScreenEnabled);
            });
            this.smallScreenListener.listen();

            this.dynamicSearchEnabled = !(options.disableDynamicSearch || this.smallScreenEnabled) &&
                (toggles.toggleEnabled('DYNAMICALLY_UPDATE_SEARCH_RESULTS') && this.options.sidebarEnabled);
            this.searchOnClear = (options.searchOnClear && !this.smallScreenEnabled);

            if (Object.keys(options.groupHeaders).length > 0) {
                const groupedCollection = groupDisplays(options.collection, options.groupHeaders);
                this.collection = new Collection(groupedCollection);
            }
        },

        templateContext: function () {
            var description = this.options.collection.description === undefined ?
                "" : markdown.render(this.options.collection.description.trim());
            return {
                title: this.options.title.trim(),
                description: DOMPurify.sanitize(description),
                sidebarEnabled: this.options.sidebarEnabled,
                grouped: Boolean(this.collection.find(c => c.has("groupKey"))),
            };
        },

        ui: {
            clearButton: '#query-clear-button',
            submitButton: '#query-submit-button',
            valueInput: 'input.query-field',
        },

        events: {
            'click @ui.clearButton': 'clearAction',
            'click @ui.submitButton': 'submitAction',
        },

        handleSmallScreenChange: function (enabled) {
            this.smallScreenEnabled = enabled;
            if (this.options.sidebarEnabled) {
                if (this.smallScreenEnabled) {
                    $('#sidebar-region').addClass('collapse');
                } else {
                    $('#sidebar-region').removeClass('collapse');
                }
            }
        },

        _getChildren: function () {
            const children = [];
            this.children.each(function (childView) {
                if (childView.children) {
                    childView.children.each(function (grandChildView) {
                        children.push(grandChildView);
                    });
                } else {
                    children.push(childView);
                }
            });
            return children;
        },

        _getChildModels: function () {
            return _.flatten(_.map(
                Array.from(this.collection),
                function (item) {
                    if (item.has("displays")) {
                        return item.get("displays");
                    } else {
                        return [item];
                    }
                }
            ));
        },

        getAnswers: function () {
            var answers = {};
            const children = this._getChildren();
            children.forEach(function (childView) {
                var encodedValue = childView.getEncodedValue();
                if (encodedValue !== undefined) {
                    answers[childView.model.get('id')] = encodedValue;
                }
            });
            return answers;
        },

        notifyFieldChange: function (e, changedChildView, useDynamicSearch, initiatedBy) {
            e.preventDefault();
            var self = this;
            self.validateFieldChange(changedChildView, initiatedBy).always(function (response) {
                var $fields = $(".query-field");
                for (var i = 0; i < response.models.length; i++) {
                    var choices = response.models[i].get('itemsetChoices');
                    if (choices) {
                        var $field = $($fields.get(i)),
                            value = response.models[i].get('value');
                        if ($field.data('select2')) {
                            // force close dropdown, the set below can interfere with this when clearing selection
                            $field.select2('close');
                        }
                        if (value !== null) {
                            value = value.split(selectDelimiter);
                            value = _.filter(value, function (val) { return val !== ''; });
                            if (!$field.attr('multiple')) {
                                value = _.isEmpty(value) ? null : value[0];
                            }
                        }
                        self._getChildModels()[i].set({
                            value: value,
                        });

                        var childByIndex = self._getChildren()[i];
                        childByIndex._setItemset(choices, response.models[i].get('itemsetChoicesKey'));
                        childByIndex._render();      // re-render with new choice values
                    }
                }
            });
            if (self.dynamicSearchEnabled && useDynamicSearch) {
                self.updateSearchResults();
            }
        },

        clearAction: function () {
            var self = this;
            self._getChildren().forEach(function (childView) {
                childView.clear();
            });
            self.setStickyQueryInputs();
            if (self.dynamicSearchEnabled || this.searchOnClear) {
                self.updateSearchResults();
            }
        },

        submitAction: function (e) {
            var self = this;
            e.preventDefault();
            self.performSubmit();
        },

        performSubmit: function (initiatedBy) {
            var self = this;
            self.validateAllFields().done(function () {
                FormplayerFrontend.trigger(
                    "menu:query",
                    self.getAnswers(),
                    self.options.sidebarEnabled,
                    initiatedBy
                );
                if (self.smallScreenEnabled && self.options.sidebarEnabled) {
                    $('#sidebar-region').collapse('hide');
                }
                sessionStorage.submitPerformed = true;
            });
        },

        updateSearchResults: function () {
            var self = this;
            var invalidRequiredFields = [];
            self._getChildren().forEach(function (childView) {
                if (childView.hasRequiredError()) {
                    invalidRequiredFields.push(childView.model.get('text'));
                }
            });
            if (invalidRequiredFields.length === 0) {
                self.performSubmit(formplayerConstants.requestInitiatedByTagsMapping.DYNAMIC_SEARCH);
            }
        },

        validateFieldChange: function (changedChildView, initiatedBy) {
            var self = this;
            var promise = $.Deferred();

            self._updateModelsForValidation(initiatedBy).done(function (response) {
                //Gather error messages
                self._getChildren().forEach(function (childView) {
                    //Filter out empty required fields and check for validity
                    if (!childView.hasRequiredError() || childView === changedChildView) { childView.isValid(); }
                });
                promise.resolve(response);
            });

            return promise;
        },

        /*
         *  Send request to formplayer to validate fields. Displays any errors.
         *  Returns a promise that contains the formplayer response.
         */
        validateAllFields: function () {
            var self = this;
            var promise = $.Deferred();
            var invalidFields = [];
            var updatingModels = self.updateModelsForValidation || self._updateModelsForValidation();

            $.when(updatingModels).done(function (response) {
                // Gather error messages
                self._getChildren().forEach(function (childView) {
                    if (!childView.isValid()) {
                        invalidFields.push(childView.model.get('text'));
                    }
                });

                // Display error messages
                FormplayerFrontend.trigger('clearNotifications');
                if (invalidFields.length) {
                    var errorHTML = gettext("Please check the following fields:");
                    errorHTML += "<ul>" + _.map(invalidFields, function (f) {
                        return "<li>" + DOMPurify.sanitize(f) + "</li>";
                    }).join("") + "</ul>";
                    FormplayerFrontend.trigger('showError', errorHTML, true, false);
                }

                if (invalidFields.length) {
                    promise.reject(response);
                } else {
                    promise.resolve(response);
                }
            });

            return promise;
        },

        _updateModelsForValidation: function (initiatedByTag) {
            var self = this;
            var promise = $.Deferred();
            self.updateModelsForValidation = promise;
            sessionStorage.validationInProgress = true;

            var urlObject = formplayerUtils.currentUrlToObject();
            urlObject.setQueryData({
                inputs: self.getAnswers(),
                execute: false,
                forceManualSearch: true,
            });
            urlObject.setRequestInitiatedByTag(initiatedByTag);
            var fetchingPrompts = FormplayerFrontend.getChannel().request("app:select:menus", urlObject);
            $.when(fetchingPrompts).done(function (response) {
                // Update models based on response
                if (response.queryResponse) {
                    _.each(response.queryResponse.displays, function (responseModel, i) {
                        self._getChildModels()[i].set({
                            error: responseModel.error,
                            required: responseModel.required,
                            required_msg: responseModel.required_msg,
                        });
                    });
                } else {
                    _.each(response.models, function (responseModel, i) {
                        const childModels = self._getChildModels();
                        childModels[i].set({
                            error: responseModel.get('error'),
                            required: responseModel.get('required'),
                            required_msg: responseModel.get('required_msg'),
                        });
                    });
                }
                promise.resolve(response);

            });
            sessionStorage.validationInProgress = false;
            return promise;
        },

        setStickyQueryInputs: function () {
            formplayerUtils.setStickyQueryInputs(this.getAnswers());
        },

        onAttach: function () {
            this.initGeocoders();
        },

        onBeforeDetach: function () {
            this.smallScreenListener.stopListening();
        },

        initGeocoders: function () {
            var self = this;
            _.each(self._getChildModels(), function (model, i) {
                var $field = $($(".query-field")[i]);

                // Set geocoder receivers to subscribe
                if (model.get('receive')) {
                    var topic = model.get('receive').split("-")[0];
                    $.subscribe(topic, updateReceiver($field));
                }

                // Set geocoder address publish
                if (model.get('input') === 'address') {
                    initMapboxWidget(model);
                }
            });
        },

    });

    return {
        queryListView: function (data) {
            return new QueryListView(data);
        },
        groupDisplays: groupDisplays,
    };
});
