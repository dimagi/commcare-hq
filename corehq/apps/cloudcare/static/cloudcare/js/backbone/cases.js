
if (typeof cloudCare === 'undefined') {
    var cloudCare = {};
}

cloudCare.CASE_PROPERTY_MAP = {
    // IMPORTANT: if you edit this you probably want to also edit
    // the corresponding map in the app_manager
    // (corehq/apps/app_manager/models.py)
    'external-id': 'external_id',
    'date-opened': 'date_opened',
    'status': '@status', // must map to corresponding function on the Case model
    'name': 'case_name',
};

cloudCare.Case = Backbone.Model.extend({
    
    initialize: function() {
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
    }
});

cloudCare.Details = Backbone.Model.extend({
    // nothing here yet
});
    

// Though this is called the CaseView, it actually displays the case 
// summary as a line in the CaseListView. Not to be confused with the
// CaseDetailsView
cloudCare.CaseView = Selectable.extend({
    tagName: 'tr', // name of (orphan) root tag in this.el
    initialize: function() {
        _.bindAll(this, 'render', 'select', 'deselect', 'toggle');
        this.selected = false; 
    },
    render: function(){
        var self = this;
        _(this.options.columns).each(function (col) {
            $("<td />").text(self.model.getProperty(col.field) || "?").appendTo(self.el);
        });
        return this; 
    }
});

        
cloudCare.CaseList = Backbone.Collection.extend({
    initialize: function() {
        _.bindAll(this, 'url', 'setUrl'); 
    },
    model: cloudCare.Case,
    url: function () {
        return this.caseUrl;
    },
    setUrl: function (url) {
        this.caseUrl = url;
    }
    
});

cloudCare.CaseListView = Backbone.View.extend({
    
    initialize: function(){
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
            this.caseList.fetch({success: hideLoadingCallback});
        }
    },
    
    render: function () {
	    var self = this;
	    this.el = $('<section />').attr("id", "case-list").addClass("span7");
        var table = $("<table />").addClass("table table-striped datatable").css('clear', 'both').appendTo($(this.el));
        var thead = $("<thead />").appendTo(table);
        var theadrow = $("<tr />").appendTo(thead);
        _(this.detailsShort.get("columns")).each(function (col) {
            $("<th />").append('<i class="icon-hq-white icon-hq-doublechevron"></i> ').append(localize(col.header, self.options.language)).appendTo(theadrow);
        });
        var tbody = $("<tbody />").appendTo(table);
        _(this.caseList.models).each(function(item){ 
            self.appendItem(item);
        });

        return this;
    },
    appendItem: function (item) {
        var self = this;
        var caseView = new cloudCare.CaseView({
            model: item,
            columns: this.detailsShort.get("columns")
        });
        // set the app config on the case if it's there
        // so that other events can access it later
        item.set("appConfig", this.options.appConfig);
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
      
        $('table tbody', this.el).append(caseView.render().el);
        this.caseMap[item.id] = caseView;
      
    },
    appendAll: function () {
        this.caseList.each(this.appendItem);
        $('table', this.el).dataTable({
            'bFilter': true,
            'bPaginate': false,
            'bSort': true,
            "oLanguage": {
                "sSearch": "Filter cases:"
            }
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
    }, 
});

cloudCare.CaseDetailsView = Backbone.View.extend({
    initialize: function(){
        _.bindAll(this, 'render'); 
      
        this.details = new cloudCare.Details();
        this.details.set(this.options.details);
        this.render();
    },
    
    render: function () {
        var self = this;
        if (!this._everRendered) {
            this.el = $('<section />').attr("id", "case-details").addClass("span5");
            this._everRendered = true;    
        }
        $(this.el).html(""); // clear
        if (this.model) {
            var table = $("<table />").addClass("table table-striped datatable").appendTo($(this.el));
            var thead = $("<thead />").appendTo(table);
            var theadrow = $("<tr />").appendTo(thead);
	        $("<th />").attr("colspan", "2").text("Case Details for " + self.model.getProperty("name")).appendTo(theadrow);
	        var tbody = $("<tbody />").appendTo(table);
	        
            _(this.details.get("columns")).each(function (col) {
                var row = $("<tr />").appendTo(table);
                $("<th />").text(localize(col.header, self.options.language)).appendTo(row);
                $("<td />").text(self.model.getProperty(col.field) || "?").appendTo(row);
            });
        }
        return this;
    },               
});

cloudCare.CaseMainView = Backbone.View.extend({
    
    initialize: function () {
        _.bindAll(this, 'render', 'selectCase', 'fetchCaseList');
        // adding an internal section so that the filter button displays correctly
        this.el = this.options.el;
        this.section = $('<section class="row-fluid" />');
        this.section.appendTo(this.el);
        var self = this;
        this.listView = new cloudCare.CaseListView({details: this.options.listDetails,
                                          cases: this.options.cases,
                                          case_type: this.options.case_type,
                                          language: this.options.language,
                                          caseUrl: this.options.caseUrl,
                                          appConfig: this.options.appConfig});
        $(this.listView.render().el).appendTo($(this.section));
        this.detailsView = new cloudCare.CaseDetailsView({details: this.options.summaryDetails,
                                                language: this.options.language,
                                                appConfig: this.options.appConfig});
        $(this.detailsView.render().el).appendTo($(this.section));
        $("<div />").addClass("clear").appendTo($(this.section));
        cloudCare.dispatch.on("case:selected", function (caseModel) {
            self.selectCase(caseModel);
        });
        cloudCare.dispatch.on("case:deselected", function (caseModel) {
            self.selectCase(null);
        });
        
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
        this.listView.caseList.fetch({success: hideLoadingCallback});
    },
    
    render: function () {
        return this;
    }
});

$.extend( $.fn.dataTableExt.oStdClasses, {
    "sSortAsc": "header headerSortDown",
    "sSortDesc": "header headerSortUp",
    "sSortable": "header"
} );
