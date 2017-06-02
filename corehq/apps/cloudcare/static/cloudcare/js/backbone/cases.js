/* globals moment */
hqDefine('cloudcare/js/backbone/cases.js', function () {
    var Selectable = hqImport('cloudcare/js/backbone/shared.js').Selectable;
    var localize = hqImport('cloudcare/js/util.js').localize;
    var showError = hqImport('cloudcare/js/util.js').showError;
    var showLoading = hqImport('cloudcare/js/util.js').showLoading;
    var hideLoadingCallback = hqImport('cloudcare/js/util.js').hideLoadingCallback;
    var isParentField = hqImport('cloudcare/js/util.js').isParentField;
    var cloudCareCases = {};

    cloudCareCases.EMPTY = '---';

    var _caseListLoadError = function (model, response) {
        var errorMessage = translatedStrings.caseListError;
        hideLoadingCallback();
        console.error(response.responseText);

        if (response.status === 400 || response.status === 401) {
            errorMessage = response.responseText;
        }
        showError(errorMessage, $("#cloudcare-notifications"));
    };

    cloudCareCases.CASE_PROPERTY_MAP = {
        // IMPORTANT: if you edit this you probably want to also edit
        // the corresponding map in the app_manager
        // (corehq/apps/app_manager/models.py)
        'external-id': 'external_id',
        'date-opened': 'date_opened',
        'status': '@status', // must map to corresponding function on the Case model
        'name': 'case_name',
        'owner_id': '@owner_id'
    };

    cloudCareCases.Case = Backbone.Model.extend({

        initialize: function () {
            _.bindAll(this, 'getProperty', 'status');
        },
        idAttribute: "case_id",

        getProperty: function (property) {
            if (cloudCareCases.CASE_PROPERTY_MAP[property] !== undefined) {
                property = cloudCareCases.CASE_PROPERTY_MAP[property];
            }
            if (property.indexOf("@") === 0) {
                // we use @ signs to denote function references, since the phone
                // does some magic with them that we need to reproduce here.
                var f = this[property.substring(1)];
                if (f !== undefined) {
                    return f();
                }
            }
            var root = this.get(property);
            return root ? root : this.get("properties")[property];
        },

        status: function () {
            return this.get("closed") ? "closed" : "open";
        },

        caseProperties: function(language) {
            // Returns case-details as key-value pairs
            // there should be a better way to access language var, than passing here
            var raw_columns = this.get("module") ?
                              this.get("module").get("case_details").long.columns :
                              this.get("appConfig").module.get("case_details").long.columns ; // If Parent-child selection is on
            return _.map(raw_columns, function(col){
                return {
                    key: localize(col.header, language),
                    value: this.getProperty(col.field) ? this.getProperty(col.field) : cloudCareCases.EMPTY
                };
            }, this);
        },

        caseDetailsLabel: function(language) {
            return this.get("properties").case_name;

        },

        childCaseUrl: function() {
            var getChildSelectUrl = hqImport('cloudcare/js/util.js').getChildSelectUrl;
            var parentConfig = this.get("appConfig");
            if (!parentConfig) {
                throw "not a parent case";
            }
            var root = window.location.href.replace(Backbone.history.getFragment(), '');
            return getChildSelectUrl(
                root,
                parentConfig.app_id,
                parentConfig.module_index,
                parentConfig.form_index,
                this.id
            );
        },
    });

    cloudCareCases.Details = Backbone.Model.extend({
        // nothing here yet
    });

    cloudCareCases.caseViewMixin = {
        lookupField: function (detailColumn) {
            var parentCase,
                field = detailColumn.field,
                fieldValue;
            if (isParentField(field) && this.model.get('casedb')) {
                parentCase = this.model.get('casedb').get(this.model.get('indices').parent.case_id);
                fieldValue = parentCase.getProperty(field.slice('parent/'.length));
            } else {
                fieldValue = this.model.getProperty(field);
            }
            return this.formatDetailField(fieldValue, detailColumn);
        },
        formatDetailField: function(fieldValue, detailColumn) {
            var agoInterval = detailColumn.time_ago_interval,
                // See corehq/apps/app_manager/models#TimeAgoInterval
                agoIntervalMap = {
                    '1': 'days',
                    '7': 'weeks',
                    '30.4375': 'months',
                    '365.25': 'years'
                },
                agoUnit; // The unit for time-ago (days, months, etc)

            if (!fieldValue) return fieldValue;

            if (detailColumn.format === 'time-ago') {
                agoUnit = agoIntervalMap[Math.abs(agoInterval)];
                if (agoInterval < 0) {
                    fieldValue = moment(fieldValue).diff(new Date(), agoUnit) || 0;
                } else {
                    fieldValue = moment(new Date()).diff(fieldValue, agoUnit) || 0;
                }
            }
            return fieldValue;
        },
        delegationFormName: function () {
            var self = this;
            if (self.options.delegation) {
                var formId = self.model.getProperty('form_id');
                var module = self.options.appConfig.module;
                var form = module.getFormByUniqueId(formId);
                return localize(form.get('name'), self.options.language);
            } else {
                throw "not in delegation mode";
            }
        },
        makeDelegationFormTd: function () {
            var self = this;
            var name;

            try {
                name = self.delegationFormName();
            } catch (e) {
                if (e.type == 'FormLookupError') {
                    name = '?';
                } else {
                    throw e;
                }
            }
            return $('<td/>').text(name);
        },
        makeTd: function (col) {
            var self = this,
                text = self.lookupField(col),
                td = $("<td/>");
            if (text !== null) {
                return td.text(text);
            } else {
                return td.append(
                    $('<small/>').text(cloudCareCases.EMPTY)
                );
            }
        }
    };

    // Though this is called the CaseView, it actually displays the case
    // summary as a line in the CaseListView. Not to be confused with the
    // CaseDetailsView
    cloudCareCases.CaseView = Selectable.extend(cloudCareCases.caseViewMixin).extend({
        tagName: 'tr', // name of (orphan) root tag in this.el
        initialize: function () {
            var self = this;
            _.bindAll(self, 'render', 'select', 'deselect', 'toggle');
            self.selected = false;
        },
        render: function () {
            var self = this;
            if (self.options.delegation) {
                self.makeDelegationFormTd().appendTo(self.el);
            }
            _(self.options.columns).each(function (col) {
                self.makeTd(col).appendTo(self.el);
            });
            return self;
        }
    });

    cloudCareCases.CaseList = Backbone.Collection.extend({
        initialize: function () {
            var self = this;
            _.bindAll(self, 'url', 'setUrl');
            self.casedb = null;
        },
        model: cloudCareCases.Case,
        url: function () {
            return this.caseUrl;
        },
        setUrl: function (url) {
            this.caseUrl = url;
        },
        parse: function(response) {
            if (response.parents) {
                this.casedb = new cloudCareCases.CaseList(response.cases.concat(response.parents));
            }
            return response.cases;
        }
    });

    cloudCareCases.CaseListView = Backbone.View.extend({

        initialize: function () {
            _.bindAll(this, 'render', 'appendItem', 'appendAll');

            this.caseMap = {};

            this.detailsShort = new cloudCareCases.Details();
            this.detailsShort.set(this.options.details);

            this.caseList = new cloudCareCases.CaseList();
            this.caseList.bind('add', this.appendItem);
            this.caseList.bind('reset', this.appendAll);
            if (this.options.cases) {
                this.caseList.reset(this.options.cases);
            } else if (this.options.caseUrl) {
                this.caseList.setUrl(this.options.caseUrl);
                showLoading();
                this.caseList.fetch({
                    data: {
                        requires_parent_cases: this.requiresParentCases(this.detailsShort)
                    },
                    success: hideLoadingCallback,
                    error: _caseListLoadError
                });
            }
        },
        render: function () {
            var self = this,
                $panelBody,
                $panel;
            self.el = $('<section />').attr("id", "case-list").addClass("col-sm-7");
            self.$el = $(self.el);
            $panel = $('<div class="panel panel-default"></div>')
                .append('<div class="panel-heading">Cases</div>');

            $panelBody = $('<div class="panel-body"></div>');
            $panel.append($panelBody);
            self.$el.append($panel);

            var table = $("<table />").addClass("table table-striped table-hover datatable clearfix").appendTo($panelBody);
            var thead = $("<thead />").appendTo(table);
            var theadrow = $("<tr />").appendTo(thead);
            if (self.options.delegation) {
                $('<th/>').appendTo(theadrow);
            }
            _(self.detailsShort.get("columns")).each(function (col) {
                $("<th />").append('<i class="icon-white"></i> ').append(localize(col.header, self.options.language)).appendTo(theadrow);
            });
            var tbody = $("<tbody />").appendTo(table);
            _(self.caseList.models).each(function(caseModel){
                self.appendItem(caseModel);
            });

            return self;
        },
        requiresParentCases: function(details) {
            var columns = details.get('columns');
            return _.any(_.map(columns, function(d) { return d.field; }), isParentField);
        },
        appendItem: function (caseModel) {
            var cloudCare = hqImport('cloudcare/js/backbone/apps.js');
            var self = this;
            caseModel.set('casedb', self.caseList.casedb);
            var caseView = new cloudCareCases.CaseView({
                model: caseModel,
                columns: self.detailsShort.get("columns"),
                delegation: self.options.delegation,
                appConfig: self.options.appConfig,
                language: self.options.language
            });
            // set the app config on the case if it's there
            // so that other events can access it later
            caseModel.set("appConfig", self.options.appConfig);
            caseView.on("selected", function () {
                if (self.selectedCaseView) {
                    self.selectedCaseView.deselect();
                }
                if (self.selectedCaseView !== this) {
                    self.selectedCaseView = this;
                    cloudCare.dispatch.trigger("case:selected", this.model);
                }
            });
            caseView.on("deselected", function () {
                self.selectedCaseView = null;
                cloudCare.dispatch.trigger("case:deselected", this.model);
            });

            $('table tbody', self.el).append(caseView.render().el);
            self.caseMap[caseModel.id] = caseView;

        },
        appendAll: function () {
            var $table;
            this.caseList.each(this.appendItem);
            $table = $('table', this.el);
            $table.css('width', '100%');
            $table.dataTable({
                bFilter: true,
                bPaginate: false,
                bSort: true,
                oLanguage: {
                    "sSearch": "Filter cases:",
                    "sEmptyTable": "No cases available. You must register a case to access this form."
                },
                sScrollX: $('#case-list').outerWidth(),
                bScrollCollapse: true
            });
            var $dataTablesFilter = $(".dataTables_filter");
            $dataTablesFilter.addClass('col-sm-4 form-search form-group');
            var $inputField = $dataTablesFilter.find("input"),
                $inputLabel = $dataTablesFilter.find("label");

            $dataTablesFilter.append($inputField);
            $inputField.attr("id", "dataTables-filter-box");
            $inputField.addClass("search-query").addClass("form-control");
            $inputField.attr("placeholder", "Filter cases");

            $inputLabel.attr("for", "dataTables-filter-box");
            $inputLabel.text('Filter cases:');
            this.el.parent().before($('<section class="row" />').append($dataTablesFilter));
        }
    });

    cloudCareCases.CaseDetailsView = Backbone.View.extend(cloudCareCases.caseViewMixin).extend({
        initialize: function () {
            _.bindAll(this, 'render');
            this.details = new cloudCareCases.Details();
            this.details.set(this.options.details);
            this.render();
        },

        render: function () {
            var self = this,
                $panelBody,
                $panel;
            if (!self._everRendered) {
                self.el = $('<section />').attr("id", "case-details").addClass("col-sm-5");
                self._everRendered = true;
            }
            $(self.el).html(""); // clear

            $panel = $('<div class="panel panel-default"></div>')
                .append('<div class="panel-heading">Case Details</div>');
            $panelBody = $('<div class="panel-default"></div>');
            $panel.append($panelBody);
            $(self.el).append($panel);


            if (self.model) {
                var table = $("<table />").addClass("table table-striped table-hover datatable").appendTo($panelBody);
                var thead = $("<thead />").appendTo(table);
                var theadrow = $("<tr />").appendTo(thead);
                $("<th />").attr("colspan", "2").text("Case Details for " + self.model.getProperty("name")).appendTo(theadrow);
                var tbody = $("<tbody />").appendTo(table);

                _(self.details.get("columns")).each(function (col) {
                    var row = $("<tr />").appendTo(table);
                    $("<th />").text(localize(col.header, self.options.language)).appendTo(row);
                    self.makeTd(col).appendTo(row);
                });
            }
            return self;
        }
    });

    cloudCareCases.CaseMainView = Backbone.View.extend({
        initialize: function () {
            var self = this;
            _.bindAll(this, 'render', 'selectCase', 'fetchCaseList');
            // adding an internal section so that the filter button displays correctly
            self.el = self.options.el;
            self.section = $('<section class="row" />');
            self.section.appendTo(self.el);
            // this is copy-pasted
            self.delegation = self.options.appConfig.form_index === 'task-list';
            self.listView = new cloudCareCases.CaseListView({
                details: self.options.listDetails,
                cases: self.options.cases,
                case_type: self.options.case_type,
                language: self.options.language,
                caseUrl: self.options.caseUrl,
                appConfig: self.options.appConfig,
                delegation: self.delegation
            });
            $(self.listView.render().el).appendTo($(self.section));
            self.detailsView = new cloudCareCases.CaseDetailsView({
                details: self.options.summaryDetails,
                language: self.options.language,
                appConfig: self.options.appConfig,
                delegation: self.delegation
            });
            $(self.detailsView.render().el).appendTo($(self.section));
            $("<div />").addClass("clear").appendTo($(self.section));
        },

        selectCase: function (caseModel) {
            if (caseModel === null) {
                this.detailsView.model = null;
            } else {
                this.detailsView.model = caseModel;
            }
            this.detailsView.render();
        },

        fetchCaseList: function () {
            showLoading();
            this.listView.caseList.fetch({
                success: hideLoadingCallback,
                error: _caseListLoadError
            });
        },

        render: function () {
            return this;
        }
    });

    cloudCareCases.CaseSelectionModel = Backbone.Model.extend({
    });

    cloudCareCases.CaseSelectionView = Backbone.View.extend({
        el: $("#case-crumbs"),
        template: _.template($("#template-crumbs").html()),

        initialize: function (){
            var self = this;
            self.model = new cloudCareCases.CaseSelectionModel();
            self.language = this.options.language;
            self.model.on("change", self.render, this);
        },
        render: function (){
            var self = this;
            var parentCase = self.model.get("parentCase");
            var childCase = self.model.get("childCase");
            var data = {parentCase: null, childCase: null};

            if (parentCase){
                data.parentCase = {};
                data.parentCase.text = parentCase.caseDetailsLabel(self.language);
                data.parentCase.href = parentCase.childCaseUrl();
                data.parentCase.properties = parentCase.caseProperties(self.language);
            }
            if (childCase){
                data.childCase = {};
                data.childCase.text = childCase.caseDetailsLabel(self.language);
                data.childCase.properties = childCase.caseProperties(self.language);
            }
            self.$el.html(self.template(data));
            return self;
        }
    });

    $.extend( $.fn.dataTableExt.oStdClasses, {
        "sSortAsc": "header headerSortDown",
        "sSortDesc": "header headerSortUp",
        "sSortable": "header"
    });
    return cloudCareCases;
});
