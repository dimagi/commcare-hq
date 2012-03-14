
               
var AppNavigation = Backbone.Router.extend({
    
    initialize: function() {
        // _.bindAll(this); 
    },
    
    routes: {
        "view/:app":   "app",    // #view/appid
        "":            "clear"
    },
    
});


var AppSummary = Backbone.Model.extend({
    idAttribute: "_id"
});

var AppSummaryView = Selectable.extend({
    tagName: 'li', 
    initialize: function() {
        _.bindAll(this, 'render', 'toggle', 'select', 'deselect');
    },
    render: function() {
        $("<a />").text(this.model.get("name")).appendTo($(this.el));
        return this; 
    }
});

var AppList = Backbone.Collection.extend({
    model: AppSummary,
});

var AppListView = Backbone.View.extend({
    el: $('#app-list'), 
    
    initialize: function(){
        _.bindAll(this, 'render', 'appendItem');
        this.appList = new AppList();
        this.appList.reset(this.options.apps);
        this.render();
    },
    
    render: function () {
        var self = this;
        var ul = $("<ul />").addClass("nav nav-list").appendTo($(this.el));
        $("<li />").addClass("nav-header").text("Apps").appendTo(ul);
        _(this.appList.models).each(function(item){ 
            self.appendItem(item);
        });
    },
    appendItem: function (item) {
        var self = this;
        var appView = new AppSummaryView({
            model: item
        });
        
        appView.on("selected", function () {
            if (self.selectedAppView) {
                self.selectedAppView.deselect();
            }
            if (self.selectedAppView !== this) {
                self.selectedAppView = this;
                self.trigger("app:selected", this);
            }
        });
        appView.on("deselected", function () {
            self.selectedAppView = null;
            self.trigger("app:deselected", this);
        });
      
        $('ul', this.el).append(appView.render().el);
    }
});

var App = Backbone.Model.extend({
    idAttribute: "_id",
    initialize: function () {
        _.bindAll(this, "updateModules");
        var self = this;
        this.updateModules();
        this.on("change", function () {
            this.updateModules();
        });
    },
    urlRoot: function () {
        return this.get("urlRoot");
    },
    updateModules: function () {
        var self = this;
        if (this.get("modules")) {
            var index = 0;
            this.modules = _(this.get("modules")).map(function (module) {
                var ret = new Module(module);
                ret.set("app_id", self.id);
                ret.set("index", index);
                index++;
                return ret;
            });
            this.trigger("modules-changed");
        } 
    }
});

var Form = Backbone.Model.extend({
    initialize: function () {
        _.bindAll(this, 'getLocalized');
    },
    getLocalized: getLocalizedString
});

var FormView = Selectable.extend({
    tagName: 'li', 
    initialize: function() {
        _.bindAll(this, 'render', 'toggle', 'select', 'deselect');
    },
    render: function () {
        $("<a />").text(this.model.getLocalized("name", this.options.language)).appendTo($(this.el));
        return this;
    }
});

var Module = Backbone.Model.extend({
    initialize: function () {
        _.bindAll(this, 'getLocalized', 'updateForms', 'getDetail');
        this.updateForms();
        this.on("change", function () {
            this.updateForms();
        });
    },
    getLocalized: getLocalizedString,
    
    getDetail: function (type) {
        return _(this.get("details")).find(function (elem) {
            return elem.type === type;
        });
    },
    
    updateForms: function () {
        var self = this;
        if (this.get("forms")) {
            var index = 0;
            this.forms = _(this.get("forms")).map(function (form) {
                var ret = new Form(form);
                ret.set("app_id", self.get("app_id"));
                ret.set("module_index", self.get("index"));
                ret.set("index", index);
                index++;
                return ret;
            });
            this.trigger("forms-changed");
        } 
    } 
});

var ModuleView = Selectable.extend({
    tagName: 'li', 
    initialize: function() {
        _.bindAll(this, 'render', 'toggle', 'select', 'deselect');
    },
    render: function() {
        $("<a />").text(this.model.getLocalized("name", this.options.language)).appendTo($(this.el));
        return this;
    }
});

var ModuleList = Backbone.Collection.extend({
    model: Module
});

var ModuleListView = Backbone.View.extend({
    el: $('#module-list'), 
    initialize: function () {
        _.bindAll(this, 'render', 'appendItem', 'updateModules');
        var self = this;
        this.moduleList = new ModuleList([], {
            language: this.options.language
        });
        this.moduleList.on("reset", function () {
            self.updateModules();
        });
        this.render();
    },
    render: function () {
        this.updateModules();
    },
    updateModules: function () {
        // clear
        $(this.el).html("");
        var self = this;
        var ul = $("<ul />").addClass("nav nav-list").appendTo($(this.el));
        $("<li />").addClass("nav-header").text("Modules").appendTo(ul);
        _(this.moduleList.models).each(function(item){ 
            self.appendItem(item);
        });
    },
    appendItem: function (item) {
        var self = this;
        var moduleView = new ModuleView({
            model: item,
            language: this.options.language
            
        });
        moduleView.on("selected", function () {
            if (self.selectedModuleView) {
                self.selectedModuleView.deselect();
            }
            if (self.selectedModuleView !== this) {
                self.selectedModuleView = this;
                self.trigger("module:selected", this);
            }
        });
        moduleView.on("deselected", function () {
            self.selectedModuleView = null;
            self.trigger("module:deselected", this);
        });
      
        $('ul', this.el).append(moduleView.render().el);
    }
});

var FormListView = Backbone.View.extend({
    el: $('#form-list'), 
    initialize: function () {
        _.bindAll(this, 'render', 'appendForm');
    },
    render: function () {
        var self = this;
        $(this.el).html("");
        if (this.model) {
	        var formUl = $("<ul />").addClass("nav nav-list").appendTo($(this.el));
	        $("<li />").addClass("nav-header").text("Forms").appendTo(formUl);
	        _(this.model.forms).each(function (form) {
	            self.appendForm(form);
	        });
        }
        return this;
    },
    appendForm: function (form) {
        var self = this;
        var formView = new FormView({
            model: form,
            language: this.options.language
        });
        formView.on("selected", function () {
            if (self.selectedFormView) {
                self.selectedFormView.deselect();
            }
            if (self.selectedFormView !== this) {
                self.selectedFormView = this;
                self.trigger("form:selected", this.model);
            }
        });
        formView.on("deselected", function () {
            self.selectedFormView = null;
            self.trigger("form:deselected", this.model);
        });
        
	    $('ul', this.el).append(formView.render().el);
    }
});

var AppView = Backbone.View.extend({
    
    initialize: function(){
        _.bindAll(this, 'render', 'setModel', 'showModule');
        var self = this;
        this.moduleListView = new ModuleListView({
            language: this.options.language
        });
        this.formListView = new FormListView({
            language: this.options.language
        });
        
        this.formListView.on("form:selected", function (form) {
            self.selectForm(form);
            
        });
        this.formListView.on("form:deselected", function (form) {
            self.selectForm(null);
        });
        this.moduleListView.on("module:selected", function (moduleView) {
            self.showModule(moduleView.model);
        });
        this.moduleListView.on("module:deselected", function (app) {
            self.showModule(null);
        });
        
        this.setModel(this.model);
    },
    setModel: function (app) {
        this.model = app;
        var self = this;
        if (app) {
            this.moduleListView.moduleList.reset(this.model.modules);
	    }
    },
    showModule: function (module) {
        this.formListView.model = module;
        this.formListView.render();
    },
    selectForm: function (form) {
        var self = this;
        var formListView = this.formListView;
        if (form) {
            if (form.get("requires") === "none") {
	            // go play the form
	            var url = getFormUrl(self.options.urlRoot, form.get("app_id"), 
	                                 form.get("module_index"), form.get("index"));
	            window.location.href = url;
            } else if (form.get("requires") === "case") {
	            var listDetails = formListView.model.getDetail("case_short");
	            var summaryDetails = formListView.model.getDetail("case_long");
	            // clear anything existing
	            if (formListView.caseView) {
	                $(formListView.caseView.el).html("");
	            }
	            formListView.caseView = new CaseMainView({                    
	                el: $("#cases"),
	                listDetails: listDetails,
	                summaryDetails: summaryDetails,
	                language: formListView.options.language,
	                // TODO: clean up how filtering works
	                caseUrl: self.options.caseUrlRoot + "?properties/case_type=" + formListView.model.get("case_type")
	            });
	            formListView.caseView.listView.on("case:selected", function (caseView) {
	                formListView.enterForm = $("<a />").text("Enter " + form.getLocalized("name", self.options.language)).addClass("btn btn-primary").appendTo(
	                        $(formListView.caseView.detailsView.el));
	                formListView.enterForm.click(function () {
	                    var url = getFormUrl(self.options.urlRoot, form.get("app_id"), form.get("module_index"), form.get("index"));
	                    window.location.href = url + "?case_id=" + caseView.model.id;
	                });
	            });
	            formListView.caseView.listView.on("case:deselected", function (caseView) {
	                if (formListView.enterForm) {
	                    formListView.enterForm.detach();
	                    formListView.enterForm = null;                      
	                }
	            });
	        }
        } else {
            if (formListView.caseView) {
                $(formListView.caseView.el).html("");
            }
        }
    },
    render: function () {
        // clear details when rerendering
        this.showModule(null);
        if (!this.model) {
            this.moduleListView.moduleList.reset([]);
        } else {
            this.moduleListView.moduleList.reset(this.model.modules);
        }
        return this;
    }
});

var AppMainView = Backbone.View.extend({
    el: $('#app-main'),
     
    initialize: function () {
        _.bindAll(this, 'render', 'selectApp'); 
        var self = this;
        this.router = new AppNavigation();
        this.router.on("route:app", function (appId) {
            // TODO
            self.selectApp(appId);
        });
        this.router.on("route:clear", function () {
            // TODO
        });
        this.appListView = new AppListView({
            apps: this.options.apps,
            language: this.options.language
        });
        this.appListView.on("app:selected", function (app) {
            self.selectApp(app.model.id);
        });
        this.appListView.on("app:deselected", function (app) {
            self.selectApp(null);
        });
        this.appView = new AppView({
            // if you pass in model: it will auto-populate the view
            model: this.options.model, 
            language: this.options.language,
            caseUrlRoot: this.options.caseUrlRoot,
            urlRoot: this.options.urlRoot
        });
    },
    
    selectApp: function (appId) {
        // TODO: this.router.navigate("view/" + appId);
        var self = this;
        if (appId === null) {
            this.app = null;
            this.appView.setModel(null);
            this.appView.render();
        }
        else {
            this.app = new App({
	            _id: appId,
	        });
	        this.app.set("urlRoot", this.options.appUrlRoot);
	        this.app.fetch({
	            success: function (model, response) {
	                self.appView.setModel(model);
	                self.appView.render();           
	            }
	        });
	    }
    },
    
    render: function () {
        return this;
    }
});
