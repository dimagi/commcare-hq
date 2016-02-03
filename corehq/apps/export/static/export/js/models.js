Exports.ViewModels.ExportInstance = function(instanceJSON, options) {
    options = options || {};
    var self = this;
    ko.mapping.fromJS(instanceJSON, Exports.ViewModels.ExportInstance.mapping, self);
    self.saveState = ko.observable(Exports.Constants.SAVE_STATES.READY);
    self.saveUrl = options.saveUrl;
};

Exports.ViewModels.ExportInstance.prototype.getFormatOptionValues = function() {
    return _.map(Exports.Constants.EXPORT_FORMATS, function(value, key) { return value; });
};

Exports.ViewModels.ExportInstance.prototype.getFormatOptionText = function(format) {
    if (format === Exports.Constants.EXPORT_FORMATS.HTML) {
        return gettext('Web Page (Excel Dashboards)');
    } else if (format === Exports.Constants.EXPORT_FORMATS.CSV) {
        return gettext('CSV (Zip file)');
    } else if (format === Exports.Constants.EXPORT_FORMATS.XLS) {
        return gettext('Excel 2007');
    } else if (format === Exports.Constants.EXPORT_FORMATS.XLSX) {
        return gettext('Web Page (Excel Dashboards)');
    }
};

Exports.ViewModels.ExportInstance.prototype.isNew = function() {
    return !!ko.utils.unwrapObservable(self._id);
};

Exports.ViewModels.ExportInstance.prototype.getSaveText = function() {
    return this.isNew() ? gettext('Create') : gettext('Save');
};

Exports.ViewModels.ExportInstance.prototype.save = function() {
    var self = this,
        serialized;

    self.saveState(Exports.Constants.SAVE_STATES.SAVING);
    serialized = self.toJSON();
    $.post(self.saveUrl, serialized)
        .success(function(data) {
            var eventCategory,
                redirect = function() { window.location.href = data.redirect; };

            self.saveState(Exports.Constants.SAVE_STATES.SUCCESS);
            self.recordSaveAnalytics();

            if (self.isNew()) {
                eventCategory = Exports.Utils.getEventCategory(self.type());
                ga_track_event(eventCategory, 'Custom export creation', '', {
                    hitCallback: redirect
                });
            } else {
                redirect();
            }
        })
        .fail(function(response) {
            self.saveState(Exports.Constants.SAVE_STATES.ERROR);
        });
};

Exports.ViewModels.ExportInstance.prototype.recordSaveAnalytics = function() {
    var analyticsAction = self.is_daily_saved_export() ? 'Saved' : 'Regular',
        analyticsExportType = _.capitalize(self.type());

    analytics.usage("Create Export", analyticsExportType, analyticsAction);
    if (self.export_format === Exports.Constants.EXPORT_FORMATS.HTML) {
        analytics.usage("Create Export", analyticsExportType, 'Excel Dashboard');
    }
    if (self.isNew()) {
        analytics.workflow("Clicked 'Create' in export edit page");
    }
};

Exports.ViewModels.ExportInstance.prototype.toJS = function() {
    return ko.mapping.toJS(this, Exports.ViewModels.ExportInstance.mapping);
};

Exports.ViewModels.ExportInstance.mapping = {
    include: [
        '_id',
        'name',
        'tables',
        'type',
        'export_format',
        'split_multiselects',
        'transform_dates',
        'include_errors',
        'is_deidentified',
        'is_daily_saved_export',
    ],
    tables: {
        create: function(options) {
            return new Exports.ViewModels.TableConfiguration(options.data);
        }
    }
};

Exports.ViewModels.TableConfiguration = function(tableJSON) {
    var self = this;
    self.showAdvanced = ko.observable(false);
    ko.mapping.fromJS(tableJSON, Exports.ViewModels.TableConfiguration.mapping, self);
};

Exports.ViewModels.TableConfiguration.prototype.isVisible = function() {
    // Not implemented
    return true;
};

Exports.ViewModels.TableConfiguration.prototype.toggleShowAdvanced = function(table) {
    table.showAdvanced(!table.showAdvanced());
};

Exports.ViewModels.TableConfiguration.prototype._select = function(select) {
    _.each(this.columns(), function(column) {
        column.selected(select && column.isVisible(this));
    }.bind(this));
};

Exports.ViewModels.TableConfiguration.prototype.selectAll = function(table) {
    table._select(true);
};

Exports.ViewModels.TableConfiguration.prototype.selectNone = function(table) {
    table._select(false);
};

Exports.ViewModels.TableConfiguration.mapping = {
    include: ['name', 'path', 'columns', 'selected'],
    columns: {
        create: function(options) {
            return new Exports.ViewModels.ExportColumn(options.data);
        }
    }
};

Exports.ViewModels.ExportColumn = function(columnJSON) {
    var self = this;
    ko.mapping.fromJS(columnJSON, Exports.ViewModels.ExportColumn.mapping, self);
};

Exports.ViewModels.ExportColumn.prototype.formatProperty = function() {
    return this.item.path.join('.');
};

Exports.ViewModels.ExportColumn.prototype.isVisible = function(table) {
    return table.showAdvanced() || (!this.is_advanced() || this.selected());
};

Exports.ViewModels.ExportColumn.mapping = {
    include: ['item', 'label', 'is_advanced', 'selected', 'tags'],
    item: {
        create: function(options) {
            return new Exports.ViewModels.ExportItem(options.data);
        }
    }
};

Exports.ViewModels.ExportItem = function(itemJSON) {
    // ExportItem is not modifyable through the UI so we should not make it observable
    var self = this;
    self.path = itemJSON.path;
    self.label = itemJSON.label;
    self.tag = itemJSON.tag;
};

Exports.ViewModels.ExportItem.prototype.isCaseName = function() {
    return self.path[self.path.length - 1] === 'case_name';
};
