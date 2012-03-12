
var CaseNavigation = Backbone.Router.extend({
    
    initialize: function() {
        // _.bindAll(this); 
    },
    
    routes: {
        "case/:case":  "case",    // #view/caseid
        "":            "clear"
    },
    
});

var Case = Backbone.Model.extend({
    
    initialize: function() {
        _.bindAll(this, 'getProperty'); 
    },
    idAttribute: "case_id",
    
    getProperty: function (property) {
        if (property === "name") {
            return this.get("properties").case_name;
        }
        var root = this.get(property);
        return root ? root : this.get("properties")[property];
    }
});

var Details = Backbone.Model.extend({
    // nothing here yet
});
    
    
var CaseView = Backbone.View.extend({
    tagName: 'tr', // name of (orphan) root tag in this.el
    initialize: function() {
        _.bindAll(this, 'render', 'select', 'deselect', 'toggle');
        this.selected = false; 
    },
    events: {
        "click": "toggle"
    },
    toggle: function () {
        if (this.selected) {
            this.deselect();
            this.trigger("deselected");
        } else {
            this.select();
        }
    }, 
    select: function () {
        this.selected = true;
        $(this.el).addClass("selected");
        this.trigger("selected");
    }, 
    
    deselect: function () {
        this.selected = false;
        $(this.el).removeClass("selected");
    }, 
    
    render: function(){
        var self = this;
        _(this.options.columns).each(function (col) {
            $("<td />").text(self.model.getProperty(col.field) || "?").appendTo($(self.el));
        });
        
        return this; 
    }
});

        
var CaseList = Backbone.Collection.extend({
    initialize: function() {
        _.bindAll(this, 'url', 'setUrl'); 
    },
    model: Case,
    url: function () {
        return this.caseUrl;
    },
    setUrl: function (url) {
        this.caseUrl = url;
    }
    
});

var CaseListView = Backbone.View.extend({
    
    initialize: function(){
        _.bindAll(this, 'render', 'appendItem', 'appendAll'); 
      
        this.caseMap = {};
      
        this.detailsShort = new Details();
        this.detailsShort.set(this.options.details);
      
        this.caseList = new CaseList();
        this.caseList.bind('add', this.appendItem);
        this.caseList.bind('reset', this.appendAll);
        if (this.options.cases) {
            this.caseList.reset(this.options.cases);
        } else if (this.options.caseUrl) {
            this.caseList.setUrl(this.options.caseUrl);
            this.caseList.fetch();
        }
    },
    
    render: function () {
	    var self = this;
	    this.el = $('<section />').attr("id", "case-list").addClass("span4");
        var table = $("<table />").addClass("table table-striped datatable").appendTo($(this.el));
        var thead = $("<thead />").appendTo(table);
        var theadrow = $("<tr />").appendTo(thead);
        _(this.detailsShort.get("columns")).each(function (col) {
            $("<th />").text(col.header[self.options.language] || "?").appendTo(theadrow);
        });
        var tbody = $("<tbody />").appendTo(table);
        _(this.caseList.models).each(function(item){ 
            self.appendItem(item);
        });
        return this;
    },
    appendItem: function (item) {
        var self = this;
        var caseView = new CaseView({
            model: item,
            columns: this.detailsShort.get("columns")
        });
        caseView.on("selected", function () {
            if (self.selectedCaseView) {
                self.selectedCaseView.deselect();
            }
            if (self.selectedCaseView !== this) {
                self.selectedCaseView = this;
                self.trigger("case:selected", this);
            } 
        });
        caseView.on("deselected", function () {
            self.selectedCaseView = null;
            self.trigger("case:deselected", this);
        });
      
        $('table tbody', this.el).append(caseView.render().el);
        this.caseMap[item.id] = caseView;
      
    },
    appendAll: function () {
        this.caseList.each(this.appendItem);
    }, 
});

var CaseDetailsView = Backbone.View.extend({
    initialize: function(){
        _.bindAll(this, 'render'); 
      
        this.details = new Details();
        this.details.set(this.options.details);
        this.render();
    },
    
    render: function () {
        var self = this;
        if (!this._everRendered) {
            this.el = $('<section />').attr("id", "case-details").addClass("span8");
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
                $("<th />").text(col.header[self.options.language] || "?").appendTo(row);
                $("<td />").text(self.model.getProperty(col.field) || "?").appendTo(row);
            });
        }
        return this;
    },               
});

var CaseMainView = Backbone.View.extend({
    
    initialize: function () {
        _.bindAll(this, 'render', 'selectCase', 'fetchCaseList');
        this.el = this.options.el;
        var self = this;
        this.router = new CaseNavigation();
        this.router.on("route:case", function (caseId) {
            self.listView.caseMap[caseId].select();
        });
        this.router.on("route:clear", function () {
            if (self.listView.selectedCaseView) {
                self.listView.selectedCaseView.deselect();
                self.listView.selectedCaseView.trigger("deselected");
            }
        });
        this.listView = new CaseListView({details: this.options.listDetails,
                                          cases: this.options.cases,
                                          case_type: this.options.case_type,
                                          language: this.options.language,
                                          caseUrl: this.options.caseUrl });
        $(this.listView.render().el).appendTo($(this.el));
        this.detailsView = new CaseDetailsView({details: this.options.summaryDetails,
                                                language: this.options.language});
        $(this.detailsView.render().el).appendTo($(this.el));
        $("<div />").addClass("clear").appendTo($(this.el));
        this.listView.on("case:selected", function (caseView) {
            self.selectCase(caseView);
            self.router.navigate("case/" + caseView.model.id);
        });
        this.listView.on("case:deselected", function (caseView) {
            self.selectCase(null);
            self.router.navigate("");
        });
        
    },
    
    selectCase: function (caseView) {
        if (caseView === null) {
            this.detailsView.model = null;
        } else {
            this.detailsView.model = caseView.model;
        }
        this.detailsView.render();
    },
    
    fetchCaseList: function () {
        this.listView.caseList.fetch();
    },
    
    render: function () {
        return this;
    }
});
