
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
    model: Case,
    // url: "{% url cloudcare_get_cases domain %}?user_id={{user_id}}"
});

var CaseListView = Backbone.View.extend({
    el: $('#case-list'), 
    
    initialize: function(){
        _.bindAll(this, 'render', 'appendItem', 'appendAll'); 
      
        this.caseMap = {};
      
        this.detailsShort = new Details();
        this.detailsShort.set(this.options.details);
      
        this.caseList = new CaseList();
        this.caseList.bind('add', this.appendItem);
        this.caseList.bind('reset', this.appendAll);
        this.caseList.reset(this.options.cases);
        this.render();
      
      
    },
    
    render: function () {
	    var self = this;
        var table = $("<table />").appendTo($(this.el));
        var thead = $("<thead />").appendTo(table);
        var theadrow = $("<tr />").appendTo(thead);
        _(this.detailsShort.get("columns")).each(function (col) {
            $("<th />").text(col.header[self.options.language] || "?").appendTo(theadrow);
        });
        var tbody = $("<tbody />").appendTo(table);
        _(this.caseList.models).each(function(item){ 
            self.appendItem(item);
        });
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
        this.caseMap[item.getProperty("case_id")] = caseView;
      
    },
    appendAll: function () {
        this.caseList.each(this.appendItem);
    }, 
});

var CaseDetailsView = Backbone.View.extend({
    el: $('#case-details'),
    
    initialize: function(){
        _.bindAll(this, 'render'); 
      
        this.details = new Details();
        this.details.set(this.options.details);
        this.render();
    },
    
    render: function () {
        var self = this;
        $(this.el).html(""); // clear
        if (this.model) {
            var table = $("<table />").appendTo($(this.el));
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
        _.bindAll(this, 'render', 'selectCase'); 
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
                                          language: this.options.language});
        this.detailsView = new CaseDetailsView({details: this.options.summaryDetails,
                                                language: this.options.language});
        this.listView.on("case:selected", function (caseView) {
            self.selectCase(caseView);
            self.router.navigate("case/" + caseView.model.getProperty("case_id"));
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
    
    render: function () {
        return this;
    }
});
