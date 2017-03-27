/* global django, ReportBuilder */
hqDefine('userreports/js/builder_view_models.js', function () {

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

        this.property = ko.observable("");
        this.getPropertyObject = getPropertyObject;
        this.hasDisplayText = hasDisplayText;

        // True if the property exists in the current version of the app
        this.existsInCurrentVersion = ko.observable(true);

        // The header for the column or filter in the report
        this.displayText = ko.observable("");

        // True if the display text has been modified by the user at least once
        this.displayTextModifiedByUser = ko.observable(false);

        // True if the display text should be updated when the property changes
        this.inheritDisplayText = ko.observable(!this.displayText());
        this.property.subscribe(function(newValue) {
            if (self.inheritDisplayText()){
                var newDisplayText = getDefaultDisplayText(newValue);
                self.displayText(newDisplayText);
            }
        });
        this.displayText.subscribe(function(value){
            if (!value) {
                // If the display text has been cleared, go back to inherting
                // it from the property
                self.inheritDisplayText(true);
            }
        });

        // A proxy for displayText that will let us know when displayText
        // has been modified by the user (by updating inheritDisplayText).
        // This is useful because sometimes the displayText is changed
        // programatically when the user changes this.property.
        this.inputBoundDisplayText = ko.computed({
            read: function() {
                return self.displayText();
            },
            write: function(value) {
                // User has made changes to display text
                self.inheritDisplayText(false);
                self.displayTextModifiedByUser(true);
                self.displayText(value);
            },
            owner: this,
        });

        this.displayTextIsValid = ko.pureComputed(function(){
            // Blank display text is not allowed
            return Boolean(self.displayText() || !self.hasDisplayText);
        });
        this.showDisplayTextError = ko.pureComputed(function(){
            // This should also return true if the user has tried to submit the form
            return !self.displayTextIsValid() && (self.displayTextModifiedByUser() || self.showWarnings());
        });

        // The format of the filter. This field is not used if the
        // PropertyListItem is representing columns
        this.format = ko.observable("");
        // The aggregation type for this column. This field is not used if
        // the PropertyListItem represents columns in a non-aggregated report
        // or a filter
        this.calculation = ko.observable(
            hqImport('userreports/js/constants.js').DEFAULT_CALCULATION_OPTIONS[0]
        );
        this.calculationOptions = ko.pureComputed(function() {
            var propObject = self.getPropertyObject(self.property());
            if (propObject) {
                return propObject.aggregation_options;
            }
            return hqImport('userreports/js/constants.js').DEFAULT_CALCULATION_OPTIONS;
        });
        // for default filters, the value to filter by
        this.filterValue = ko.observable("");
        // for default filters, the dynamic date operator to filter by
        this.filterOperator = ko.observable("");
        // If this PropertyListItem represents a property that no longer
        // exists in the app, then dataSourceField will be the name of the
        // property that no longer exists
        this.dataSourceField = ko.observable("");
        this.isEditable = ko.pureComputed(function(){
            return !self.existsInCurrentVersion();
        });

        // True if validation messages should be shown on any and all fields
        this.showWarnings = ko.observable(false);
        this.isValid = ko.computed(function(){
            return Boolean(self.property() && self.existsInCurrentVersion() && self.displayTextIsValid());
        });
    };
    /**
     * Return a "plain" javascript object representing this view model
     * suitable for sending to the server.
     */
    PropertyListItem.prototype.toJS = function () {
        return {
            property: this.property(),
            display_text: this.displayText(),
            format: this.format(),
            calculation: this.calculation(),
            pre_value: this.filterValue(),
            pre_operator: this.filterOperator(),
        };
    };
    /**
     *  Return True if the item is valid, and start showing warnings if
     *  we weren't already.
     */
    PropertyListItem.prototype.validate = function() {
        this.showWarnings(true);
        return this.isValid();
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
        this.propertyOptions = options.propertyOptions;

        // The propertyOptions transformed into a shape that either the
        // select2 or questionsSelect binding can handle.
        this.selectablePropertyOptions = options.selectablePropertyOptions;

        this.reportType = options.reportType;
        this.buttonText = getOrDefault(options, 'buttonText', 'Add property');
        // True if at least one column is required.
        this.requireColumns = getOrDefault(options, 'requireColumns', false);
        this.requireColumnsText = getOrDefault(options, 'requireColumnsText', "Please select at least one property");
        // This function will be called if a user tries to submit the form with no columns.
        this.noColumnsValidationCallback = getOrDefault(options, 'noColumnsValidationCallback', null);
        this.propertyHelpText = getOrDefault(options, 'propertyHelpText', null);
        this.displayHelpText = getOrDefault(options, 'displayHelpText', null);
        this.formatHelpText = getOrDefault(options, 'formatHelpText', null);
        this.calcHelpText = getOrDefault(options, 'calcHelpText', null);
        this.filterValueHelpText = getOrDefault(options, 'filterValueHelpText', null);
        this.analyticsAction = getOrDefault(options, 'analyticsAction', null);
        this.analyticsLabel = getOrDefault(options, 'analyticsLabel', this.reportType);

        this.hasDisplayCol = getOrDefault(options, 'hasDisplayCol', true);
        this.hasFormatCol = getOrDefault(options, 'hasFormatCol', true);
        this.hasCalculationCol = getOrDefault(options, 'hasCalculationCol', false);
        this.hasFilterValueCol = getOrDefault(options, 'hasFilterValueCol', false);

        this.columns = ko.observableArray(_.map(getOrDefault(options, 'initialCols', []), function(i) {
            return wrapListItem(i);
        }));
        this.serializedProperties = ko.computed(function(){
            return JSON.stringify(
                _.map(self.columns(), function(c){return c.toJS();})
            );
        });
        this.showWarnings = ko.observable(false);
    };
    PropertyList.prototype.validate = function () {
        this.showWarnings(true);
        var columnsValid = !_.contains(
            _.map(
                this.columns(),
                function(c){return c.validate();}
            ),
            false
        );
        var columnLengthValid = !(this.requireColumns && !this.columns().length);
        if (this.noColumnsValidationCallback && !columnLengthValid){
            this.noColumnsValidationCallback();
        }
        return columnsValid && columnLengthValid;
    };
    PropertyList.prototype.buttonHandler = function () {
        this.columns.push(new PropertyListItem(
            this.getDefaultDisplayText.bind(this),
            this.getPropertyObject.bind(this)
        ));
        if (!_.isEmpty(this.analyticsAction) && !_.isEmpty(this.analyticsLabel)){
            window.analytics.usage("Report Builder", this.analyticsAction, this.analyticsLabel);
            window.analytics.workflow("Clicked " + this.analyticsAction + " in Report Builder");
        }
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
            dateRangeOptions
    ) {
        this.optionsContainQuestions = _.any(dataSourceIndicators, function (o) {
            return o.type === 'question';
        });
        this.dataSourceIndicators = dataSourceIndicators;
        this.reportColumnOptions = reportColumnOptions;

        // Convert the DataSourceProperty and ColumnOption passed through the template
        // context into objects with the correct format for the select2 and
        // questionsSelect knockout bindings.
        if (this.optionsContainQuestions) {
            this.selectableDataSourceIndicators = _.compact(_.map(
                this.dataSourceIndicators, convertDataSourcePropertyToQuestionsSelectFormat
            ));
            this.selectableReportColumnOptions = _.compact(_.map(
                this.reportColumnOptions, convertReportColumnOptionToQuestionsSelectFormat
            ));
        } else {
            this.selectableDataSourceIndicators = _.compact(_.map(
                this.dataSourceIndicators, convertDataSourcePropertyToSelect2Format
            ));
            this.selectableReportColumnOptions = _.compact(_.map(
                this.reportColumnOptions, convertReportColumnOptionToSelect2Format
            ));
        }
        this.dateRangeOptions = dateRangeOptions;

        this.userFiltersList = new PropertyList({
            hasFormatCol: sourceType === "case",
            hasCalculationCol: false,
            initialCols: userFilters,
            buttonText: 'Add User Filter',
            analyticsAction: 'Add User Filter',
            propertyHelpText: django.gettext('Choose the property you would like to add as a filter to this report.'),
            displayHelpText: django.gettext('Web users viewing the report will see this display text instead of the property name. Name your filter something easy for users to understand.'),
            formatHelpText: django.gettext('What type of property is this filter?<br/><br/><strong>Date</strong>: Select this if the property is a date.<br/><strong>Choice</strong>: Select this if the property is text or multiple choice.'),
            reportType: reportType,
            propertyOptions: this.dataSourceIndicators,
            selectablePropertyOptions: this.selectableDataSourceIndicators,
        });
        this.defaultFiltersList = new PropertyList({
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
            propertyOptions: this.dataSourceIndicators,
            selectablePropertyOptions: this.selectableDataSourceIndicators,
        });
        this.defaultFiltersList.validate = function() {
                var isColumnsValid = PropertyList.prototype.validate.call(this);
                var isFilterValuesValid = !_.contains(
                    _.map(
                        this.columns(),
                        function(c) {return Boolean(c.filterValue())}
                    ),
                    false
                );
                return isColumnsValid && isFilterValuesValid;

        };
        this.columnsList = new PropertyList({
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
            propertyOptions: this.reportColumnOptions,
            selectablePropertyOptions: this.selectableReportColumnOptions,
        });
    };
    ConfigForm.prototype.submitHandler = function (formElement) {
        var isValid = true;
        isValid = this.userFiltersList.validate() && isValid;
        isValid = this.defaultFiltersList.validate() && isValid;
        isValid = this.columnsList.validate() && isValid;
        if (!isValid){
            alert('Invalid report configuration. Please fix the issues and try again.');
            // The event handler that disables the button is triggered
            // after this handler is invoked. Therefore, we use _.defer()
            // to re-enable it immediately after the call stack clears.
            _.defer(function(el){
                $(el).find('.disable-on-submit').enableButton();
            }, formElement);
        }
        return isValid;
    };

    return {
        ConfigForm: ConfigForm,
        PropertyList: PropertyList,
        PropertyListItem: PropertyListItem,
    };
});
