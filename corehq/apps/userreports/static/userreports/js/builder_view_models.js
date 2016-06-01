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
     * @constructor
     */
    var PropertyListItem = function() {
        var self = this;

        this.property = ko.observable("");

        // True if the selected property is known to contain non numeric
        // data. This would be true for numeric form questions, false
        // for text questions and hidden value questions, and false for case
        // properties (because we don't know what type of data they might
        // contain)
        this.propertyIsNonNumeric = ko.pureComputed(function(){
            return ReportBuilder.IS_NON_NUMERIC_MAP[self.property()];
        });

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
                self.displayText(newValue);
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
            return Boolean(self.displayText());
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
        this.calculation = ko.observable("Count per Choice");
        this.calculationOptions = ko.pureComputed(function(){
            if (self.propertyIsNonNumeric()) {
                return hqImport('userreports/js/constants.js').NON_NUMERIC_PROPERTY_CALCULATION_OPTIONS;
            }
            return hqImport('userreports/js/constants.js').DEFAULT_CALCULATION_OPTIONS;
        });
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
            return Boolean(self.property() && self.existsInCurrentVersion() && self.displayText());
        });
    };
    PropertyListItem.wrap = function(o){
        var i = new PropertyListItem();
        i.existsInCurrentVersion(o.exists_in_current_version);
        i.property(getOrDefault(o, 'property', ""));
        i.dataSourceField(getOrDefault(o, 'data_source_field', null));
        i.displayText(o.display_text);
        i.calculation(o.calculation);
        i.format(o.format);
        return i;
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

        this.propertyOptions = options.propertyOptions;
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
        this.analyticsAction = getOrDefault(options, 'analyticsAction', null);
        this.analyticsLabel = getOrDefault(options, 'analyticsLabel', this.reportType);

        this.hasFormatCol = getOrDefault(options, 'hasFormatCol', true);
        this.hasCalculationCol = getOrDefault(options, 'hasCalculationCol', false);

        this.columns = ko.observableArray(getOrDefault(options, 'initialCols', []));
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
        this.columns.push(new PropertyListItem());
        if (!_.isEmpty(this.analyticsAction) && !_.isEmpty(this.analyticsLabel)){
            window.analytics.usage("Report Builder", this.analyticsAction, this.analyticsLabel);
            window.analytics.workflow("Clicked " + this.analyticsAction + " in Report Builder");
        }
    };

    var ConfigForm = function(reportType, sourceType, columns, filters, dataSourceIndicators, reportColumnOptions){

        var initialFilters = _.map(filters, function(i){
            return PropertyListItem.wrap(i);
        });
        var initialColumns = _.map(columns, function(i){
            return PropertyListItem.wrap(i);
        });

        this.optionsContainQuestions = _.any(dataSourceIndicators, function (o) {
            return o.type === 'question';
        });
        this.dataSourceIndicators = dataSourceIndicators;
        this.reportColumnOptions = reportColumnOptions;
        if (this.optionsContainQuestions) {
            var transformPropertyOptions = function (options) {
                return _.compact(_.map(options, function (o) {
                    if (o.type === 'question') {
                        return o.source;
                    } else if (o.type === 'meta') {
                        return {
                            value: o.source[0],
                            label: o.text,
                            type: o.type,
                        };
                    }
                }));
            };
            // Transform the property_options into the form expected by the questionsSelect binding.
            this.dataSourceIndicators = transformPropertyOptions(this.dataSourceIndicators);
            this.reportColumnOptions = transformPropertyOptions(this.reportColumnOptions);
        }

        this.filtersList = new PropertyList({
            hasFormatCol: sourceType === "case",
            hasCalculationCol: false,
            initialCols: initialFilters,
            buttonText: 'Add Filter',
            analyticsAction: 'Add Filter',
            propertyHelpText: django.gettext('Choose the property you would like to add as a filter to this report.'),
            displayHelpText: django.gettext('Web users viewing the report will see this display text instead of the property name. Name your filter something easy for users to understand.'),
            formatHelpText: django.gettext('What type of property is this filter?<br/><br/><strong>Date</strong>: select this if the property is a date.<br/><strong>Choice</strong>: select this if the property is text or multiple choice.'),
            reportType: reportType,
            propertyOptions: this.dataSourceIndicators,
        });
        this.columnsList = new PropertyList({
            hasFormatCol: false,
            hasCalculationCol: reportType === "table" || reportType === "worker",
            initialCols: initialColumns,
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
        });
    };
    ConfigForm.prototype.submitHandler = function (formElement) {
        var isValid = true;
        isValid = this.filtersList.validate() && isValid;
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
