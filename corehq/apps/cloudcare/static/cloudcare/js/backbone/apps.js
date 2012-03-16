cloudCare = {};

cloudCare.dispatch = _.extend({}, Backbone.Events);

var AppNavigation = Backbone.Router.extend({
    
    initialize: function() {
        // _.bindAll(this); 
    },
    
    routes: {
        "view/:app":                        "app",                              
        "view/:app/:module":                "app:module",               
        "view/:app/:module/:form":          "app:module:form",               
        "view/:app/:module/:form/:case":    "app:module:form:case",    
        "":                                 "clear"
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
        _.bindAll(this, 'render', 'appendItem', "getAppView", "clearSelectionState");
        this.appList = new AppList();
        this.appList.reset(this.options.apps);
        this._appViews = {};
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
        
        this._appViews[item.id] = appView;
        
        appView.on("selected", function () {
            if (self.selectedAppView) {
                self.selectedAppView.deselect();
            }
            if (self.selectedAppView !== this) {
                self.selectedAppView = this;
                cloudCare.dispatch.trigger("app:selected", this);
            }
        });
        appView.on("deselected", function () {
            self.selectedAppView = null;
            cloudCare.dispatch.trigger("app:deselected", this);
        });
      
        $('ul', this.el).append(appView.render().el);
    },
    getAppView: function (appId) {
        return this._appViews[appId];
    },
    
    clearSelectionState: function () {
        this.selectedAppView = null;
        _(_(this._appViews).values()).each(function (view) {
            view.deselect();
        });
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
        _.bindAll(this, 'render', 'appendItem', 'updateModules', 'getModuleView', 'clearSelectionState');
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
        this._moduleViews = {};
        
        var self = this;
        var ul = $("<ul />").addClass("nav nav-list").appendTo($(this.el));
        $("<li />").addClass("nav-header").text("Modules").appendTo(ul);
        _(this.moduleList.models).each(function(item){ 
            self.appendItem(item);
        });
        self.trigger("modules:updated");
    },
    appendItem: function (item) {
        var self = this;
        var moduleView = new ModuleView({
            model: item,
            language: this.options.language
            
        });
        this._moduleViews[item.get("index")] = moduleView;
        
        moduleView.on("selected", function () {
            if (self.selectedModuleView) {
                self.selectedModuleView.deselect();
            }
            if (self.selectedModuleView !== this) {
                self.selectedModuleView = this;
                cloudCare.dispatch.trigger("module:selected", this.model);
            }
        });
        moduleView.on("deselected", function () {
            self.selectedModuleView = null;
            cloudCare.dispatch.trigger("module:deselected", this.model);
        });
      
        $('ul', this.el).append(moduleView.render().el);
    },
    getModuleView: function (moduleIndex) {
        return this._moduleViews[moduleIndex];
    },
    clearSelectionState: function () {
        this.selectedModuleView = null;
        _(_(this._moduleViews).values()).each(function (view) {
            view.deselect();
        });
    }
});

var FormListView = Backbone.View.extend({
    el: $('#form-list'), 
    initialize: function () {
        _.bindAll(this, 'render', 'appendForm', 'getFormView', 'clearSelectionState');
        this._formViews = {};
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
        this._formViews[form.get("index")] = formView;
        formView.on("selected", function () {
            if (self.selectedFormView) {
                self.selectedFormView.deselect();
            }
            if (self.selectedFormView !== this) {
                self.selectedFormView = this;
                cloudCare.dispatch.trigger("form:selected", this.model);
            }
        });
        formView.on("deselected", function () {
            self.selectedFormView = null;
            cloudCare.dispatch.trigger("form:deselected", this.model);
        });
        
	    $('ul', this.el).append(formView.render().el);
    },
    clearSelectionState: function () {
        this.selectedFormView = null;
        _(_(this._formViews).values()).each(function (view) {
            view.deselect();
        });
    },
    getFormView: function (formIndex) {
        return this._formViews[formIndex];
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
        
        cloudCare.dispatch.on("form:selected", function (form) {
            self.selectForm(form);
            
        });
        cloudCare.dispatch.on("form:deselected", function (form) {
            self.selectForm(null);
            // self.trigger("form:deselected", form);
        });
        cloudCare.dispatch.on("module:selected", function (module) {
            self.showModule(module);
        });
        cloudCare.dispatch.on("module:deselected", function (module) {
            self.showModule(null);
            
        });
        
        this.setModel(this.model);
    },
    setModel: function (app) {
        this.model = app;
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
	            // go play the form. this is a little sketchy
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
	                appConfig: {"app_id": form.get("app_id"),
	                            "module_index": form.get("module_index"),
	                            "form_index": form.get("index")},
	                language: formListView.options.language,
	                // TODO: clean up how filtering works
	                caseUrl: self.options.caseUrlRoot + "?properties/case_type=" + formListView.model.get("case_type")
	            });
	            cloudCare.dispatch.on("case:selected", function (caseModel) {
	                formListView.enterForm = $("<a />").text("Enter " + form.getLocalized("name", self.options.language)).addClass("btn btn-primary").appendTo(
	                        $(formListView.caseView.detailsView.el));
	                formListView.enterForm.click(function () {
	                    var url = getFormUrl(self.options.urlRoot, form.get("app_id"), 
	                                         form.get("module_index"), form.get("index"));
	                    window.location.href = url + "?case_id=" + caseModel.id;
	                });
	            });
	            cloudCare.dispatch.on("case:deselected", function (caseModel) {
	                if (formListView.enterForm) {
	                    formListView.enterForm.detach();
	                    formListView.enterForm = null;                      
	                }
	            });
	            
	            formListView.caseView.listView.caseList.on("reset", function () {
	                cloudCare.dispatch.trigger("cases:updated");
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
        _.bindAll(this, 'render', 'selectApp', "clearCases", "clearForms", "clearModules", "clearAll");
        var self = this;

        this._selectedModule = null;
        this._selectedForm = null;
        this._selectedCase = null;
        this.router = new AppNavigation();
        this.appListView = new AppListView({
            apps: this.options.apps,
            language: this.options.language
        });
        cloudCare.dispatch.on("app:selected", function (app) {
            self.router.navigate("view/" + app.model.id);
            self.selectApp(app.model.id);
        });
        cloudCare.dispatch.on("app:deselected", function (app) {
            this._selectedModule = null;
            self.router.navigate("");
            self.selectApp(null);
        });
        this.appView = new AppView({
            // if you pass in model: it will auto-populate the view
            model: this.options.model, 
            language: this.options.language,
            caseUrlRoot: this.options.caseUrlRoot,
            urlRoot: this.options.urlRoot
        });
        this.appView.moduleListView.on("modules:updated", function () {
            // this selects an appropriate module any time they are updated.
            // we have to be careful to clear this field anytime a module
            // is deselected
            if (self._selectedModule !== null) {
                this.getModuleView(self._selectedModule).select();
            }
            self._selectedModule = null;
        });
        cloudCare.dispatch.on("cases:updated", function () {
            // same trick but with cases
            if (self._selectedCase !== null) {
                self.appView.formListView.caseView.listView.caseMap[self._selectedCase].select();
            }
            self._selectedCase = null;
        });

        // incoming routes
        this.router.on("route:clear", function () {
            self.clearAll();
        });
        
        var selectApp = function (appId) {
            self.appListView.getAppView(appId).select();
        };
        
        var selectModule = function (moduleIndex) {
            var modView = self.appView.moduleListView.getModuleView(moduleIndex);
            if (modView) {
                modView.select();
            }
            // other event handling magic uses this to select the module
            // after it gets loaded. 
            self._selectedModule = moduleIndex;
        };
        
        var selectForm = function (formIndex) {
            var formView = self.appView.formListView.getFormView(formIndex);
            if (formView) {
                formView.select();
            } 
            self._selectedForm = formIndex;
        };
        
        var selectCase = function (caseId) {
            var caseMainView = self.appView.formListView.caseView;
            if (caseMainView) {
                var caseView = caseMainView.listView.caseMap[caseId];
                if (caseView) {
                    caseView.select();
                }
            }
            self._selectedCase = caseId; 
        };
        
        this.router.on("route:app", function (appId) {
            self.clearModules();
            selectApp(appId);
        });
        this.router.on("route:app:module", function (appId, moduleIndex) {
            self.clearForms();
            selectApp(appId);
            selectModule(moduleIndex);
        });
        this.router.on("route:app:module:form", function (appId, moduleIndex, formIndex) {
            self.clearForms();
            selectApp(appId);
            selectModule(moduleIndex);
            selectForm(formIndex);
        });
        this.router.on("route:app:module:form:case", function (appId, moduleIndex, formIndex, caseId) {
            self.clearCases();
            selectApp(appId);
            selectModule(moduleIndex);
            selectForm(formIndex);
            selectCase(caseId);
        });
        
        
        // setting routes
        cloudCare.dispatch.on("module:selected", function (module) {
            self.router.navigate("view/" + module.get("app_id") + 
                                 "/" + module.get("index"));
            // hack to resolve annoying event-driven dependencies (see below)
            self.trigger("module:selected");
        });
        self.on("module:selected", function () {
            // magic pairing with the above to support proper selection ordering
            if (self._selectedForm !== null) {
                self.appView.formListView.getFormView(self._selectedForm).select();
            }
            self._selectedForm = null;
        });
        
        cloudCare.dispatch.on("module:deselected", function (module) {
            self.router.navigate("view/" + module.get("app_id"));
            self.clearModules();
        });
        cloudCare.dispatch.on("form:selected", function (form) {
            self.router.navigate("view/" + form.get("app_id") + 
                                 "/" + form.get("module_index") + 
                                 "/" + form.get("index"));
            
        });
        cloudCare.dispatch.on("form:deselected", function (form) {
            self.router.navigate("view/" + form.get("app_id") + 
                                 "/" + form.get("module_index"));
            self.clearForms();
        });
        cloudCare.dispatch.on("case:selected", function (caseModel) {
            var appConfig = caseModel.get("appConfig");
            self.router.navigate("view/" + appConfig.app_id + 
                                 "/" + appConfig.module_index + 
                                 "/" + appConfig.form_index +
                                 "/" + caseModel.id);
        });
        cloudCare.dispatch.on("case:deselected", function (caseModel) {
            var appConfig = caseModel.get("appConfig");
            self.router.navigate("view/" + appConfig.app_id + 
                                 "/" + appConfig.module_index + 
                                 "/" + appConfig.form_index);
        });
        
        
    },
    
    selectApp: function (appId) {
        var self = this;
        if (appId === null) {
            this.clearAll();
            
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
    clearCases: function () {
        // TODO
        this._selectedCase = null;
        
    },
    clearForms: function () {
        this.clearCases();
        this._selectedForm = null;
        this.appView.formListView.clearSelectionState();
        this.appView.selectForm(null);
    },
    clearModules: function () {
        this.clearForms();
        this._selectedModule = null;
        this.appView.moduleListView.clearSelectionState();
        this.appView.showModule(null);
    },
    clearAll: function () {
        this.clearModules();
        this.appListView.clearSelectionState();
        this.app = null;
        this.appView.setModel(null);
        this.appView.render();
    },
    
    render: function () {
        return this;
    }
});
