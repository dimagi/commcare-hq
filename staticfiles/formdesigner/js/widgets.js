if (typeof formdesigner === 'undefined') {
    var formdesigner = {};
}

formdesigner.widgets = (function () {
    var that = {};
    
    that.unchangeableQuestionTypes = [
        "item", "group", "repeat", "datanode", "trigger"
    ];
    
    that.getGroupName = function (path) {
        return path.split("/")[0];
    };
    
    that.getPropertyName = function (path) {
        return path.split("/")[1];
    };
    
    that.baseWidget = function(mugType) {
        // set properties shared by all widgets
        var widget = {};
        // this shared method provides fake inheritance, assuming
        // it is called in a constructor on the object being constructed
        widget.mug = mugType;
                
        widget.getDisplayName = function () {
            // use the display text, or the property name if none found
            return this.definition.lstring ? this.definition.lstring : this.propName;
        }
        
        widget.getLabel = function () {
            var label = $("<label />").text(this.getDisplayName()).attr("for", this.getID()); 
            return label;
        };
        
        widget.getControl = function () {
            throw ("must be overridden");
        };
        
        widget.getID = function () {
            throw ("must be overridden");
        };
        
        
        widget.setValue = function (val) {
            // noop
        };
        
        widget.getValue = function () {
            // noop
        };
        
        
        widget.fireValueChanged = function () {
            var ref = this;
            return function () {
                formdesigner.controller.fire({
                    type: 'widget-value-changed',
                    widget: ref
                });
            };
        };
        
        widget.getUIElement = function () {
            // gets the whole widget (label + control)
	        var uiElem = $("<div />").addClass("widget");
	        uiElem.append(this.getLabel());
	        uiElem.append(this.getControl());
	        return uiElem;
        };
        
        return widget;
    };
    
    that.normalWidget = function(mugType, path) {
        // for "normal" = non-itext widgets.
        var widget = that.baseWidget(mugType);
        widget.path = path;
        widget.definition = mugType.getPropertyDefinition(path);
        widget.currentValue = mugType.getPropertyValue(path);
        widget.groupName = that.getGroupName(widget.path);
        widget.propName = that.getPropertyName(widget.path);
        
        widget.getID = function () {
            return this.path.split("/").join("-");
        };
        
        
        widget.save = function () {
            formdesigner.controller.setMugPropertyValue(this.mug.mug,
	                                                    this.groupName,
                                                        this.propName,
                                                        this.getValue(),
                                                        this.mug);
        };
        return widget;
        
    };
    
    that.textWidget = function (mugType, path) {
        // a text widget 
        var widget = that.normalWidget(mugType, path);
        
	    var input = $("<input />").attr("id", widget.getID()).attr("type", "text");
            
	    widget.getControl = function () {
            return input;
        };
        
        widget.setValue = function (value) {
            input.val(value);
        };
        
        widget.getValue = function() {
            return input.val();
        };
        
        input.keyup(widget.fireValueChanged());
        return widget;    
    };
    
    that.iTextIDWidget = function (mugType, path) {
        // a special text widget that holds itext ids
        var widget = that.textWidget(mugType, path);
        
        widget.isSelectItem = formdesigner.util.isSelectItem(widget.mug);
        widget.parentMug = widget.isSelectItem ? formdesigner.controller.form.controlTree.getParentMugType(widget.mug) : null;
        
        // a few little hacks to support auto-update of select items
        widget.getRootId = function () {
            if (this.isSelectItem) {
                return this.parentMug.getDefaultItextRoot() + "-";
            }
            return "";
        };
        
        widget.getNodeId = function () {
            if (!this.isSelectItem) {
                return this.mug.getDefaultItextRoot();
            } else {
                var val = this.mug.mug.properties.controlElement.properties.defaultValue; 
                return val ? val : "null";
            }
        };
        
        widget.autoGenerateId = function (nodeId) {
            return this.getRootId() + nodeId + "-" + widget.propName.replace("ItextID", "");
        };
        
        widget.setUIValue = function (val) {
            this.getControl().val(val);
        };
        
        widget.updateAutoId = function () {
            widget.setUIValue(widget.autoGenerateId(widget.getNodeId()));
        };
        
        widget.getItextItem = function () {
            return this.itextItem;
        };
        
        widget.setValue = function (value) {
            this.itextItem = value;
            this.setUIValue(value.id);
        };
        
        widget.getValue = function() {
            return this.getControl().val();
        };
        
        
        // auto checkbox
        var autoBoxId = widget.getID() + "-auto-itext";
        var autoBox = $("<input />").attr("type", "checkbox").attr("id", autoBoxId);
        var autoBoxLabel = $("<label />").text("auto?").attr("for", autoBoxId); 
        
        autoBox.change(function () {
            var auto = $(this).prop("checked");
            widget.setAutoMode(auto);
            if (auto) {
                widget.updateAutoId();
                widget.fireValueChanged()();
            }
        });
        
        widget.setAutoMode = function (autoMode) {
            this.autoMode = autoMode;
            if (autoMode) {
                //this.getControl().addClass("auto-itext");
            } else {
                //this.getControl().removeClass("auto-itext");
            }
        };
        
        // support auto mode to keep ids in sync
        if (widget.currentValue.id === widget.autoGenerateId(widget.getNodeId())) {
            widget.setAutoMode(true);
            autoBox.prop("checked", true);
        }
        
        widget.getUIElement = function () {
            // gets the whole widget (label + control)
            var uiElem = $("<div />").addClass("widget");
            uiElem.append(this.getLabel());
            uiElem.append(this.getControl());
            var autoDiv = $("<div />").addClass("auto-itext");
            autoDiv.append(autoBoxLabel);
            autoDiv.append(autoBox);
            uiElem.append(autoDiv);
            return uiElem;
        };
        
        
        widget.save = function () {
            // override save to call out to rename itext
            var oldItext = this.mug.getPropertyValue(this.path);
            var val = this.getValue();
            if (oldItext.id !== val) {
                oldItext.id = val;
                formdesigner.controller.setMugPropertyValue(this.mug.mug,
	                                                        this.groupName,
	                                                        this.propName,
	                                                        oldItext,
	                                                        this.mug);
            } 
        };
        
        widget.mug.mug.on('property-changed', function (e) {
            // keep the ids in sync if we're in auto mode
            if (widget.autoMode && 
                (e.property === "nodeID" || 
                 (widget.isSelectItem && e.property === "defaultValue"))) {
                var newVal = widget.autoGenerateId(e.val);
                if (newVal !== widget.getValue()) {
                    widget.setUIValue(newVal);
                    widget.fireValueChanged()();
                }
            } 
        });
        
        widget.getControl().keyup(function () {
            // turn off auto-mode if the id is ever manually overridden
            var newVal = $(this).val();
            if (newVal !== widget.autoGenerateId(widget.getNodeId())) {
                autoBox.prop("checked", false);
                widget.setAutoMode(false);
                
            }
        }); 
        return widget;
    };
    
    that.checkboxWidget = function (mugType, path) {
                
        var widget = that.normalWidget(mugType, path);
        
        var input = $("<input />").attr("id", widget.getID());
        input.attr("type", "checkbox");
        
        widget.getControl = function () {
	        return input;
        };
        
        widget.getUIElement = function () {
            // override this because the label comes after the control
            var uiElem = $("<div />").addClass("widget");
            uiElem.append(this.getControl());
            uiElem.append(this.getLabel());
            return uiElem;
        };
        
        widget.setValue = function (value) {
            input.prop("checked", value);
        };
        
        widget.getValue = function() {
            return input.prop("checked");
        };
        
        input.change(widget.fireValueChanged());
        return widget;    
    };
    
    that.xPathWidget = function (mugType, path) {
                
        var widget = that.textWidget(mugType, path);
        var xPathButton = $('<button />').addClass("xpath-edit-button").text("Edit").button().addClass('btn');
        xPathButton.data("group", widget.groupName).data("prop", widget.propName).data("inputControlID", widget.getID());
        xPathButton.click(function () {
            formdesigner.controller.displayXPathEditor({
                group:     $(this).data("group"),
                property:  $(this).data("prop"),
                xpathType: widget.definition.xpathType,
                value:     $("#" + $(this).data("inputControlID")).val()
            });
        });
        
        widget.getUIElement = function () {
            // gets the whole widget (label + control)
            var uiElem = $("<div />").addClass("widget");
            uiElem.append(this.getLabel());
            uiElem.append(this.getControl());
            uiElem.append(xPathButton);
            return uiElem;
        };
        
        return widget;
    };
    
    that.baseItextWidget = function (mugType, language, itemFunc, slug, form) {
        var widget = that.baseWidget(mugType);
        widget.language = language;
        widget.form = form;
        widget.slug = slug;
        
        widget.getTextItem = function () {
            return itemFunc(this.mug);
        };
        
        widget.getID = function () {
            return "itext-" + this.language + "-" + this.slug + "-" + this.form;
        };
        
        widget.getType = function () {
            if (this.form === "default") {
                return "Display Text";
            }
            return this.form;
        };
        
        widget.setValue = function (value) {
            input.val(value);
        };
        
        widget.getValue = function() {
            return input.val();
        };
        
        widget.fireChangeEvents = function () {
            item = this.getTextItem();
            if (item) {
	            // fire the property changed event(s)
	            formdesigner.controller.fire({ 
	               type: "question-itext-changed",
	               language: this.language,
	               item: item,
	               form: this.form,
	               value: this.getValue()
	            });
	            formdesigner.controller.form.fire({ 
	               type: "form-property-changed"
	            });
	        }
        };
        widget.save = function () {
            // override save to reference the itext, rather than
            // a property of the mug
            item = this.getTextItem();
            if (item) {
	            item.getForm(this.form).setValue(this.language, this.getValue());
	            this.fireChangeEvents();
	        }
        };
        
        // this is special
        widget.deleteValue = function () {
            item = this.getTextItem();
            if (item) {
                item.removeForm(this.form);
            }
        };
        
        var input = $("<input />").attr("id", widget.getID()).attr("type", "text");
        
        widget.getControl = function () {
            return input;
        };
        
        input.keyup(widget.fireValueChanged());
        return widget;
    };
    
    that.iTextWidget = function(mugType, language, itemFunc, slug, form) {
        
        var widget = that.baseItextWidget(mugType, language, itemFunc, slug, form);
        
        // a bit of a hack, only allow deletion for non-default forms
        if (form !== "default") {
            // override getUIElement to include the delete button
            widget.getUIElement = function () {
	            // gets the whole widget (label + control)
	            var uiElem = $("<div />").addClass("widget").attr("data-form", form);
	            uiElem.append(this.getLabel());
	            uiElem.append(this.getControl());
	            var deleteButton = $('<button />').addClass("xpath-edit-button").addClass('btn').addClass('btn-danger').text("Delete").button();
	            deleteButton.click(function () {
	                widget.deleteValue();
	                // this is a bit ridiculous but finds the right things to remove
	                uiElem.parent().parent().children(".itext-language-section")
                        .children('div[data-form="' + form + '"]').each(function () {
                        $(this).remove();    
	                });
	                widget.fireChangeEvents();
	            });
	            uiElem.append(deleteButton);
                return uiElem;
	        };
            
        }
        
        widget.getDisplayName = function () {
            return this.getType();
        };
        return widget;
    };
    
    that.iTextInlineWidget = function (mugType, language, itemFunc, slug, form, displayName) {
        
        var widget = that.baseItextWidget(mugType, language, itemFunc, slug, form);
        
        widget.getDisplayName = function () {
            var formSpecifier = (this.form === "default") ? "" : " - " + this.form;
            return displayName + formSpecifier + " (" + language + ")";
        };
        
        return widget;
    };
    
    that.selectWidget = function (mugType, path) {
        // a select widget 
        var widget = that.normalWidget(mugType, path);
        
        var input = $("<select />").attr("id", widget.getID()).addClass("chzn-select");
        input.append($('<option value="blank" />'));
        for (var i in widget.definition.values) {
            if (widget.definition.values.hasOwnProperty(i)) {
                var strVal = formdesigner.util.fromCamelToRegularCase(widget.definition.values[i].replace('xsd:','')),
                    isSelected = '';
        
                option = $("<option />").val(widget.definition.values[i]).text(strVal).appendTo(input);
                if (widget.currentValue === widget.definition.values[i]) {
                    // TODO: is this necessary?
                    option.attr("selected", "selected");
                }
            }
        }
    
        widget.getControl = function () {
        	return input;
        };
        
        widget.setValue = function (value) {
            input.val(value);
        };
        
        widget.getValue = function() {
            return input.val();
        };
        
        input.change(widget.fireValueChanged());
        
        return widget;    
    };
    
    that.questionTypeSelectorWidget = function (mugType) {
        var widget = that.baseWidget(mugType);
        widget.definition = {};
        widget.currentValue = mugType.typeSlug;
        widget.propName = "Question Type";
        
        widget.getID = function () {
            return "question-type";
        };
        
        var input = formdesigner.ui.getQuestionTypeSelector();
        // small hack: don't show data nodes or select items for now
        for (var i = 0; i < that.unchangeableQuestionTypes.length; i++) {
            input.find("#" + that.unchangeableQuestionTypes[i]).remove();
        }
        
        // crazy temporary css hack
        var label = widget.getLabel().css("float", "left").css("line-height", "40px");
        widget.getLabel = function () {
            
            return label;
        };
        
        widget.getControl = function () {
            return input;
        };
        
        widget.setValue = function (value) {
            input.val(value);
        };
        
        widget.getValue = function() {
            return input.val();
        };
        
        input.change(function () {
            try {
                formdesigner.controller.changeQuestionType(mugType, widget.getValue());
            } catch (err) {
                alert("Sorry, you can't do that because: " + err);
                input.val(mugType.typeSlug);
            }
        });
        
        return widget;
        
    };
    
    that.widgetTypeFromPropertyDefinition = function (propertyDef) {
        switch (propertyDef.uiType) {
            case "select":
                return that.selectWidget;
            case "checkbox":
                return that.checkboxWidget;
            case "xpath":
                return that.xPathWidget;
            case "itext-id":
                return that.iTextIDWidget;
            default:
                return that.textWidget;
        }                        
    };

    that.widgetFromMugAndDefinition = function (mugType, definition) {
        // there is probably one layer of indirection too many here
        switch (definition.widgetType) {
            case "itext":
                if (definition.displayMode === "inline") {
                    return that.iTextFieldBlockInline(mugType, definition);
                } else {
                    // default to "full"   
                    return that.iTextFieldBlock(mugType, definition);
                }
            case "questionType":
                return that.questionTypeSelectorWidget(mugType);
            case "generic":
            default: 
                var cls = that.widgetTypeFromPropertyDefinition(mugType.getPropertyDefinition(definition.path));
                return cls(mugType, definition.path);
        }
    };
    
    that.baseSection = function (mugType, options) {
        // functional inheritance
        var section = {};
        section.mugType = mugType;
        section.slug = options.slug || "anon";
        section.displayName = options.displayName;
        section.elements = options.elements;
        
        section.getHeader = function () {
            return $('<h2 />').text(this.displayName);
        };
        
        section.getId = function () {
            return "fd-question-edit-" + this.slug;
        }
        return section;
    };
    
    that.genericSection = function (mugType, options) {
        var section = that.baseSection(mugType, options);   
                
        section.getWidgets = function () {
                    
            var inner = this;
            var toWidget = function (elementdefinition) {
                var w = that.widgetFromMugAndDefinition(inner.mugType, elementdefinition);
                return w;
            }
            return this.elements.map(toWidget);
            
        }
        section.getSectionDisplay = function () {
            // returns the actual display for the section
            
            var header = this.getHeader();
            var sec = $("<fieldset />").attr("id", this.getId()).addClass("question-section");
            this.getWidgets().map(function (elemWidget) {
                elemWidget.setValue(elemWidget.currentValue);
                elemWidget.getUIElement().appendTo(sec);
            });
            return header.add(sec);
        };
        return section;
    };
    
    
    that.accordionSection = function (mugType, options) {
        var section = that.baseSection(mugType, options);   
        
        section.getHeader = function () {
            return $('<h3><a href="#">' + this.displayName + '</a></h3>');
        };
        
        section.getWidgets = function () {
            // TODO: don't copy paste this -- break into subsections?
            var inner = this;
            var toWidget = function (elementdef) {
                return that.widgetFromMugAndDefinition(inner.mugType, elementdef);
            }
            return this.elements.map(toWidget);
        }
        
        section.getSectionDisplay = function () {
            // returns the actual display for the section
            var sec = $("<fieldset />").attr("id", this.getId()).addClass("question-section");
            this.getHeader().appendTo(sec);
            var inner = $('<div />').appendTo(sec);
            this.getWidgets().map(function (elemWidget) {
                elemWidget.setValue(elemWidget.currentValue);
                elemWidget.getUIElement().appendTo(inner);
            });
            sec.accordion({
                autoHeight: false,
                collapsible: true,
                active: options.active !== undefined ? options.active : false
            });
            
            return sec;
        };
        return section;
    };
    
    that.baseITextFieldBlock = function (mugType, options) {
        var block = {};
        block.mugType = mugType;
        block.textIdFunc = options.textIdFunc;
        block.slug = options.slug;
        
        block.getTextId = function () {
            return this.textIdFunc(this.mugType);                           
        }
        
        block.showAddFormButton = options.showAddFormButton;
        block.formList = block.getTextId().getFormNames();
        block.displayName = options.displayName || "";
        
        block.langs = formdesigner.model.Itext.getLanguages();
        
        // hack, so they adhere to the same api
        block.setValue = function (val) {
            // noop
        };
        
        block.getValue = function () {
            // noop
        };
        
        return block;
    };
    
    that.iTextFieldBlock = function (mugType, options) {
        var block = that.baseITextFieldBlock(mugType, options);
        var main = $("");
        // needed for closure
        var textIdFunc = block.textIdFunc; 
        var slug = block.slug;
        
        var getDefaultValue = function (formType) {
            if (formType === "image" || formType === "audio" || formType === "video") {
                // default formats
                // image: jr://file/commcare/image/form_id/question_id.png
                // audio: jr://file/commcare/audio/form_id/question_id.mp3
                var extension = (formType === "image") ? "png" : 
                    (formType == "audio") ? "mp3" : "3gp";
                var ret = "jr://file/commcare/" + formType + "/" + 
                       formdesigner.controller.form.formID + "/" + 
                       mugType.getDefaultItextRoot() + "." + extension;
                return ret;
            } 
            return null;
        };
        var addItextType = block.addItextType = function (form, value) {
            main.parent().find(".itext-language-section").each(function () {
                var lang = $(this).data("language");
                var itextWidget = that.iTextWidget(mugType, lang, textIdFunc, slug, form);
                itextWidget.getUIElement().appendTo($(this));
                var itextForm = itextWidget.getTextItem().getOrCreateForm(form);
                if (value) {
                    itextForm.setValue(lang, value);
                    itextWidget.setValue(value);
                }
                itextWidget.fireChangeEvents();
            });
        };
        
        var itextItem = block.getTextId();
        
        block.getUIElement = function () {
            
            var itextWidget, subBlock, subSec;
            
            for (var i = 0; i < this.langs.length; i++) {
                subSec = $("<div />").addClass("itext-language-section").data("language", this.langs[i]);
                main = main.add(subSec);
                // sub heading for language
                $("<h3 />").text(this.langs[i]).appendTo(subSec);
                
                // loop through items, add to UI
                for (var j = 0; j < this.formList.length; j++) {
                    // add widget
                    itextWidget = that.iTextWidget(mugType, this.langs[i], this.textIdFunc, 
                                                   this.slug, this.formList[j]);
                    itextWidget.setValue(itextItem.getValue(this.formList[j], this.langs[i]));
                    itextWidget.getUIElement().appendTo(subSec);
                }
            }
            
            if (this.showAddFormButton) {
	            var defaultContentTypes = ["image", "audio", "video", "long", "short"];
	            var iWrapper = $("<div />").addClass("itext-wrapper");
	            main = main.add(iWrapper);
	            $("<span />").text("Add: ").addClass("help-inline").appendTo(iWrapper);
                var bg = $("<div />").addClass("btn-group itext-options").appendTo(iWrapper);
                for (i = 0; i < defaultContentTypes.length; i++) {
		            $("<div />").text(defaultContentTypes[i]).button().addClass('btn itext-option').click(
		                function () {
		                    var form = $(this).text();
		                    addItextType(form, getDefaultValue(form));
		                }).appendTo(bg);
		        }
                var addButton = $("<div />").text("custom...").button().addClass('btn').appendTo(bg);
	            addButton.click(function () {
	                var dialog = $("#fd-dialog-confirm");
	                dialog.dialog( "destroy" );
	                dialog.empty();
	                $("<label />").attr("for", "new-itext-id").text("Content type: ").appendTo(dialog);
	                var input = $("<input />").addClass("fd-property-input").attr("id", "new-itext-id").appendTo(dialog);
	                dialog.dialog({
	                    title: "New Content Item Type",
	                    buttons: {
	                        "Add": function () {
	                            addItextType(input.val());
	                            $(this).dialog("close");
	                        },
	                        "Cancel": function () {
	                            $(this).dialog("close");
	                        }
	                    }
	               });
	            });
	        }
	        return main;
        };
        
        return block;
    };
    
    that.iTextFieldBlockInline = function (mugType, options) {
        // an inline way of displaying itext blocks.
        // doesn't support adding fields
        // show's each langauge in the label
        
        var block = that.baseITextFieldBlock(mugType, options);
        var main = $("");
        
        var itextItem = block.getTextId();
        
        block.getUIElement = function () {
            var itextWidget, subBlock, subSec;
            
            for (var i = 0; i < this.langs.length; i++) {
                
                // loop through items, add to UI
                for (var j = 0; j < this.formList.length; j++) {
                    // add widget
                    itextWidget = that.iTextInlineWidget(mugType, this.langs[i], this.textIdFunc, 
                                                         this.slug, this.formList[j], this.displayName);
                    itextWidget.setValue(itextItem.getValue(this.formList[j], this.langs[i]));
                    main = main.add(itextWidget.getUIElement());
                }
            }
            
            return main;
        };
        
        return block;
    };
    
    /**
     * Hard coded function to map mugs to the types of things
     * that they display
     * 
     */
    that.getSectionListForMug = function (mugType) {
        
        sections = [];
        sections.push(that.getMainSection(mugType));
        if (mugType.hasControlElement()) {
            sections.push(that.getContentSection(mugType));
        }
        if (mugType.hasBindElement()) {
            sections.push(that.getLogicSection(mugType));
        }
        sections.push(that.getAdvancedSection(mugType));
        return sections;    
    };
    
    var wrapAsGeneric = function (elemPath) {
        // utility method for ease of editing paths
        return {widgetType: "generic", path: elemPath };
    };
    
    var filterByMugProperties = function (list, mugType) {
        var ret = [];
        var path, propertyDef;
        
        for (var i = 0; i < list.length; i++) {
            path = list[i];
            try {
                propertyDef = mugType.getPropertyDefinition(path);
                if (propertyDef.presence !== "notallowed") {
                    ret.push(path);
                }
            } catch (err) {
                // assume we couldn't get the property definition
                // therefore we should ignore it.
            }
        }
        return ret;
    };
    that.getMainSection = function (mugType) {
        var elements = ["dataElement/nodeID"];
        
        if (formdesigner.util.isSelectItem(mugType)) {
            elements.push("controlElement/defaultValue");
        }
        
        elements = filterByMugProperties(elements, mugType).map(wrapAsGeneric);
        
        if (that.unchangeableQuestionTypes.indexOf(mugType.typeSlug) === -1) {
            elements.splice(1, 0, {widgetType: "questionType", path: "system/questionType"});
        }
        return that.genericSection(mugType, { 
                            slug: "main",
                            displayName: "Main Properties",
                            elements: elements});
                                       
    };
    
    that.getContentSection = function (mugType) {
        elements = [{ widgetType: "itext",
                      slug: "text",
                      displayMode: "full",
                      textIdFunc: function (mt) { return mt.getItext() },
                      showAddFormButton: true}];
        return that.genericSection(mugType, { 
            displayName: "Content",
            slug: "content",
            elements: elements
        });
    };
    
    that.getLogicSection = function (mugType) {
        var elementPaths = filterByMugProperties(
            ["bindElement/requiredAttr",
             "bindElement/relevantAttr", "bindElement/calculateAttr", 
             "bindElement/constraintAttr",
             "bindElement/constraintMsgItextID"], mugType)
        var elements = elementPaths.map(wrapAsGeneric);
        if (elementPaths.indexOf("bindElement/constraintMsgItextID") !== -1) {
            // only add the itext if the constraint was relevant
	        elements.push({ widgetType: "itext",
	                        displayMode: "inline",
	                        slug: "constraint",
	                        displayName: "Constraint Message",
	                        textIdFunc: function (mt) { return mt.getConstraintMsgItext() }, 
	                        showAddFormButton: false});
        }
        return that.accordionSection(mugType, {
                            slug: "logic",
                            displayName: "Logic Properties",
                            elements: elements,
                            active: 0});
    };
    
    that.getAdvancedSection = function (mugType) {
        var elementPaths = filterByMugProperties(
            ["dataElement/dataValue", "dataElement/keyAttr", "dataElement/xmlnsAttr", 
             "bindElement/preload", "bindElement/preloadParams", 
             "controlElement/label", "controlElement/hintLabel", 
             "bindElement/constraintMsgAttr", "controlElement/labelItextID", 
             "controlElement/hintItextID", "controlElement/repeat_count", "controlElement/no_add_remove"], mugType);
        var elements = elementPaths.map(wrapAsGeneric);
        
        if (elementPaths.indexOf("controlElement/hintItextID") !== -1) {
	        // only add the itext if the hint was relevant
	        elements.push({ widgetType: "itext",
	                        displayMode: "inline",
	                        slug: "hint",
	                        displayName: "Hint",
	                        textIdFunc: function (mt) { return mt.getHintItext() }, 
	                        showAddFormButton: false});
        }
        return that.accordionSection(mugType, { 
                            slug: "advanced",
                            type: "accordion",
                            displayName: "Advanced Properties",
                            elements: elements});
    };
    
    return that;
}());

