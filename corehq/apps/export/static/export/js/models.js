/* globals Exports, hqDefine */

hqDefine('export/js/models.js', function () {

var ExportInstance = function(instanceJSON, options) {
    options = options || {};
    var self = this;
    ko.mapping.fromJS(instanceJSON, ExportInstance.mapping, self);
    self.saveState = ko.observable(Exports.Constants.SAVE_STATES.READY);
    self.saveUrl = options.saveUrl;
    // If any column has a deid transform, show deid column
    self.isDeidColumnVisible = ko.observable(self.is_deidentified() || _.any(self.tables(), function(table) {
        return table.selected() && _.any(table.columns(), function(column) {
            return column.selected() && column.deid_transform();
        });
    }));
};

ExportInstance.prototype.getFormatOptionValues = function() {
    return _.map(Exports.Constants.EXPORT_FORMATS, function(value, key) { return value; });
};

ExportInstance.prototype.getFormatOptionText = function(format) {
    if (format === Exports.Constants.EXPORT_FORMATS.HTML) {
        return gettext('Web Page (Excel Dashboards)');
    } else if (format === Exports.Constants.EXPORT_FORMATS.CSV) {
        return gettext('CSV (Zip file)');
    } else if (format === Exports.Constants.EXPORT_FORMATS.XLS) {
        return gettext('Excel (older versions)');
    } else if (format === Exports.Constants.EXPORT_FORMATS.XLSX) {
        return gettext('Excel 2007');
    }
};

ExportInstance.prototype.isNew = function() {
    return !ko.utils.unwrapObservable(this._id);
};

ExportInstance.prototype.getSaveText = function() {
    return this.isNew() ? gettext('Create') : gettext('Save');
};

ExportInstance.prototype.save = function() {
    var self = this,
        serialized;

    self.saveState(Exports.Constants.SAVE_STATES.SAVING);
    serialized = self.toJS();
    $.post(self.saveUrl, JSON.stringify(serialized))
        .success(function(data) {
            self.recordSaveAnalytics(function() {
                self.saveState(Exports.Constants.SAVE_STATES.SUCCESS);
                Exports.Utils.redirect(data.redirect);
            });
        })
        .fail(function(response) {
            self.saveState(Exports.Constants.SAVE_STATES.ERROR);
        });
};

ExportInstance.prototype.recordSaveAnalytics = function(callback) {
    var analyticsAction = this.is_daily_saved_export() ? 'Saved' : 'Regular',
        analyticsExportType = _.capitalize(this.type()),
        args,
        eventCategory;

    analytics.usage("Create Export", analyticsExportType, analyticsAction);
    if (this.export_format === Exports.Constants.EXPORT_FORMATS.HTML) {
        args = ["Create Export", analyticsExportType, 'Excel Dashboard'];
        // If it's not new then we have to add the callback in to redirect
        if (!this.isNew()) {
            args.push(callback);
        }
        analytics.usage.apply(null, args);
    }
    if (this.isNew()) {
        eventCategory = Exports.Constants.ANALYTICS_EVENT_CATEGORIES[this.type()];
        analytics.usage(eventCategory, 'Custom export creation', '');
        analytics.workflow("Clicked 'Create' in export edit page", callback);
    } else if (this.export_format !== Exports.Constants.EXPORT_FORMATS.HTML) {
        callback();
    }
};

ExportInstance.prototype.showDeidColumn = function() {
    Exports.Utils.animateToEl('#field-select', function() {
        this.isDeidColumnVisible(true);
    }.bind(this));
};

ExportInstance.prototype.toJS = function() {
    return ko.mapping.toJS(this, ExportInstance.mapping);
};

ExportInstance.mapping = {
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
            return new TableConfiguration(options.data);
        }
    }
};

var TableConfiguration = function(tableJSON) {
    var self = this;
    self.showAdvanced = ko.observable(false);
    ko.mapping.fromJS(tableJSON, TableConfiguration.mapping, self);
};

TableConfiguration.prototype.isVisible = function() {
    // Not implemented
    return true;
};

TableConfiguration.prototype.toggleShowAdvanced = function(table) {
    table.showAdvanced(!table.showAdvanced());
};

TableConfiguration.prototype._select = function(select) {
    _.each(this.columns(), function(column) {
        column.selected(select && column.isVisible(this));
    }.bind(this));
};

TableConfiguration.prototype.selectAll = function(table) {
    table._select(true);
};

TableConfiguration.prototype.selectNone = function(table) {
    table._select(false);
};

TableConfiguration.prototype.useLabels = function(table) {
    _.each(table.columns(), function(column) {
        if (column.isQuestion()) {
            column.label(column.item.label() || column.label());
        }
    });
};

TableConfiguration.prototype.useIds = function(table) {
    _.each(table.columns(), function(column) {
        if (column.isQuestion()) {
            column.label(column.item.readablePath() || column.label());
        }
    });
};

TableConfiguration.mapping = {
    include: ['name', 'path', 'columns', 'selected', 'label', 'is_deleted'],
    columns: {
        create: function(options) {
            return new ExportColumn(options.data);
        }
    },
    path: {
        create: function(options) {
            return new PathNode(options.data);
        }
    }
};

var ExportColumn = function(columnJSON) {
    var self = this;
    ko.mapping.fromJS(columnJSON, ExportColumn.mapping, self);
    self.showOptions = ko.observable(false);
    self.userDefinedOptionToAdd = ko.observable('');
};

ExportColumn.prototype.isQuestion = function() {
    var disallowedTags = ['info', 'case', 'server', 'row', 'app', 'stock'],
        self = this;
    return !_.any(disallowedTags, function(tag) { return _.include(self.tags(), tag); });
};

ExportColumn.prototype.addUserDefinedOption = function() {
    var option = this.userDefinedOptionToAdd();
    if (option) {
        this.user_defined_options.push(option);
    }
    this.userDefinedOptionToAdd('');
};

ExportColumn.prototype.removeUserDefinedOption = function(option) {
    this.user_defined_options.remove(option);
};

ExportColumn.prototype.formatProperty = function() {
    if (this.tags().length !== 0){
        return this.label();
    } else {
        return _.map(this.item.path(), function(node) { return node.name(); }).join('.');
    }
};

ExportColumn.prototype.getDeidOptions = function() {
    return _.map(Exports.Constants.DEID_OPTIONS, function(value, key) { return value; });
};

ExportColumn.prototype.getDeidOptionText = function(deidOption) {
    if (deidOption === Exports.Constants.DEID_OPTIONS.ID) {
        return gettext('Sensitive ID');
    } else if (deidOption === Exports.Constants.DEID_OPTIONS.DATE) {
        return gettext('Sensitive Date');
    } else if (deidOption === Exports.Constants.DEID_OPTIONS.NONE) {
        return gettext('None');
    }
};

ExportColumn.prototype.isVisible = function(table) {
    return table.showAdvanced() || (!this.is_advanced() || this.selected());
};

ExportColumn.prototype.isCaseName = function() {
    return this.item.isCaseName();
};

ExportColumn.prototype.translatedHelp = function() {
    return gettext(this.help_text);
};

ExportColumn.mapping = {
    include: [
        'item',
        'label',
        'is_advanced',
        'selected',
        'tags',
        'deid_transform',
        'help_text',
        'split_type',
        'user_defined_options',
    ],
    item: {
        create: function(options) {
            return new ExportItem(options.data);
        }
    }
};

var ExportItem = function(itemJSON) {
    var self = this;
    ko.mapping.fromJS(itemJSON, ExportItem.mapping, self);
};

ExportItem.prototype.isCaseName = function() {
    return this.path()[this.path().length - 1].name === 'name';
};

ExportItem.prototype.readablePath = function() {
    return _.map(this.path(), function(pathNode) {
        return pathNode.name();
    }).join('.');
};

ExportItem.mapping = {
    include: ['path', 'label', 'tag'],
    path: {
        create: function(options) {
            return new PathNode(options.data);
        }
    }
};

var PathNode = function(pathNodeJSON) {
    ko.mapping.fromJS(pathNodeJSON, PathNode.mapping, this);
};

PathNode.mapping = {
    include: ['name', 'is_repeat']
};

return {
    ExportInstance: ExportInstance,
    ExportColumn: ExportColumn,
    ExportItem: ExportItem,
};

});
