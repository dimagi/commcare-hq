/**
 * @file Defines all models for the export page. Models map to python models in
 * corehq/apps/export/models/new.py
 *
 */

hqDefine('export/js/models', [
    'jquery',
    'knockout',
    'underscore',
    'hqwebapp/js/initial_page_data',
    'hqwebapp/js/toggles',
    'analytix/js/google',
    'analytix/js/kissmetrix',
    'export/js/const',
    'export/js/utils',
    'hqwebapp/js/bootstrap3/validators.ko',        // needed for validation of customPathString
    'hqwebapp/js/bootstrap3/knockout_bindings.ko', // needed for multirow_sortable binding
], function (
    $,
    ko,
    _,
    initialPageData,
    toggles,
    googleAnalytics,
    kissmetricsAnalytics,
    constants,
    utils
) {
    /**
     * readablePath
     *
     * Helper function that takes an array of PathNodes and converts them to a string dot path.
     *
     * @param {Array} pathNodes - An array of PathNodes to be converted to a string
     *      dot path.
     * @returns {string} A string dot path that represents the array of PathNodes
     */
    var readablePath = function (pathNodes) {
        return _.map(pathNodes, function (pathNode) {
            var name = pathNode.name();
            return ko.utils.unwrapObservable(pathNode.is_repeat) ? name + '[]' : name;
        }).join('.');
    };

    /**
     * customPathToNodes
     *
     * Helper function that takes a string path like form.meta.question and
     * returns the equivalent path in an array of PathNodes.
     *
     * @param {string} customPathString - A string dot path to be converted
     *      to PathNodes.
     * @returns {Array} Returns an array of PathNodes.
     */
    var customPathToNodes = function (customPathString) {
        var parts = customPathString.split('.');
        return _.map(parts, function (part) {
            var isRepeat = !!part.match(/\[]$/);
            if (isRepeat) {
                part = part.slice(0, part.length - 2);  // Remove the [] from the end of the path
            }
            return new PathNode({
                name: part,
                is_repeat: isRepeat,
                doc_type: 'PathNode',
            });
        });
    };

    /**
     * ExportInstance
     * @class
     *
     * This is an instance of an export. It contains the tables to export
     * and other presentation properties.
     */
    var ExportInstance = function (instanceJSON, options) {
        options = options || {};
        var self = this;
        ko.mapping.fromJS(instanceJSON, ExportInstance.mapping, self);

        self.geoProperties = options.geoProperties;
        self.buildSchemaProgress = ko.observable(0);
        self.showBuildSchemaProgressBar = ko.observable(false);
        self.errorOnBuildSchema = ko.observable(false);
        self.schemaProgressText = ko.observable(gettext('Process'));
        self.numberOfAppsToProcess = options.numberOfAppsToProcess || 0;

        // Constants and utils that the HTML template needs access to
        self.splitTypes = {
            multiselect: constants.MULTISELECT_SPLIT_TYPE,
            plain: constants.PLAIN_SPLIT_TYPE,
            userDefined: constants.USER_DEFINED_SPLIT_TYPES,
        };
        self.getTagCSSClass = utils.getTagCSSClass;
        self.constants = constants;
        if (self.include_errors) {
            self.initiallyIncludeErrors = ko.observable(self.include_errors());
        }

        // Determines the state of the save. Used for controlling the presentation
        // of the Save button.
        self.saveState = ko.observable(constants.SAVE_STATES.READY);
        self.saveStateReady = ko.computed(function () { return self.saveState() === constants.SAVE_STATES.READY; });
        self.saveStateSaving = ko.computed(function () { return self.saveState() === constants.SAVE_STATES.SAVING; });
        self.saveStateSuccess = ko.computed(function () { return self.saveState() === constants.SAVE_STATES.SUCCESS; });
        self.saveStateError = ko.computed(function () { return self.saveState() === constants.SAVE_STATES.ERROR; });

        // True if the form has no errors
        self.isValid = ko.pureComputed(function () {
            if (self.is_odata_config() && self.hasDuplicateColumnLabels()) {
                return false;
            }
            if (!self.hasDailySavedAccess && self.is_daily_saved_export()) {
                return false;
            }
            return true;
        });

        self.duplicateLabel = ko.observable();

        self.hasDuplicateColumnLabels = ko.pureComputed(function () {
            self.duplicateLabel('');
            var hasDuplicates = false;
            _.each(self.tables(), function (table) {
                var labels = [];
                _.each(table.columns(), function (column) {
                    if (column.selected() && labels.indexOf(column.label()) === -1) {
                        labels.push(column.label());
                    } else if (column.selected()) {
                        hasDuplicates = true;
                        self.duplicateLabel(column.label());
                    }
                });
            });
            return hasDuplicates;
        });

        // The url to save the export to.
        self.saveUrl = options.saveUrl;
        self.hasExcelDashboardAccess = Boolean(options.hasExcelDashboardAccess);
        self.hasDailySavedAccess = Boolean(options.hasDailySavedAccess);

        self.formatOptions = options.formatOptions !== undefined ? options.formatOptions : _.map(constants.EXPORT_FORMATS, function (format) {
            return format;
        });

        self.sharingOptions = options.sharingOptions !== undefined ? options.sharingOptions : _.map(constants.SHARING_OPTIONS, function (format) {
            return format;
        });

        self.initialSharing = instanceJSON.sharing;
        self.hasOtherOwner = options.hasOtherOwner;

        // If any column has a deid transform, show deid column
        self.isDeidColumnVisible = ko.observable(self.is_deidentified() || _.any(self.tables(), function (table) {
            return table.selected() && _.any(table.columns(), function (column) {
                return column.selected() && column.deid_transform();
            });
        }));

        // Set column widths
        self.questionColumnClass = ko.computed(function () {
            var width = 6;
            if (self.type && self.type() === 'case' && toggles.previewEnabled('SPLIT_MULTISELECT_CASE_EXPORT')) {
                width--;
            }
            if (self.isDeidColumnVisible()) {
                width--;
            }
            return "col-sm-" + width;
        });
        self.displayColumnClass = ko.computed(function () {
            var width = 5;
            if (self.type && self.type() === 'case' && toggles.previewEnabled('SPLIT_MULTISELECT_CASE_EXPORT')) {
                width--;
            }
            if (self.isDeidColumnVisible()) {
                width--;
            }
            return "col-sm-" + width;
        });

        self.hasHtmlFormat = ko.pureComputed(function () {
            return this.export_format() === constants.EXPORT_FORMATS.HTML;
        }, self);
        self.hasDisallowedHtmlFormat = ko.pureComputed(function () {
            return this.hasHtmlFormat() && !this.hasExcelDashboardAccess;
        }, self);

        self.hasCaseHistoryTable = ko.pureComputed(function () {
            return _.any(self.tables(), function (table) {
                if (table.label() !== 'Case History') {
                    return false;
                }
                return _.any(table.columns(), function (column) {
                    return column.selected();
                });
            });
        });

        self.export_format.subscribe(function (newFormat) {
            // Selecting Excel Dashboard format automatically checks the daily saved export box
            if (newFormat === constants.EXPORT_FORMATS.HTML) {
                self.is_daily_saved_export(true);
            } else {
                if (!self.hasExcelDashboardAccess) {
                    self.is_daily_saved_export(false);
                }
            }
        });
    };

    ExportInstance.prototype.onBeginSchemaBuild = function (exportInstance, e) {
        var self = this,
            $btn = $(e.currentTarget),
            errorHandler,
            successHandler,
            buildSchemaUrl = initialPageData.reverse('build_schema', this.domain()),
            identifier = ko.utils.unwrapObservable(this.case_type) || ko.utils.unwrapObservable(this.xmlns);

        // We've already built the schema and now the user is clicking the button to refresh the page
        if (this.buildSchemaProgress() === 100) {
            // This param will let us know to automatically enable the filter after the page refreshes
            let pageUrl = new URL(window.location.href);
            pageUrl.searchParams.append('delete_filter_enabled', 'True');
            window.location.href = pageUrl;
            return;
        }

        this.showBuildSchemaProgressBar(true);
        this.buildSchemaProgress(0);

        self.schemaProgressText(gettext('Processing...'));
        $btn.attr('disabled', true);
        $btn.addClass('disabled');
        $btn.addSpinnerToButton();

        errorHandler = function () {
            $btn.attr('disabled', false);
            $btn.removeSpinnerFromButton();
            $btn.removeClass('disabled');
            self.errorOnBuildSchema(true);
            self.schemaProgressText(gettext('Process'));
        };

        successHandler = function () {
            $btn.removeSpinnerFromButton();
            $btn.removeClass('disabled');
            $btn.attr('disabled', false);
            self.schemaProgressText(gettext('Refresh page'));
        };

        $.ajax({
            url: buildSchemaUrl,
            type: 'POST',
            data: {
                type: this.type(),
                app_id: this.app_id(),
                identifier: identifier,
            },
            dataType: 'json',
            success: function (response) {
                self.checkBuildSchemaProgress(response.download_id, successHandler, errorHandler);
            },
            error: errorHandler,
        });
    };

    ExportInstance.prototype.checkBuildSchemaProgress = function (downloadId, successHandler, errorHandler) {
        var self = this,
            buildSchemaUrl = initialPageData.reverse('build_schema', this.domain());

        $.ajax({
            url: buildSchemaUrl,
            type: 'GET',
            data: {
                download_id: downloadId,
            },
            dataType: 'json',
            success: function (response) {
                if (response.success) {
                    self.buildSchemaProgress(100);
                    self.showBuildSchemaProgressBar(false);
                    successHandler();
                    return;
                }

                if (response.failed) {
                    self.errorOnBuildSchema(true);
                    return;
                }

                self.buildSchemaProgress(response.progress.percent || 0);
                if (response.not_started || response.progress.current === null ||
                        response.progress.current !== response.progress.total) {
                    window.setTimeout(
                        self.checkBuildSchemaProgress.bind(self, response.download_id, successHandler, errorHandler),
                        2000
                    );
                }
            },
            error: errorHandler,
        });
    };

    ExportInstance.prototype.onLoadAllProperties = function () {
        var pageUrl = new URL(window.location.href);
        pageUrl.searchParams.append('load_deprecated', 'True');
        window.location.href = pageUrl;
    };

    ExportInstance.prototype.getFormatOptionValues = function () {
        return _.filter(constants.EXPORT_FORMATS, function (format) {
            return this.formatOptions.indexOf(format) !== -1;
        }, this);
    };

    ExportInstance.prototype.getFormatOptionText = function (format) {
        if (format === constants.EXPORT_FORMATS.HTML) {
            return gettext('Web Page (Excel Dashboards)');
        } else if (format === constants.EXPORT_FORMATS.CSV) {
            return gettext('CSV (Zip file)');
        } else if (format === constants.EXPORT_FORMATS.XLS) {
            return gettext('Excel (older versions)');
        } else if (format === constants.EXPORT_FORMATS.XLSX) {
            return gettext('Excel 2007+');
        } else if (format === constants.EXPORT_FORMATS.GEOJSON) {
            return gettext('GeoJSON');
        }
    };

    ExportInstance.prototype.getSharingOptionValues = function () {
        return _.filter(constants.SHARING_OPTIONS, function (format) {
            return this.sharingOptions.indexOf(format) !== -1;
        }, this);
    };

    ExportInstance.prototype.getSharingOptionText = function (format) {
        if (format === constants.SHARING_OPTIONS.PRIVATE) {
            return gettext('Private');
        } else if (format === constants.SHARING_OPTIONS.EXPORT_ONLY) {
            return gettext('Export Only');
        } else if (format === constants.SHARING_OPTIONS.EDIT_AND_EXPORT) {
            return gettext('Edit and Export');
        }
    };

    ExportInstance.prototype.getSharingHelpText = gettext(
        '<strong>Private</strong>: Only you can edit and export.'
        + '<br/> <strong>Export Only</strong>: You can edit and export, other users can only export.'
        + '<br/> <strong>Edit and Export</strong>: All users can edit and export.'
    );

    /**
     * isNew
     *
     * Determines if an export has been saved or not
     *
     * @returns {Boolean} - Returns true if the export has been saved, false otherwise.
     */
    ExportInstance.prototype.isNew = function () {
        return !ko.utils.unwrapObservable(this._id);
    };

    ExportInstance.prototype.getSaveText = function () {
        if (this.is_odata_config()) {
            return gettext('Save');
        }
        return this.isNew() ? gettext('Create') : gettext('Save');
    };

    /**
     * isReservedOdataColumn
     *
     * determines if a column is reserved for odata exports and cannot be deleted
     *
     * returns {Boolean}
     */
    ExportInstance.prototype.isReservedOdataColumn = function (column, tableId) {
        if (!this.is_odata_config()) {
            return false;
        }
        if (tableId === 0) {
            return (column.formatProperty() === 'formid' || column.formatProperty() === 'caseid') && column.tags().indexOf('info') !== -1;
        }
        return column.formatProperty() === 'number';
    };

    /**
     * save
     *
     * Saves an ExportInstance by serializing it and POSTing it
     * to the server.
     */
    ExportInstance.prototype.save = function () {
        var self = this,
            serialized;

        self.saveState(constants.SAVE_STATES.SAVING);
        serialized = self.toJS();
        $.post({
            url: self.saveUrl,
            data: JSON.stringify(serialized),
            success: function (data) {
                self.recordSaveAnalytics(function () {
                    self.saveState(constants.SAVE_STATES.SUCCESS);
                    utils.redirect(data.redirect);
                });
            },
            error: function () {
                self.saveState(constants.SAVE_STATES.ERROR);
            },
        });
    };

    /**
     * recordSaveAnalytics
     *
     * Reports to analytics what type of configurations people are saving
     * exports as.
     *
     * @param {function} callback - A function to be called after recording analytics.
     */
    ExportInstance.prototype.recordSaveAnalytics = function (callback) {
        var analyticsAction = this.is_daily_saved_export() ? 'Saved' : 'Regular',
            analyticsExportType = utils.capitalize(this.type()),
            args,
            eventCategory;

        googleAnalytics.track.event("Create Export", analyticsExportType, analyticsAction);
        if (this.export_format === constants.EXPORT_FORMATS.HTML) {
            args = ["Create Export", analyticsExportType, 'Excel Dashboard', '', {}];
            // If it's not new then we have to add the callback in to redirect
            if (!this.isNew()) {
                args.push(callback);
            }
            googleAnalytics.track.event.apply(null, args);
        }
        if (this.isNew()) {
            eventCategory = constants.ANALYTICS_EVENT_CATEGORIES[this.type()];
            googleAnalytics.track.event(eventCategory, 'Custom export creation', '');
            kissmetricsAnalytics.track.event("Clicked 'Create' in export edit page", {}, callback);
        } else if (this.export_format !== constants.EXPORT_FORMATS.HTML) {
            callback();
        }
    };

    ExportInstance.prototype.toggleShowDeleted = function (table) {
        table.showDeleted(!table.showDeleted());

        if (this.numberOfAppsToProcess > 0 && table.showDeleted()) {
            $('#export-process-deleted-applications').modal('show');
        }
    };

    /**
     * showDeidColumn
     *
     * Makse the deid column visible and scrolls the user back to the
     * top of the export.
     */
    ExportInstance.prototype.showDeidColumn = function () {
        utils.animateToEl('#field-select', function () {
            this.isDeidColumnVisible(true);
        }.bind(this));
    };

    ExportInstance.prototype.toJS = function () {
        return ko.mapping.toJS(this, ExportInstance.mapping);
    };

    /**
     * addUserDefinedTableConfiguration
     *
     * This will add a new table to the export configuration and seed it with
     * one column, row number.
     *
     * @param {ExportInstance} instance
     * @param {Object} e - The window's click event
     */
    ExportInstance.prototype.addUserDefinedTableConfiguration = function (instance, e) {
        e.preventDefault();
        instance.tables.push(new UserDefinedTableConfiguration({
            selected: true,
            doc_type: 'TableConfiguration',
            label: 'Sheet',
            is_user_defined: true,
            path: [],
            columns: [
                {
                    doc_type: 'RowNumberColumn',
                    tags: ['row'],
                    item: {
                        doc_type: 'ExportItem',
                        path: [{
                            doc_type: 'PathNode',
                            name: 'number',
                        }],
                    },
                    selected: true,
                    is_advanced: false,
                    is_deprecated: false,
                    label: 'number',
                    deid_transform: null,
                    repeat: null,
                },
            ],
        }));
    };

    ExportInstance.mapping = {
        include: [
            '_id',
            'name',
            'description',
            'sharing',
            'tables',
            'type',
            'export_format',
            'split_multiselects',
            'transform_dates',
            'format_data_in_excel',
            'include_errors',
            'is_deidentified',
            'domain',
            'app_id',
            'case_type',
            'xmlns',
            'is_daily_saved_export',
            'show_det_config_download',
            'selected_geo_property',
        ],
        tables: {
            create: function (options) {
                if (options.data.is_user_defined) {
                    return new UserDefinedTableConfiguration(options.data);
                } else {
                    return new TableConfiguration(options.data);
                }
            },
        },
    };

    /**
     * TableConfiguration
     * @class
     *
     * The TableConfiguration represents one excel sheet in an export.
     * It contains a list of columns and other presentation properties
     */
    var TableConfiguration = function (tableJSON) {
        var self = this;
        const urlParams = new URLSearchParams(window.location.search);
        // Whether or not to show advanced columns in the UI
        self.showAdvanced = ko.observable(false);
        self.showDeleted = ko.observable(urlParams.get('delete_filter_enabled') === 'True');

        self.showDeprecated = ko.observable(urlParams.get('load_deprecated') === 'True');
        ko.mapping.fromJS(tableJSON, TableConfiguration.mapping, self);
    };

    TableConfiguration.prototype.isVisible = function () {
        // Not implemented
        return true;
    };

    TableConfiguration.prototype.toggleShowAdvanced = function (table) {
        table.showAdvanced(!table.showAdvanced());
    };

    TableConfiguration.prototype.toggleShowDeprecated = function (table) {
        table.showDeprecated(!table.showDeprecated());

        const queryString = window.location.search;
        const urlParams = new URLSearchParams(queryString);
        if (urlParams.get('load_deprecated') !== 'True' && table.showDeprecated()) {
            $('#export-process-deprecated-properties').modal('show');
        }
    };

    TableConfiguration.prototype._select = function (select) {
        _.each(this.columns(), function (column) {
            column.selected(select && column.isVisible(this));
        }.bind(this));
    };

    /**
     * selectAll
     *
     * @param {TableConfiguration} table
     *
     * Selects all visible columns in the table.
     */
    TableConfiguration.prototype.selectAll = function (table) {
        table._select(true);
    };

    /**
     * selectNone
     *
     * @param {TableConfiguration} table
     *
     * Deselects all visible columns in the table.
     */
    TableConfiguration.prototype.selectNone = function (table) {
        table._select(false);
    };

    /**
     * useLabels
     *
     * @param {TableConfiguration} table
     *
     * Uses the question labels for the all the label values in the column.
     */
    TableConfiguration.prototype.useLabels = function (table) {
        _.each(table.columns(), function (column) {
            if (column.isQuestion() && !column.isUserDefined) {
                column.label(column.item.label() || column.label());
            }
        });
    };

    /**
     * useIds
     *
     * @param {TableConfiguration} table
     *
     * Uses the question ids for the all the label values in the column.
     */
    TableConfiguration.prototype.useIds = function (table) {
        _.each(table.columns(), function (column) {
            if (column.isQuestion() && !column.isUserDefined) {
                column.label(column.item.readablePath() || column.label());
            }
        });
    };

    TableConfiguration.prototype.getColumn = function (path) {
        return _.find(this.columns(), function (column) {
            return readablePath(column.item.path()) === path;
        });
    };

    TableConfiguration.prototype.addUserDefinedExportColumn = function (table, e) {
        e.preventDefault();
        table.columns.push(new UserDefinedExportColumn({
            selected: true,
            is_editable: true,
            deid_transform: null,
            doc_type: 'UserDefinedExportColumn',
            label: '',
            custom_path: [],
        }));
    };

    TableConfiguration.mapping = {
        include: ['name', 'path', 'columns', 'selected', 'label', 'is_deleted', 'doc_type', 'is_user_defined'],
        columns: {
            create: function (options) {
                if (options.data.doc_type === 'UserDefinedExportColumn') {
                    return new UserDefinedExportColumn(options.data);
                } else {
                    return new ExportColumn(options.data);
                }
            },
        },
        path: {
            create: function (options) {
                return new PathNode(options.data);
            },
        },
    };

    /**
     * UserDefinedTableConfiguration
     * @class
     *
     * This represents a table configuration that has been defined by the user. It
     * is very similar to a TableConfiguration except that the user defines the
     * path to where the new sheet should be.
     *
     * The customPathString for a table should always end in [] since a new export
     * table should be an array.
     *
     * When specifying questions/properties in a user defined table, you'll need
     * to include the base table path in the property. For example:
     *
     * table path: form.repeat[]
     * question path: form.repeat[].question1
     */
    var UserDefinedTableConfiguration = function (tableJSON) {
        var self = this;
        ko.mapping.fromJS(tableJSON, TableConfiguration.mapping, self);
        self.customPathString = ko.observable(readablePath(self.path()));
        self.customPathString.extend({
            required: true,
            pattern: {
                message: gettext('The table path should end with []'),
                params: /^.*\[\]$/,
            },
        });

        self.showAdvanced = ko.observable(false);
        self.showDeleted = ko.observable(false);
        self.showDeprecated = ko.observable(false);
        self.customPathString.subscribe(self.onCustomPathChange.bind(self));
    };
    UserDefinedTableConfiguration.prototype = Object.create(TableConfiguration.prototype);

    UserDefinedTableConfiguration.prototype.onCustomPathChange = function () {
        var rowColumn,
            nestedRepeatCount;
        this.path(customPathToNodes(this.customPathString()));

        // Update the rowColumn's repeat count by counting the number of
        // repeats in the table path
        rowColumn = this.getColumn('number');
        if (rowColumn) {
            nestedRepeatCount = _.filter(this.path(), function (node) { return node.is_repeat(); }).length;
            rowColumn.repeat(nestedRepeatCount);
        }
    };

    /**
     * ExportColumn
     * @class
     *
     * The model that represents a column in an export. Each column has a one-to-one
     * mapping with an ExportItem. The column controls the presentation of that item.
     */
    var ExportColumn = function (columnJSON) {
        var self = this;
        ko.mapping.fromJS(columnJSON, ExportColumn.mapping, self);
        // In some cases case property was having deleted tag present
        // the function removes such exceptions on display
        self.removeDeletedTagFromCaseName();
        // showOptions is used a boolean for whether to show options for user defined option
        // lists. This is used for the feature preview SPLIT_MULTISELECT_CASE_EXPORT
        self.showOptions = ko.observable(false);
        self.userDefinedOptionToAdd = ko.observable('');
        self.isUserDefined = false;
        self.selectedForSort = ko.observable(false);
    };

    /**
     * isQuestion
     *
     * @returns {Boolean} - Returns true if the column is associated with a form question
     *      or a case property, false otherwise.
     */
    ExportColumn.prototype.isQuestion = function () {
        var disallowedTags = ['info', 'case', 'server', 'row', 'app', 'stock'],
            self = this;
        return !_.any(disallowedTags, function (tag) { return _.include(self.tags(), tag); });
    };


    /**
     * addUserDefinedOption
     *
     * This adds an options to the user defined options. This is used for the
     * feature preview: SPLIT_MULTISELECT_CASE_EXPORT
     */
    ExportColumn.prototype.addUserDefinedOption = function () {
        var option = this.userDefinedOptionToAdd();
        if (option) {
            this.user_defined_options.push(option);
        }
        this.userDefinedOptionToAdd('');
    };

    /**
     * removeUserDefinedOption
     *
     * Removes a user defined option.
     */
    ExportColumn.prototype.removeUserDefinedOption = function (option) {
        this.user_defined_options.remove(option);
    };

    /**
     * formatProperty
     *
     * Formats a property/question for display.
     *
     * @returns {string} - Returns a string representation of the property/question
     */
    ExportColumn.prototype.formatProperty = function () {
        if (this.tags().length !== 0) {
            return this.label();
        } else {
            return _.map(this.item.path(), function (node) { return node.name(); }).join('.');
        }
    };

    /**
     * getDeidOptions
     *
     * @returns {Array} - A list of all deid option choices
     */
    ExportColumn.prototype.getDeidOptions = function () {
        return _.map(constants.DEID_OPTIONS, function (value) { return value; });
    };

    /**
     * getDeidOptionText
     *
     * @param {string} deidOption - A deid option
     * @returns {string} - Given a deid option, returns the human readable label
     */
    ExportColumn.prototype.getDeidOptionText = function (deidOption) {
        if (deidOption === constants.DEID_OPTIONS.ID) {
            return gettext('Sensitive ID');
        } else if (deidOption === constants.DEID_OPTIONS.DATE) {
            return gettext('Sensitive Date');
        } else if (deidOption === constants.DEID_OPTIONS.NONE) {
            return gettext('None');
        }
    };

    /**
     * isVisible
     *
     * Determines whether the column is visible to the user.
     *
     * @returns {Boolean} - True if the column is visible false otherwise.
     */
    ExportColumn.prototype.isVisible = function (table) {
        if (this.selected()) {
            return true;
        }

        if (!this.is_advanced() && !this.is_deleted() && !this.is_deprecated()) {
            return true;
        }

        if (table.showAdvanced() && this.is_advanced()) {
            return true;
        }

        if (table.showDeleted() && this.is_deleted()) {
            return true;
        }

        if (table.showDeprecated() && this.is_deprecated()) {
            return true;
        }

        return false;
    };

    /**
     * isCaseName
     *
     * Checks to see if the column is the name of the case property
     *
     * @returns {Boolean} - True if it is the case name property False otherwise.
     */
    ExportColumn.prototype.isCaseName = function () {
        return this.item.isCaseName();
    };

    ExportColumn.prototype.translatedHelp = function () {
        return gettext(this.help_text);
    };

    ExportColumn.prototype.isEditable = function () {
        return false;
    };

    ExportColumn.prototype.removeDeletedTagFromCaseName = function () {
        if (this.isCaseName() && this.is_deleted()) {
            this.is_deleted(false);
            var newTags = _.filter(this.tags(), function (tag) {
                return tag !== "deleted";
            });
            this.tags(newTags);
        }
    };

    ExportColumn.mapping = {
        include: [
            'item',
            'label',
            'is_advanced',
            'is_deleted',
            'is_deprecated',
            'selected',
            'tags',
            'deid_transform',
            'help_text',
            'split_type',
            'user_defined_options',
        ],
        item: {
            create: function (options) {
                return new ExportItem(options.data);
            },
        },
    };

    /*
     * UserDefinedExportColumn
     *
     * This model represents a column that a user has defined the path to the
     * data within the form. It should only be needed for RemoteApps
     */
    var UserDefinedExportColumn = function (columnJSON) {
        var self = this;
        ko.mapping.fromJS(columnJSON, UserDefinedExportColumn.mapping, self);
        self.showOptions = ko.observable(false);
        self.isUserDefined = true;
        self.customPathString = ko.observable(readablePath(self.custom_path())).extend({
            required: true,
        });
        self.customPathString.subscribe(self.customPathToNodes.bind(self));
    };
    UserDefinedExportColumn.prototype = Object.create(ExportColumn.prototype);

    UserDefinedExportColumn.prototype.isVisible = function () {
        return true;
    };

    UserDefinedExportColumn.prototype.formatProperty = function () {
        return _.map(this.custom_path(), function (node) { return node.name(); }).join('.');
    };

    UserDefinedExportColumn.prototype.isEditable = function () {
        return this.is_editable();
    };

    UserDefinedExportColumn.prototype.customPathToNodes = function () {
        this.custom_path(customPathToNodes(this.customPathString()));
    };

    UserDefinedExportColumn.mapping = {
        include: [
            'selected',
            'deid_transform',
            'doc_type',
            'custom_path',
            'label',
            'is_editable',
        ],
        custom_path: {
            create: function (options) {
                return new PathNode(options.data);
            },
        },
    };

    /**
     * ExportItem
     * @class
     *
     * An item for export that is generated from the schema generation
     */
    var ExportItem = function (itemJSON) {
        var self = this;
        ko.mapping.fromJS(itemJSON, ExportItem.mapping, self);
    };

    /**
     * isCaseName
     *
     * Checks to see if the item is the name of the case
     *
     * @returns {Boolean} - True if it is the case name property False otherwise.
     */
    ExportItem.prototype.isCaseName = function () {
        try {
            return this.path()[this.path().length - 1].name() === 'name';
        } catch (error) {
            return false;
        }
    };

    ExportItem.prototype.readablePath = function () {
        return readablePath(this.path());
    };

    ExportItem.mapping = {
        include: ['path', 'label', 'tag'],
        path: {
            create: function (options) {
                return new PathNode(options.data);
            },
        },
    };

    /**
     * PathNode
     * @class
     *
     * An node representing a portion of the path to item to export.
     */
    var PathNode = function (pathNodeJSON) {
        ko.mapping.fromJS(pathNodeJSON, PathNode.mapping, this);
    };

    PathNode.mapping = {
        include: ['name', 'is_repeat'],
    };

    return {
        ExportInstance: ExportInstance,
        ExportColumn: ExportColumn,
        ExportItem: ExportItem,
        PathNode: PathNode,
        customPathToNodes: customPathToNodes,   // exported for tests only
        readablePath: readablePath,             // exported for tests only
    };

});
