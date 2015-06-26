if (typeof cloudCare === 'undefined') {
    var cloudCare = {};
}

cloudCare.EMPTY = '---';

var _caseListLoadError = function (model, response) {
    var errorMessage = translatedStrings.caseListError;
    hideLoadingCallback();
    console.error(response.responseText);

    if (response.status === 400 || response.status === 401) {
        errorMessage = response.responseText;
    }
    showError(errorMessage, $("#cloudcare-notifications"));
};

cloudCare.CASE_PROPERTY_MAP = {
    // IMPORTANT: if you edit this you probably want to also edit
    // the corresponding map in the app_manager
    // (corehq/apps/app_manager/models.py)
    'external-id': 'external_id',
    'date-opened': 'date_opened',
    'status': '@status', // must map to corresponding function on the Case model
    'name': 'case_name',
    'owner_id': '@owner_id'
};

cloudCare.Case = Backbone.Model.extend({
    
    initialize: function () {
        _.bindAll(this, 'getProperty', 'status'); 
    },
    idAttribute: "case_id",
    
    getProperty: function (property) {
        if (cloudCare.CASE_PROPERTY_MAP[property] !== undefined) {
            property = cloudCare.CASE_PROPERTY_MAP[property];
        }
        if (property.indexOf("@") == 0) {
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
                value: this.getProperty(col.field) ? this.getProperty(col.field) : cloudCare.EMPTY
            };
        }, this);
    },

    caseDetailsLabel: function(language) {
        var caseLabel = (this.get("module") ?
                         this.get("module").get("case_label")[language] :
                         this.get("appConfig").module.get("case_label")[language]) + 
                        ": ";
        if (caseLabel === "Cases: "){
            caseLabel = "";
        }
        var caseName = this.get("properties").case_name;
        return caseLabel + caseName;

    },

    childCaseUrl: function() {
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

cloudCare.Details = Backbone.Model.extend({
    // nothing here yet
});

cloudCare.caseViewMixin = {
    lookupField: function (field) {
        return this.model.getProperty(field);
    },
    delegationFormName: function () {
        var self = this;
        if (self.options.delegation) {
            var formId = self.model.getProperty('form_id');
            var module = self.options.appConfig.module;
            var form = module.getFormByUniqueId(formId);
            return localize(form.get('name'), self.options.language);
        } else {
            throw "not in delegation mode"
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
            text = self.lookupField(col.field),
            td = $("<td/>");
        if (text) {
            return td.text(text);
        } else {
            return td.append(
                $('<small/>').text(cloudCare.EMPTY)
            );
        }
    }
};

// Though this is called the CaseView, it actually displays the case
// summary as a line in the CaseListView. Not to be confused with the
// CaseDetailsView
cloudCare.CaseView = Selectable.extend(cloudCare.caseViewMixin).extend({
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

cloudCare.CaseList = Backbone.Collection.extend({
    initialize: function () {
        var self = this;
        _.bindAll(self, 'url', 'setUrl');
    },
    model: cloudCare.Case,
    url: function () {
        return this.caseUrl;
    },
    setUrl: function (url) {
        this.caseUrl = url;
    },
});

cloudCare.CaseListView = Backbone.View.extend({
    
    initialize: function () {
        _.bindAll(this, 'render', 'appendItem', 'appendAll'); 
      
        this.caseMap = {};
      
        this.detailsShort = new cloudCare.Details();
        this.detailsShort.set(this.options.details);

        this.caseList = new cloudCare.CaseList();
        this.caseList.bind('add', this.appendItem);
        this.caseList.bind('reset', this.appendAll);
        if (this.options.cases) {
            this.caseList.reset(this.options.cases);
        } else if (this.options.caseUrl) {
            this.caseList.setUrl(this.options.caseUrl);
            showLoading();
            this.caseList.fetch({
                success: hideLoadingCallback,
                error: _caseListLoadError
            });
        }
    },
    render: function () {
	    var self = this;
	    self.el = $('<section />').attr("id", "case-list").addClass("span7");
        var table = $("<table />").addClass("table table-striped datatable").css('clear', 'both').appendTo($(self.el));
        var thead = $("<thead />").appendTo(table);
        var theadrow = $("<tr />").appendTo(thead);
        if (self.options.delegation) {
            $('<th/>').appendTo(theadrow);
        }
        _(self.detailsShort.get("columns")).each(function (col) {
            $("<th />").append('<i class="icon-white"></i> ').append(localize(col.header, self.options.language)).appendTo(theadrow);
        });
        var tbody = $("<tbody />").appendTo(table);
        _(self.caseList.models).each(function(item){
            self.appendItem(item);
        });

        return self;
    },
    appendItem: function (item) {
        var self = this;
        var caseView = new cloudCare.CaseView({
            model: item,
            columns: self.detailsShort.get("columns"),
            delegation: self.options.delegation,
            appConfig: self.options.appConfig,
            language: self.options.language
        });
        // set the app config on the case if it's there
        // so that other events can access it later
        item.set("appConfig", self.options.appConfig);
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
        self.caseMap[item.id] = caseView;

    },
    appendAll: function () {
        this.caseList.each(this.appendItem);
        $('table', this.el).dataTable({
            bFilter: true,
            bPaginate: false,
            bSort: true,
            oLanguage: {
                "sSearch": "Filter cases:"
            },
            sScrollX: $('#case-list').css('width'),
            bScrollCollapse: true
        });
        var $dataTablesFilter = $(".dataTables_filter");
        $dataTablesFilter.css('float', 'none').css('padding', '3px').addClass('span12');
        $dataTablesFilter.addClass("form-search");
        var $inputField = $dataTablesFilter.find("input"),
            $inputLabel = $dataTablesFilter.find("label");

        $dataTablesFilter.append($inputField);
        $inputField.attr("id", "dataTables-filter-box");
        $inputField.addClass("search-query").addClass("input-large");
        $inputField.attr("placeholder", "Filter...");

        $inputLabel.attr("for", "dataTables-filter-box");
        $inputLabel.text('Filter cases:');
        this.el.parent().before($('<section class="row-fluid" />').append($dataTablesFilter));
    }
});

cloudCare.CaseDetailsView = Backbone.View.extend(cloudCare.caseViewMixin).extend({
    initialize: function () {
        _.bindAll(this, 'render');
        this.details = new cloudCare.Details();
        this.details.set(this.options.details);
        this.render();
    },
    
    render: function () {
        var self = this;
        if (!self._everRendered) {
            self.el = $('<section />').attr("id", "case-details").addClass("span5");
            self._everRendered = true;
        }
        $(self.el).html(""); // clear
        if (self.model) {
            var table = $("<table />").addClass("table table-striped datatable").appendTo($(self.el));
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

cloudCare.CaseMainView = Backbone.View.extend({
    initialize: function () {
        var self = this;
        _.bindAll(this, 'render', 'selectCase', 'fetchCaseList');
        // adding an internal section so that the filter button displays correctly
        self.el = self.options.el;
        self.section = $('<section class="row-fluid" />');
        self.section.appendTo(self.el);
        // this is copy-pasted
        self.delegation = self.options.appConfig.form_index === 'task-list';
        self.listView = new cloudCare.CaseListView({
            details: self.options.listDetails,
            cases: self.options.cases,
            case_type: self.options.case_type,
            language: self.options.language,
            caseUrl: self.options.caseUrl,
            appConfig: self.options.appConfig,
            delegation: self.delegation
        });
        $(self.listView.render().el).appendTo($(self.section));
        self.detailsView = new cloudCare.CaseDetailsView({
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

cloudCare.CaseSelectionModel = Backbone.Model.extend({
});

cloudCare.CaseSelectionView = Backbone.View.extend({
    el: $("#case-crumbs"),
    template: _.template($("#template-crumbs").html()),

    initialize: function (){
        var self = this;
        self.model = new cloudCare.CaseSelectionModel();
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
} );
