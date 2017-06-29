/* global django, ReportBuilder */
hqDefine('userreports/js/builder_view_models.js', function () {
    'use strict';

    var getOrDefault = function(options, key, default_) {
        if (options[key] === undefined) {
            return default_;
        } else {
            return options[key];
        }
    };


    /**
     * Knockout view model representing a row in the filter property list
     * @param {function} getDefaultDisplayText - a function that takes a property
     *  as an arguemnt, and returns the default display text for that property.
     * @param {function} getPropertyObject - a function that takes a property
     *  as an argument, and returns the full object representing that property.
     * @param {Boolean} hasDisplayText - whether this list has a Display Text column.
     * @constructor
     */
    var PropertyListItem = function(getDefaultDisplayText, getPropertyObject, hasDisplayText) {
        var self = this;

        self.property = ko.observable("");
        self.getPropertyObject = getPropertyObject;
        self.hasDisplayText = hasDisplayText;

        // True if the property exists in the current version of the app
        self.existsInCurrentVersion = ko.observable(true);

        // The header for the column or filter in the report
        self.displayText = ko.observable("");

        // True if the display text has been modified by the user at least once
        self.displayTextModifiedByUser = ko.observable(false);

        // True if the display text should be updated when the property changes
        self.inheritDisplayText = ko.observable(!self.displayText());
        self.property.subscribe(function(newValue) {
            if (self.inheritDisplayText()){
                var newDisplayText = getDefaultDisplayText(newValue);
                self.displayText(newDisplayText);
            }
        });
        self.displayText.subscribe(function(value){
            if (!value) {
                // If the display text has been cleared, go back to inherting
                // it from the property
                self.inheritDisplayText(true);
            }
        });

        // A proxy for displayText that will let us know when displayText
        // has been modified by the user (by updating inheritDisplayText).
        // This is useful because sometimes the displayText is changed
        // programatically when the user changes self.property.
        self.inputBoundDisplayText = ko.computed({
            read: function() {
                return self.displayText();
            },
            write: function(value) {
                // User has made changes to display text
                self.inheritDisplayText(false);
                self.displayTextModifiedByUser(true);
                self.displayText(value);
            },
            owner: self,
        });

        self.displayTextIsValid = ko.pureComputed(function(){
            // Blank display text is not allowed
            return Boolean(self.displayText() || !self.hasDisplayText);
        });
        self.showDisplayTextError = ko.pureComputed(function(){
            // This should also return true if the user has tried to submit the form
            return !self.displayTextIsValid() && (self.displayTextModifiedByUser() || self.showWarnings());
        });

        // The format of the filter. This field is not used if the
        // PropertyListItem is representing columns
        self.format = ko.observable("");
        // The aggregation type for this column. This field is not used if
        // the PropertyListItem represents columns in a non-aggregated report
        // or a filter
        self.calculation = ko.observable(
            hqImport('userreports/js/constants.js').DEFAULT_CALCULATION_OPTIONS[0]
        );
        self.calculationOptions = ko.pureComputed(function() {
            var propObject = self.getPropertyObject(self.property());
            if (propObject) {
                return propObject.aggregation_options;
            }
            return hqImport('userreports/js/constants.js').DEFAULT_CALCULATION_OPTIONS;
        });
        // for default filters, the value to filter by
        self.filterValue = ko.observable("");
        // for default filters, the dynamic date operator to filter by
        self.filterOperator = ko.observable("");
        // If this PropertyListItem represents a property that no longer
        // exists in the app, then dataSourceField will be the name of the
        // property that no longer exists
        self.dataSourceField = ko.observable("");
        self.isEditable = ko.pureComputed(function(){
            return !self.existsInCurrentVersion();
        });

        // True if validation messages should be shown on any and all fields
        self.showWarnings = ko.observable(false);
        self.isValid = ko.computed(function(){
            return Boolean(self.property() && self.existsInCurrentVersion() && self.displayTextIsValid());
        });
    };
    /**
     * Return a "plain" javascript object representing this view model
     * suitable for sending to the server.
     */
    PropertyListItem.prototype.toJS = function () {
        var self = this;
        return {
            property: self.property(),
            display_text: self.displayText(),
            format: self.format(),
            calculation: self.calculation(),
            pre_value: self.filterValue(),
            pre_operator: self.filterOperator(),
        };
    };
    /**
     *  Return True if the item is valid, and start showing warnings if
     *  we weren't already.
     */
    PropertyListItem.prototype.validate = function() {
        var self = this;
        self.showWarnings(true);
        return self.isValid();
    };


    /**
     * Knockout view model controlling the filter property list.
     */
    var PropertyList = function(options) {
        var self = this;
        options = options || {};

        var wrapListItem = function (item) {
            var i = new PropertyListItem(
                self.getDefaultDisplayText.bind(self),
                self.getPropertyObject.bind(self),
                self.hasDisplayCol
            );
            i.existsInCurrentVersion(item.exists_in_current_version);
            i.property(getOrDefault(item, 'property', ""));
            i.dataSourceField(getOrDefault(item, 'data_source_field', null));
            i.displayText(item.display_text);
            i.calculation(item.calculation);
            i.format(item.format);
            i.filterValue(item.pre_value);
            i.filterOperator(item.pre_operator);
            return i;
        };

        // A list of objects representing the properties that can be chosen from
        // for this list. Objects are js versions of ColumnOption or
        // DataSourceProperty objects.
        self.propertyOptions = options.propertyOptions;

        // The propertyOptions transformed into a shape that either the
        // select2 or questionsSelect binding can handle.
        self.selectablePropertyOptions = options.selectablePropertyOptions;

        self.reportType = options.reportType;
        self.buttonText = getOrDefault(options, 'buttonText', 'Add property');
        // True if at least one column is required.
        self.requireColumns = getOrDefault(options, 'requireColumns', false);
        self.requireColumnsText = getOrDefault(options, 'requireColumnsText', "Please select at least one property");
        // This function will be called if a user tries to submit the form with no columns.
        self.noColumnsValidationCallback = getOrDefault(options, 'noColumnsValidationCallback', null);
        self.propertyHelpText = getOrDefault(options, 'propertyHelpText', null);
        self.displayHelpText = getOrDefault(options, 'displayHelpText', null);
        self.formatHelpText = getOrDefault(options, 'formatHelpText', null);
        self.calcHelpText = getOrDefault(options, 'calcHelpText', null);
        self.filterValueHelpText = getOrDefault(options, 'filterValueHelpText', null);
        self.analyticsAction = getOrDefault(options, 'analyticsAction', null);
        self.analyticsLabel = getOrDefault(options, 'analyticsLabel', self.reportType);

        self.hasDisplayCol = getOrDefault(options, 'hasDisplayCol', true);
        self.hasFormatCol = getOrDefault(options, 'hasFormatCol', true);
        self.hasCalculationCol = getOrDefault(options, 'hasCalculationCol', false);
        self.hasFilterValueCol = getOrDefault(options, 'hasFilterValueCol', false);

        self.columns = ko.observableArray(_.map(getOrDefault(options, 'initialCols', []), function(i) {
            return wrapListItem(i);
        }));
        self.serializedProperties = ko.computed(function(){
            return JSON.stringify(
                _.map(self.columns(), function(c){return c.toJS();})
            );
        });
        self.showWarnings = ko.observable(false);

        self.validate = function () {
            self.showWarnings(true);
            var columnsValid = !_.contains(
                _.map(
                    self.columns(),
                    function(c){return c.validate();}
                ),
                false
            );
            var columnLengthValid = !(self.requireColumns && !self.columns().length);
            if (self.noColumnsValidationCallback && !columnLengthValid){
                self.noColumnsValidationCallback();
            }
            return columnsValid && columnLengthValid;
        };

        self.buttonHandler = function () {
            self.columns.push(new PropertyListItem(
                self.getDefaultDisplayText.bind(self),
                self.getPropertyObject.bind(self)
            ));
            if (!_.isEmpty(self.analyticsAction) && !_.isEmpty(self.analyticsLabel)){
                window.analytics.usage("Report Builder", self.analyticsAction, self.analyticsLabel);
                window.analytics.workflow("Clicked " + self.analyticsAction + " in Report Builder");
            }
        };

    };


    /**
     * Return the default display text for this property. For questions, it is
     * the question label.
     * @param {string} property_id
     * @returns {string}
     */
    PropertyList.prototype.getDefaultDisplayText = function (property_id) {
        var property = this.getPropertyObject(property_id);
        if (property !== undefined) {
            // property.display will exist if the property is a ColumnOption
            // property.text will exist if the property is a DataSourceProperty
            return property.display || property.text || property_id;
        }
        return property_id;
    };
    /**
     * Return the object representing the property corresponding to the given
     * property_id.
     * @param {string} property_id
     * @returns {object}
     */
    PropertyList.prototype.getPropertyObject = function(property_id) {
        return _.find(this.propertyOptions, function (opt) {return opt.id === property_id;});
    };

    /**
     * Return an object representing the given DataSourceProperty object
     * in the format expected by the select2 binding.
     * @param {object} dataSourceProperty - A js object representation of a
     *  DataSourceProperty python object.
     * @returns {object} - A js object in the format expected by the select2
     *  knockout binding.
     */
    var convertDataSourcePropertyToSelect2Format = function (dataSourceProperty) {
        return dataSourceProperty;
    };
    /**
     * Return an object representing the given DataSourceProperty object
     * in the format expected by the questionsSelect binding.
     * @param {object} dataSourceProperty - A js object representation of a
     *  DataSourceProperty python object.
     * @returns {object} - A js object in the format expected by the questionsSelect
     *  knockout binding.
     */
    var convertDataSourcePropertyToQuestionsSelectFormat = function (dataSourceProperty) {
        if (dataSourceProperty.type === 'question') {
            return dataSourceProperty.source;
        } else if (dataSourceProperty.type === 'meta') {
            return {
                value: dataSourceProperty.source[0],
                label: dataSourceProperty.text,
                type: dataSourceProperty.type,
            };
        }
    };
    /**
     * Return an object representing the given ColumnOption object in the format
     * expected by the select2 binding.
     * @param {object} columnOption - A js object representation of a
     *  ColumnOption python object.
     * @returns {object} - A js object in the format expected by the select2
     *  knockout binding.
     */
    var convertReportColumnOptionToSelect2Format = function (columnOption) {
        return {
            id: columnOption.id,
            text: columnOption.display,
        };
    };
    /**
     * Return an object representing the given ColumnOption object in the format
     * expected by the questionsSelect binding.
     * @param {object} columnOption - A js object representation of a
     *  ColumnOption python object.
     * @returns {object} - A js object in the format expected by the questionsSelect
     *  knockout binding.
     */
    var convertReportColumnOptionToQuestionsSelectFormat = function (columnOption) {
        var questionSelectRepresentation;
        if (columnOption.question_source) {
            questionSelectRepresentation = Object.assign({}, columnOption.question_source);
        } else {
            questionSelectRepresentation = {
                value: columnOption.id,
                label: columnOption.display,
            };
        }
        questionSelectRepresentation.aggregation_options = columnOption.aggregation_options;
        return questionSelectRepresentation;
    };

    var ConfigForm = function (
            reportType,
            sourceType,
            columns,
            userFilters,
            defaultFilters,
            dataSourceIndicators,
            reportColumnOptions,
            dateRangeOptions,
            isGroupByRequired,
            groupByInitialValue,
    ) {
        var self = this;
        self.optionsContainQuestions = _.any(dataSourceIndicators, function (o) {
            return o.type === 'question';
        });
        self.dataSourceIndicators = dataSourceIndicators;
        self.reportColumnOptions = reportColumnOptions;
        self.groupBy = ko.observable(groupByInitialValue);
        self.isGroupByRequired = ko.observable(isGroupByRequired);
        self.showGroupByValidationError = ko.observable(false);

        // Convert the DataSourceProperty and ColumnOption passed through the template
        // context into objects with the correct format for the select2 and
        // questionsSelect knockout bindings.
        if (self.optionsContainQuestions) {
            self.selectableDataSourceIndicators = _.compact(_.map(
                self.dataSourceIndicators, convertDataSourcePropertyToQuestionsSelectFormat
            ));
            self.selectableReportColumnOptions = _.compact(_.map(
                self.reportColumnOptions, convertReportColumnOptionToQuestionsSelectFormat
            ));
        } else {
            self.selectableDataSourceIndicators = _.compact(_.map(
                self.dataSourceIndicators, convertDataSourcePropertyToSelect2Format
            ));
            self.selectableReportColumnOptions = _.compact(_.map(
                self.reportColumnOptions, convertReportColumnOptionToSelect2Format
            ));
        }
        self.dateRangeOptions = dateRangeOptions;

        self.userFiltersList = new PropertyList({
            hasFormatCol: sourceType === "case",
            hasCalculationCol: false,
            initialCols: userFilters,
            buttonText: 'Add User Filter',
            analyticsAction: 'Add User Filter',
            propertyHelpText: django.gettext('Choose the property you would like to add as a filter to this report.'),
            displayHelpText: django.gettext('Web users viewing the report will see this display text instead of the property name. Name your filter something easy for users to understand.'),
            formatHelpText: django.gettext('What type of property is this filter?<br/><br/><strong>Date</strong>: Select this if the property is a date.<br/><strong>Choice</strong>: Select this if the property is text or multiple choice.'),
            reportType: reportType,
            propertyOptions: self.dataSourceIndicators,
            selectablePropertyOptions: self.selectableDataSourceIndicators,
        });
        self.defaultFiltersList = new PropertyList({
            hasFormatCol: true,
            hasCalculationCol: false,
            hasDisplayCol: false,
            hasFilterValueCol: true,
            initialCols: defaultFilters,
            buttonText: 'Add Default Filter',
            analyticsAction: 'Add Default Filter',
            propertyHelpText: django.gettext('Choose the property you would like to add as a filter to this report.'),
            formatHelpText: django.gettext('What type of property is this filter?<br/><br/><strong>Date</strong>: Select this to filter the property by a date range.<br/><strong>Value</strong>: Select this to filter the property by a single value.'),
            filterValueHelpText: django.gettext('What value or date range must the property be equal to?'),
            reportType: reportType,
            propertyOptions: self.dataSourceIndicators,
            selectablePropertyOptions: self.selectableDataSourceIndicators,
        });
        self.columnsList = new PropertyList({
            hasFormatCol: false,
            hasCalculationCol: reportType === "table" || reportType === "worker",
            initialCols: columns,
            buttonText: 'Add Column',
            analyticsAction: 'Add Column',
            calcHelpText: django.gettext("Column format selection will determine how each row's value is calculated."),
            requireColumns: reportType !== "chart",
            requireColumnsText: "At least one column is required",
            noColumnsValidationCallback: function(){
                window.analytics.usage(
                    'Report Builder',
                    'Click On Done (No Columns)',
                    reportType
                );
            },
            reportType: reportType,
            propertyOptions: self.reportColumnOptions,
            selectablePropertyOptions: self.selectableReportColumnOptions,
        });

        self.showValidationError = ko.observable(false);
        self.validationErrorText = ko.observable();

        self.submitHandler = function (formElement) {
            var isValid = true;
            isValid = self.userFiltersList.validate() && isValid;
            isValid = self.columnsList.validate() && isValid;
            if (self.isGroupByRequired()) {
                isValid = !_.isEmpty(self.groupBy()) && isValid;
            }
            self.showValidationError(!isValid);
            self.showGroupByValidationError(_.isEmpty(self.groupBy()) && self.isGroupByRequired());

            if (!isValid) {
                self.validationErrorText(
                    django.gettext("Please check above for any errors in your configuration.")
                );
                _.defer(function(el){
                    $(el).find('.disable-on-submit').enableButton();
                }, formElement);
            }
            return isValid;
        };
    };

    return {
        ConfigForm: ConfigForm,
        PropertyList: PropertyList,
        PropertyListItem: PropertyListItem,
    };
});
