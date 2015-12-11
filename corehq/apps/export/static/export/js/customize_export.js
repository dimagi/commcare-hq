var CustomExportView = {
    wrap: function (o, translations) {
        var self = ko.mapping.fromJS(o);

        self.utils = {
            rename: function (field, rename_map) {
                if (rename_map.hasOwnProperty(field)) {
                    return rename_map[field];
                } else {
                    return field;
                }
            },
            stripIndex: function (index) {
                var stripped;
                if (self.custom_export.type() === 'form') {
                    index = ko.utils.unwrapObservable(index);
                    stripped = index.replace(/^#.form.(.*).#$/, '$1');
                    if (index !== stripped) {
                        return stripped;
                    }
                    stripped = index.replace(/^#.(.*).#$/, '$1 (meta)');
                } else {
                    stripped = index.replace(/^#.(.*).#$/, '$1');
                }
                stripped = stripped.replace(/.#./g, ' > ');
                return stripped;
            },
            tableHeader: function (index) {
                index = ko.utils.unwrapObservable(index);
                var stripped = self.utils.stripIndex(index);
                if (self.custom_export.type() === 'form') {
                    if (index === '#') {
                        return translations.forms;
                    }
                    return translations.repeat + stripped;
                } else {
                    return {
                        '#': translations.cases,
                        'actions': translations.case_history,
                        'actions > indices': translations.history_to_parents,
                        'indices': translations.parent_cases,
                    }[stripped] || stripped;
                }
            },
            parseField: function (field, index, field_tag) {
                var tags = field_tag ? [field_tag] : [];
                var stripped;
                field = ko.utils.unwrapObservable(field);
                index = ko.utils.unwrapObservable(index);
                var server = {
                    _rev: 0,
                    doc_type: 0,
                    '-deletion_id': 0,
                    initial_processing_complete: 0
                };
                if (field in server) {
                    return {tags: ['server'].concat(tags), field: field};
                } else if (field === 'id') {
                    return {tags: ['row'].concat(tags), field: 'number'};
                }

                var renamed_field = field;
                if (self.custom_export.type() === 'form' && index === '#') {
                    var rename_map = {
                        "form.case.@case_id": "form.meta.caseid",
                        "form.meta.timeEnd": "form.meta.completed_time",
                        "form.meta.timeStart": "form.meta.started_time",
                        "_id": "form.meta.formid"
                    };
                    field = self.utils.rename(field, rename_map);
                    var patterns = [
                        {regex: /^form\.meta\.(.*)$/, tag: 'info'},
                        {regex: /^form\.case\.(.*)$/, tag: 'case'},
                        {regex: /^form\.subcase_\d(.*)$/, tag: 'subcase', no_replace: true},
                        {regex: /^form\.([#@].*)$/, tag: 'tag'},
                        {regex: /^form\.(.*)$/, tag: ''}
                    ], pattern, stripped;
                    for (var i = 0; i < patterns.length; i++) {
                        pattern = patterns[i];
                        stripped = !pattern.no_replace ? field.replace(pattern.regex, '$1') : field;
                        if (field !== stripped) {
                            return {tags: [pattern.tag].concat(tags), field: stripped};
                        }

                        if (pattern.no_replace && pattern.regex.test(field)) {
                            tags += pattern.tag;
                        }
                    }

                    return {tags: ['server'].concat(tags), field: renamed_field};
                } else if (self.custom_export.type() === 'case') {

                    if (index === '#') {
                        var meta = {
                            _id: 0,
                            closed: 0,
                            closed_by: 0,
                            closed_on: 0,
                            domain: 0,
                            computed_modified_on_: 0,
                            server_modified_on: 0,
                            modified_on: 0,
                            opened_by: 0,
                            opened_on: 0,
                            owner_id: 0,
                            user_id: 0,
                            type: 0,
                            version: 0,
                            external_id: 0
                        };
                        rename_map = {
                            '_id': 'case_id',
                            'type': 'case_type',
                            'user_id': 'last_modified_by_user_id',
                            'modified_on': 'last_modified_date',
                            'server_modified_on': 'server_last_modified_date',
                            'opened_by': 'opened_by_user_id',
                            'opened_on': 'opened_date',
                            'closed_by': 'closed_by_user_id',
                            'closed_on': 'closed_date'
                        };
                        renamed_field = self.utils.rename(field, rename_map);
                        if (meta.hasOwnProperty(field)) {
                            return {tags: ['info'].concat(tags), field: renamed_field};
                        }
                    } else if (/#\.indices\.#$/.exec(index)) {
                        var rename_map = {
                            'identifier': 'relationship',
                            'referenced_id': 'case_id',
                            'referenced_type': 'case_type'
                        };
                        renamed_field = self.utils.rename(field, rename_map);

                    } else if (index === '#.actions.#') {
                        stripped = field.replace(
                            /^updated_(?:un)?known_properties\.(.*)$/,
                            '$1'
                        );
                        if (stripped !== field) {
                            return {tags: ['update'].concat(tags), field: stripped};
                        }
                    }
                }
                return {tags: [''].concat(tags), field: renamed_field};
            },
            showTable: function (table) {
                var index = table.index();
                var excluded = index in CustomExportView.excludedTables;
                var columns = table.column_configuration();
                if (!excluded && columns.length === 2) {
                    // just an '' field and an 'id' field field, no info
                    var blank_field = columns[0],
                        id_field = columns[1];
                    if (id_field.index() === 'id' && blank_field.index() === '') {
                        excluded = true;
                    }
                }
                return !excluded || table.selected();
            },
            actuallyShowTable: function (table) {
                if (self.repeatsEnabled()) {
                    return self.utils.showTable(table);
                } else {
                    return table.index() === '#' || table.selected();
                }
            },
            putInDefaultOrder: function (index, columns) {
                // http://stackoverflow.com/questions/2998784/how-to-output-integers-with-leading-zeros-in-javascript
                // [11] < [2], so have to pad numbers
                function pad10(a){return(1e15+a+"").slice(-10)}

                var order = ko.utils.unwrapObservable(self.default_order[index]);
                var order_index = {};
                _(order).each(function (index, i) {
                    order_index[index] = pad10(i);
                });
                var tag_order = {
                    '': 0,
                    'case': 1,
                    'info': 2,
                    'update': 2.5, // for case history only
                    'server': 3,
                    'tag': 4,
                    'row': 5
                };
                return _(columns).sortBy(function (column) {
                    var key;
                    if (order_index.hasOwnProperty(column.index())) {
                        key = [0, order_index[column.index()]];
                    } else {
                        key = [1, tag_order[column._niceField.tags[0]], column._niceField.field];
                    }
                    return key;
                });
            }
        };

        self.repeatsEnabled = ko.computed(function () {
            var n_tables = _(self.table_configuration()).filter(
                    self.utils.showTable
            ).length;
            if (self.allow_repeats()) {
                return n_tables > 1;
            } else {
                return _(self.table_configuration()).filter(function (table) {
                    return table.index() !== '#' && table.selected();
                }).length > 0;
            }
        });

        _(self.table_configuration()).each(function (table) {
            table.show_deleted = ko.observable(false);
            // assumes unselected
            var unselected;
            var columns = table.column_configuration();
            var spliceIdx = 0;

            _(columns).each(function (column, idx) {
                var niceField = self.utils.parseField(column.index, table.index, column.tag());
                var special = ko.utils.unwrapObservable(column.special);
                if (special) {
                    niceField['field'] = special;
                }
                column._niceField = niceField;
                column.isCaseName = ko.computed(function () {
                    return ko.utils.unwrapObservable(column.special) === 'case_name';
                });
                column.showOptions = ko.observable(false);
                column.newOption = ko.observable("");
                column.addOption = function(e) {
                    if (this.newOption() != "") {
                        if (this.options.indexOf(this.newOption()) === -1) {
                            this.options.push(this.newOption());
                            this.allOptions.push(this.newOption());
                        }
                        this.newOption("");
                    }
                    return false;
                }.bind(column);
                if (!self.minimal() && !column.selected() && !spliceIdx) {
                    spliceIdx = idx;
                }
            });

            // Splice out unselected and put them at the end and reorder
            if (!self.minimal()) {
                unselected = table.column_configuration.splice(spliceIdx, columns.length);
                unselected = self.utils.putInDefaultOrder(table.index(), unselected);
                table.column_configuration.push.apply(
                    table.column_configuration,
                    unselected
                );
            }
        });

        self.showDeidColumn = ko.observable(function () {
            return _(self.table_configuration()).some(function (table) {
                return table.selected() && _(table.column_configuration()).some(function (column) {
                    return column.selected() && column.transform() && column.is_sensitive();
                });
            });
        }());

        self.animateShowDeidColumn = function () {
            $('html, body').animate({
                scrollTop: $('#field-select').offset().top + 'px'
            }, 'slow', undefined, function () {
                self.showDeidColumn(true);
            });

        };

        self.setAllSelected = function (table, selected) {
            _(table.column_configuration()).each(function (column) {
                if (!selected || table.show_deleted() || column.show()) {
                    column.selected(selected);
                }
            });
        };
        self.selectAll = function (table) {
            self.setAllSelected(table, true);
        };
        self.selectNone = function (table) {
            self.setAllSelected(table, false);
        };

        self.make_tables = function () {
            var tables = _(self.table_configuration()).filter(function (table) {
                return table.selected();
            }).map(function (table) {
                return {
                    display: table.display,
                    index: table.index,
                    columns: _(table.column_configuration()).filter(function (column) {
                        return column.selected() && !(column.isCaseName() && self.custom_export.is_safe());
                    }).map(function (column) {
                        var is_sensitive = column.transform() && (column.is_sensitive() || !ko.utils.unwrapObservable(column.special )),
                            col = {
                                index: column.index,
                                display: column.display,
                                transform: column.transform() || null, // it doesn't save '' well
                                is_sensitive: Boolean(is_sensitive)
                        };
                        if (self.export_type() === 'form') {
                            if (self.custom_export.split_multiselects() && column.allOptions()) {
                                col.doc_type = 'SplitColumn';
                            } else {
                                col.doc_type = 'ExportColumn';
                            }
                        } else if (column.doc_type() === 'SplitColumn'){
                            col.doc_type = column.doc_type();
                            col.options = column.options();
                        }
                        return col;
                    })
                }
            });
            tables = ko.mapping.toJS(tables);
            if (tables.length > 1) {
                _(tables).each(function (table) {
                    if (!_(table.columns).some(
                                function (column) { return column.index === 'id'; }
                            )) {
                        table.columns.splice(0, 0, {
                            index: 'id',
                            display: 'row.number',
                            transform: null
                        });
                    }
                });
            }
            return tables;
        };

        self.output = function (preview) {
            var output = ko.mapping.toJS({
                custom_export: self.custom_export,
                presave: self.presave,
                export_stock: self.export_stock,
                preview: preview
            });
            output.custom_export.tables = self.make_tables();
            return JSON.stringify(output);
        };

        self.save = function (preview) {
            self.save.state('saving' + (preview ? '-preview': ''));
            $.post(self.urls.save(), self.output(preview)).done(function (data) {

                var redirect = function(){
                    window.location.href = data.redirect;
                };

                // If the button had said "Create"
                if (!self.custom_export._id || !self.custom_export._id()) {
                    var event_category = null;
                    if (self.custom_export.type() == "form") {
                        event_category = 'Form Exports';
                    } else if (self.custom_export.type() == "case") {
                        event_category = 'Case Exports';
                    }

                    if (event_category) {
                        // Record an event
                        ga_track_event(event_category, 'Custom export creation', "", {
                            'hitCallback': redirect
                        });
                        return;
                    }
                }
                redirect();
            }).fail(function (response) {
                var data = $.parseJSON(response.responseText);
                self.save.state('error');
                alert('There was an error saving: ' + data.error);
            });
        };
        self.save.state = ko.observable('save');

        self.save_no_preview = function() {
            var exportType = self.export_type();
            exportType = _(exportType).capitalize();
            var action = "Regular";
            if (self.presave()) {
                action = "Saved";
            }
            analytics.usage("Create Export", exportType, action);
            if (self.custom_export.default_format() === 'html') {
                analytics.usage("Create Export", exportType, "Excel Dashboard");
            }

            if (!self.custom_export._id || !self.custom_export._id()) {
                analytics.workflow("Clicked 'Create' in export edit page");
            }
            self.save(false);
        };

        self.save_preview = function() {
            self.save(true);
        };

        self.row_label_classes = function(row) {
            return (row === 'no data' || row === 'deleted') ? "label label-warning" : "label";
        };

        setTimeout(function () {
            _(self.table_configuration()).each(function (table) {
                if (!table.display()) {
                    table.display(self.utils.tableHeader(table.index));
                }
                _(table.column_configuration()).each(function (column) {
                    if (!column.display()) {
                        var parsed = column._niceField;
                        var prefixed_tags = ["case", "meta", "info", "server", "tag", "row"];
                        var prefix = '';
                        for (var i = 0; i < parsed.tags.length; i++) {
                            for (var j = 0; j < prefixed_tags.length; j++) {
                                if (parsed.tags[i] === prefixed_tags[j]) {
                                    prefix = parsed.tags[i] + '.';
                                    break;
                                }
                            }
                        }
                        var display = prefix + parsed.field;
                        column.display(display);
                    }
                });
            });
        }, 0);

        return self;
    },
    excludedTables: {
        '#.#export_tag.#': 0,
        '#.export_tag.#': 0,
        '#.location_.#': 0,
        '#.referrals.#': 0,
        '#.xform_ids.#': 0
    }
};
