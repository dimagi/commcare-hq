if (typeof formdesigner === 'undefined') {
    var formdesigner = {};
}

formdesigner.controller = (function () {
    "use strict";
    var that = {},
        curSelMugType = null,
        DEBUG_MODE = false,
        FORM_SAVED = true,
        saveButton = SaveButton.init({
            save: function() {
                that.sendXForm();
            },
            unsavedMessage: 'Are you sure you want to exit? All unsaved changes will be lost!'
        });
    that.saveButton = saveButton;
    
    var initFormDesigner = function () {
        xpathmodels.DEBUG_MODE = DEBUG_MODE;
        formdesigner.util.question_counter = 1;
        
        that.curSelUfid = null;
        // ui.questionTree.empty();
        // ui.dataTree.empty();
        $('#fd-data-tree').empty();

        formdesigner.model.init();
        formdesigner.ui.init();
        that.setCurrentlySelectedMugType(null);
        
        if (formdesigner.opts.langs && formdesigner.opts.langs.length > 0) {
            // override the languages with whatever is passed in
            for (var i = 0; i < formdesigner.opts.langs.length; i++) {
                formdesigner.model.Itext.addLanguage(formdesigner.opts.langs[i]);
            }
            formdesigner.model.Itext.setDefaultLanguage(formdesigner.opts.langs[0]);
        } else if (formdesigner.model.Itext.languages.length === 0) {
            formdesigner.model.Itext.addLanguage("en");
        }
        
        formdesigner.currentItextDisplayLanguage = formdesigner.opts["displayLanguage"] ||
                                                   formdesigner.model.Itext.getDefaultLanguage();
        
        that.on('question-creation', function () {
           that.setFormChanged(); //mark the form as 'changed'
        });

        that.on('question-removed', function () {
            that.setFormChanged();
        });
        
        that.on('question-itext-changed', function () {
            that.setFormChanged();
        });

        that.on('parse-start', function () {
            that.resetParseErrorMsgs();
            that.resetParseWarningMsgs();
        });
        
        that.on('parse-finish', function () {
            // wire the event handlers for all the mugs in the tree
            var allMugs = that.getMugTypeList(true);
            allMugs.map(function (mt) {
                formdesigner.util.setStandardMugEventResponses(mt.mug);
            });

            var i;
            // update parse error and warn information in the model/UI
            if (that.parseErrorMsgs) {
                for (i = 0; i < that.parseErrorMsgs.length; i++) {
                    formdesigner.controller.form.updateError(formdesigner.model.FormError({
                        level: "error",
                        message: that.parseErrorMsgs[i]
                    }));
                }
            }

            if (that.parseWarningMsgs) {
                for (i = 0; i < that.parseWarningMsgs.length; i++) {
                    formdesigner.controller.form.updateError(formdesigner.model.FormError({
                        level: "parse-warning",
                        message: that.parseWarningMsgs[i]
                    }));
                }
            }
            formdesigner.ui.resetMessages(formdesigner.controller.form.errors);
            
            
            // populate the LogicManager with initial path data
            allMugs.map(function (mug) {
                if (mug.hasBindElement()) {
	                for (var i = 0; i < formdesigner.util.XPATH_REFERENCES.length; i++) {
	                    formdesigner.model.LogicManager.addReferences(mug, formdesigner.util.XPATH_REFERENCES[i]);
	                }
                }
            });
        });
        
        that.on('widget-value-changed', function (e) {
            // When a widget's value changes, do whatever work you need to in 
            // the model/UI to make sure we are in a consistent state.
            
            var widget = e.widget;
            var val = widget.getValue();
            if (widget.propName === 'nodeID' && val.indexOf(" ") != -1){ 
                // attempt to sanitize nodeID
                // TODO, still may allow some bad values
                widget.setValue(val.replace(/\s/g,'_'));
            }
            
            //short circuit the mug property changing process for when the
            //nodeID is changed to empty-string (i.e. when the user backspaces
            //the whole value).  This allows us to keep a reference to everything
            //and rename smoothly to the new value the user will ultimately enter.
            if (val === "" && (widget.propName === 'nodeID')) {
                return;
            }
            
            widget.save();
        });
        
        that.on('parse-error', function (e) {
            if(DEBUG_MODE) {
                console.log('There was a parse error:', e);
            }
        });

    };
    that.initFormDesigner = initFormDesigner;

    that.setFormChanged = function () {
        saveButton.fire('change');
    };

    that.isFormSaved = function () {
        return saveButton.state === "saved";
    };
    
    var setForm = that.setForm = function (aForm) {
        that.form = aForm;
        formdesigner.util.setStandardFormEventResponses(that.form);
    };

    var getMTFromFormByUFID = function (ufid) {
        var curMT = that.form.dataTree.getMugTypeFromUFID(ufid);
        if (!curMT) { //check controlTree in case it's there.
            curMT = that.form.controlTree.getMugTypeFromUFID(ufid);
        }
        return curMT;
    };
    that.getMTFromFormByUFID = getMTFromFormByUFID;

    /**
     * Walks through both internal trees (data and control) and grabs
     * the Itext id's from any Mugs that are found.  Returns
     * a flat list of iIDs.  This list is primarily used
     * for trimming out crufty itext.  See also
     * formdesigner.model.Itext.removeCruftyItext()
     */
    var getAllNonEmptyItextItemsFromMugs = function () {
        
        // get all the itext references in the forms
        var ret = [];
        var appendItemsIfPresent = function (node) {
            if (node.isRootNode) {
                return;
            }

            var mt = node.getValue();
            if(!mt) {
                throw 'Node in tree without value?!?!'
            }
            
            var thingsToGet = ['controlElement/labelItextID', 'controlElement/hintItextID', 
                               'bindElement/constraintMsgItextID'] ; 
        
            var val;            
            for (var i = 0; i < thingsToGet.length; i++) {
	            try {
	                val = mt.getPropertyValue(thingsToGet[i]);
	                if (val && !val.isEmpty() && ret.indexOf(val) === -1) {
	                   // it was there and not present so add it to the list
	                   ret.push(val);
	                } 
	            } catch (err) {
	                // probably just wasn't in the mug
	            }
            }    
        };
        
        that.form.controlTree.treeMap(appendItemsIfPresent);
        that.form.dataTree.treeMap(appendItemsIfPresent);
        return ret; 

    };
    that.getAllNonEmptyItextItemsFromMugs = getAllNonEmptyItextItemsFromMugs;

    /**
     * Returns a MugType NOT a Mug!
     * @param path - String of path you want
     * @param tree - [OPTIONAL] Type of tree, 'control' or 'data'.  Defaults to 'data'
     */
    var getMugTypeByPath = function (path, tree) {
        var recFunc, tokens, targetMT, rootNode;
        if (!tree) {
            tree = 'data';
        }

        if(!path) { //no path specified
            return null;
        }


        recFunc = function (node, recTokens) {
            var currentToken, rest, children, i;
            if (recTokens.length === 0) {
                return node.getValue(); //found the target. It is this node.
            }
            currentToken = recTokens[0];
            rest = recTokens.slice(1);
            children = node.getChildren();

            for (i in children) {
                if(children.hasOwnProperty(i)) {
                    if (children[i].getID() === currentToken) {
                        return recFunc(children[i], rest);
                    }
                }
            }

            //if we got here that means 'path not found'
            return null;

        };

        tokens = path.split('/').slice(1);
        if (tokens.length === 0) {
            return null; //empty path string === 'path not found'
        }

        if (tree === 'data') {
            rootNode = that.form.dataTree.getRootNode();

        } else if (tree === 'control') {
            rootNode = that.form.controlTree.getRootNode();
        }

        if(rootNode.getID() !== tokens[0]) {
            return null; //path not found
        }

        targetMT = recFunc(rootNode,tokens.slice(1));
        return targetMT;
    };
    that.getMugByPath = getMugTypeByPath;
    
    var getSingularMugTypeByNodeId = function (nodeId, treeType) {
        if (!treeType) {
            treeType = 'data';
        }

        if(!nodeId) { //no path specified
            return null;
        }
        
        var nodeMatches = function (node) {
            var mt = node.getValue();
            return (mt && mt.mug && mt.mug.getBindElementID() === nodeId) ? mt : null;
        };
        
        var tree = (treeType === "data") ? that.form.dataTree : that.form.controlTree;
        var matchList = tree.treeMap(nodeMatches).filter(function (m) { return m !== null; });
        if (matchList.length !== 1) {
            throw "Expected one result for node " + nodeId + " but found " + matchList.length;
        }
        return matchList[0];
    };
    that.getSingularMugTypeByNodeId = getSingularMugTypeByNodeId;
    
    var getChildren = function (mug) {
        var children = that.form.controlTree.getNodeFromMugType(mug).getChildren();
        return children.map(function (item) { return item.getValue();});
    };
    that.getChildren = getChildren;
    
    /**
     * Walks through both internal trees (data and control) and grabs
     * all mugTypes that are not (1)Select Items.  Returns
     * a flat list of unique mugTypes.  This list is primarily fo the
     * autocomplete skip logic wizard.
     */
    var getMugTypeList = function (includeSelectItems) {
        var cTree, dTree, treeFunc, cList, dList, mergeList;
        //use formdesigner.util.mergeArray

        treeFunc = function (node) {
            var mt;
            if(node.isRootNode) {
                return;
            }

            mt = node.getValue();
            if(!mt) {
                throw 'Node in tree without value?!?!'
            }

            if(mt.typeSlug === "item" && !includeSelectItems) { //skip Select Items
                return;
            }

            return mt;
        };

        cTree = that.form.controlTree;
        dTree = that.form.dataTree;

        cList = cTree.treeMap(treeFunc);
        dList = dTree.treeMap(treeFunc);

        mergeList = formdesigner.util.mergeArray(cList, dList); //strip dupes and merge

        return mergeList; //give it all back

    };
    
    that.getMugTypeList = getMugTypeList;


    /**
     * Sets the currently selected (in the UI tree) MugType
     * so that the controller is aware of the currently
     * being worked on MT without having to do the call
     * to the UI each time.
     *
     * @param ufid - UFID of the selected MugType
     */
    var setCurrentlySelectedMugType = function (ufid) {
        that.curSelUfid = ufid;
        curSelMugType = getMTFromFormByUFID(ufid);
    };
    that.setCurrentlySelectedMugType = setCurrentlySelectedMugType;

    /**
     * @param myMug - the mug thats value needs to be set
     * @param element can be one of (string) 'bind','data','control'
     * @param property (string) property name
     * @param val new value the property should be set to.
     */
    that.setMugPropertyValue = function (myMug, element, property, val, mugType) {
        var prev = myMug.properties[element].properties[property];
        myMug.properties[element].properties[property] = val;
        myMug.fire({
			type: 'property-changed',
			property: property,
			element: element,
			val: val,
			previous: prev,
			mugUfid: myMug.ufid,
			mugTypeUfid: mugType.ufid
        });
    };

    /**
     * Function for triggering a clean out of the itext
     * where all ids + itext data are removed that are
     * found to not be linked to any element in the form.
     *
     * Toggles the ui spinner (this operation could take a few seconds).
     */
    var removeCruftyItext = function () {
        var validIds = that.getAllNonEmptyItextItemsFromMugs();
        formdesigner.model.Itext.resetItextList(validIds);
    };
    that.removeCruftyItext = removeCruftyItext;

    /**
     * Inserts a new MugType into the relevant Trees (and their
     * relevant positions) according to the specified mugType and
     * the currently selected mugType.
     * @param newMugType - new MT to be inserted into the Form object
     * @param refMugType - used to determine the relative position of the insertion (relative to the refMT)
     */
    var insertMugTypeIntoForm = function (refMugType, newMugType) {
        var dataTree = that.form.dataTree, controlTree = that.form.controlTree;

        if (newMugType.properties.dataElement) {
            if (newMugType.properties.controlElement) {
                dataTree.insertMugType(newMugType, formdesigner.util.getRelativeInsertPosition(refMugType, newMugType), refMugType);
            } else { 
                // this is a data node. for now default to sticking these
                // at the end of the form
                dataTree.insertMugType(newMugType, 'after', null);
            }
        }
        if (newMugType.properties.controlElement) {
            controlTree.insertMugType(newMugType, formdesigner.util.getRelativeInsertPosition(refMugType, newMugType), refMugType);
        }
    };
    that.insertMugTypeIntoForm = insertMugTypeIntoForm;

    var initController = function () {

    };
    that.initController = initController;

    /**
     * Controller internal function.  Goes through
     * the internal data model and reloads the UI trees
     * and whatever other widgets need refreshing in order
     * for the user to start the editing process.
     */
    function reloadUI () {
        var tree, treeFunc, loaderFunc, dataNodeList, i;
        //first clear out the existing UI
        formdesigner.ui.resetUI();
        that.setCurrentlySelectedMugType(null);

        treeFunc = function (node) {
            var mt;
            if(node.isRootNode) {
                return;
            }

            mt = node.getValue();
            if(!mt) {
                throw 'Node in tree without value?!?!'
            }

            loaderFunc(mt);


        };
        loaderFunc = that.loadMugTypeIntoUI;
        tree = that.form.controlTree;
        tree.treeMap(treeFunc);
        //get list of pure data nodes and throw them in the Question UI tree (at the bottom)
        dataNodeList = that.getDataNodeList();
        for (i in dataNodeList) {
            if (dataNodeList.hasOwnProperty(i)) {
                that.loadMugTypeIntoUI(dataNodeList[i]);
            }
        }
        formdesigner.ui.setAllTreeValidationIcons();
        that.fire('fd-reload-ui');
    }
    that.reloadUI = reloadUI;

    /**
     * Goes through and grabs all of the data nodes (i.e. nodes that are only data nodes (possibly with a bind) without any
     * kind of control.  Returns a flat list of these nodes (list items are mugTypes).
     */
    that.getDataNodeList = function () {
        var treeFunc = function(node){ //the function we will pass to treeMap
            if(!node.getValue() || node.isRootNode){
                return null;
            }
            var MT = node.getValue();

            if(MT.properties.controlElement){
                return null;
            }else{
                return MT;
            }
        };

        return  that.form.dataTree.treeMap(treeFunc);
    };

    var showErrorMessage = function (msg) {
//        formdesigner.ui.appendErrorMessage(msg);
        
    };
    that.showErrorMessage = showErrorMessage;

    function createQuestionInUITree(mugType) {
        function treeSetItemType(mugType) {
            var tString = mugType.mug.properties.controlElement ? mugType.mug.properties.controlElement.properties.name.toLowerCase() : 'data',
                setType = function (tType) {
                    var controlTree = $('#fd-question-tree'),
                        mugTUfid = mugType.ufid,
                        node = $('#'+mugTUfid);
                    controlTree.jstree("set_type",tType,node);
                };

            switch(tString.toLowerCase()) {
                case 'text':
                    setType("question");
                    break;
                case 'integer':
                    setType("int");
                    break;
                case 'double':
                    setType("double");
                    break;
                case 'long':
                    setType("long");
                    break;
                case 'group':
                    setType("group");
                    break;
                case 'repeat':
                    setType("repeat");
                    break;
                case 'multi-select':
                case 'single-select':
                    setType("selectQuestion");
                    break;
                case 'trigger':
                    setType("trigger");
                    break;
                case 'item':
                    setType("item");
                    break;
                case 'secret':
                    setType("secret");
                    break;
                case 'date':
                    setType("date");
                    break;
                case 'datetime':
                    setType("datetime");
                    break;
                case 'data':
                    setType('dataNode');
                    break;
                case 'barcode':
                    setType('barcode');
                    break;
                case 'geopoint':
                    setType('geopoint');
                    break;
                case 'image':
                    setType('image');
                    break;
                case 'audio':
                    setType('audio');
                    break;
                case 'video':
                    setType('video');
                    break;


            }
        }

        var mug = mugType.mug,
            controlTagName = mug.properties.controlElement ? mug.properties.controlElement.properties.tagName : null,
            isGroupOrRepeat = (controlTagName === 'group' || controlTagName === 'repeat'),
            objectData = {},
            insertPosition,
            oldSelected;

        oldSelected = that.getCurrentlySelectedMugType();
        if (isGroupOrRepeat) {
            objectData.state = 'open'; //should new node be open or closed?, omit for leaf
        }

        objectData.data = formdesigner.util.getMugDisplayName(mugType);
        objectData.metadata = {
                                'mugTypeUfid': mugType.ufid,
                                'mugUfid': mug.ufid,
                                'dataID':mug.getDataElementID(),
                                'bindID':mug.getBindElementID()
                                };
        objectData.attr = {
            "id" : mugType.ufid
        };
        if (mug.properties.controlElement) {
            insertPosition = formdesigner.util.getRelativeInsertPosition(that.getCurrentlySelectedMugType(),mugType);
        } else {
            formdesigner.ui.getQuestionJSTree().jstree("deselect_all");
            insertPosition = "last";
        }
        $('#fd-question-tree').jstree("create",
            null, //reference node, use null if using UI plugin for currently selected
            insertPosition, //position relative to reference node
            objectData,
            null, //callback after creation, better to wait for event
            true  //skip_rename
        );

        treeSetItemType(mugType);

        formdesigner.ui.getQuestionJSTree().jstree("select_node", $('#' + oldSelected));
    }

    function createQuestionInDataTree(mugType) {
        function treeSetItemType(mugType) {
            var mugTUfid = mugType.ufid,
                node = $('#' + mugTUfid + "_data");
            $('#fd-data-tree').jstree("set_type","default",node);
        }

        var mug = mugType.mug,
            objectData = {},
            insertPosition, curSelMugElData, curSelMugElQuestion, oldSelectedMugEl;

        if (!mugType.properties.dataElement) { //this mug doesn't have a data node so shouldn't be included.
            return;
        }

        objectData.state = 'open'; //should new node be open or closed?, omit for leaf
        objectData.data = formdesigner.util.getDataMugDisplayName(mugType);
        objectData.metadata = {
                                'mugTypeUfid': mugType.ufid,
                                'mugUfid': mug.ufid,
                                'dataID':mug.getDataElementID(),
                                'bindID':mug.getBindElementID()
                                };
        objectData.attr = {
            "id" : mugType.ufid + "_data"
        };

//        insertPosition = formdesigner.util.getRelativeInsertPosition(curSelMugType,mugType);
        insertPosition = "into"; //data nodes can always have children.

        if (that.getCurrentlySelectedMugType()) {
            curSelMugElData = $('#' + that.getCurrentlySelectedMugType().ufid + '_data'); //get corresponding Data Element
            oldSelectedMugEl = curSelMugElData;
            curSelMugElQuestion = ('#' + that.getCurrentlySelectedMugType().ufid); //remember what is selected in the question tree.
            if (curSelMugElData.length === 0) {
                var curParent = that.form.controlTree.getParentMugType();
                if(curParent) {
                    curSelMugElData = $('#' + curParent.ufid + '_data');
                } else { //parent is root of tree
                    curSelMugElData = null;
                }
            }

            if (curSelMugElData) {
                formdesigner.ui.getDataJSTree().jstree('select_node', curSelMugElData);
            } else {
                formdesigner.ui.getDataJSTree().jstree('deselect_all');
            }
        }else {
            //nothing selected
            curSelMugElData = null;
            formdesigner.ui.getDataJSTree().jstree('deselect_all');
        }

        $('#fd-data-tree').jstree("create",
            null, //reference node, use null if using UI plugin for currently selected
            insertPosition, //position relative to reference node
            objectData,
            null, //callback after creation, better to wait for event
            true  //skip_rename
        );

        treeSetItemType(mugType);

        //if we're in question view mode, select the node that was previously selected in the question tree.
        if(!formdesigner.ui.isInDataViewMode()) {
            formdesigner.ui.getDataJSTree().jstree('deselect_all');
            formdesigner.ui.getQuestionJSTree().jstree('select_node', curSelMugElQuestion);
        } else { //if not, select what was originally selected in the data tree
           formdesigner.ui.getQuestionJSTree().jstree('deselect_all');
            formdesigner.ui.getDataJSTree().jstree('select_node', oldSelectedMugEl);
        }
    }
    
    that.getMugTypeByQuestionType = function (qType) {
        switch(qType.toLowerCase()) {
            case 'text':
                return formdesigner.model.mugTypeMaker.stdTextQuestion();
            case 'group':
                return formdesigner.model.mugTypeMaker.stdGroup();
            case 'select':
                return formdesigner.model.mugTypeMaker.stdMSelect();
            case '1select':
                return formdesigner.model.mugTypeMaker.stdSelect();
            case 'secret':
                return formdesigner.model.mugTypeMaker.stdSecret();
             case 'item':
                return formdesigner.model.mugTypeMaker.stdItem();
            case 'trigger':
                return formdesigner.model.mugTypeMaker.stdTrigger();
            case 'repeat':
                return formdesigner.model.mugTypeMaker.stdRepeat();
            case 'int':
                return formdesigner.model.mugTypeMaker.stdInt();
            case 'long':
                return formdesigner.model.mugTypeMaker.stdLong();
            case 'double':
                return formdesigner.model.mugTypeMaker.stdDouble();
            case 'date':
                return formdesigner.model.mugTypeMaker.stdDate();
            case 'datetime':
                return formdesigner.model.mugTypeMaker.stdDateTime();
            case 'datanode':
                return formdesigner.model.mugTypeMaker.stdDataBindOnly();
            case 'geopoint':
                return formdesigner.model.mugTypeMaker.stdGeopoint();
            case 'barcode':
                return formdesigner.model.mugTypeMaker.stdBarcode();
            case 'image':
                return formdesigner.model.mugTypeMaker.stdImage();
            case 'audio':
                return formdesigner.model.mugTypeMaker.stdAudio();
            case 'video':
                return formdesigner.model.mugTypeMaker.stdVideo();
            default:
                console.log("No standard mugType for selected question type:" + qType + " switching to 'Text Question' type!");
                return formdesigner.model.mugTypeMaker.stdTextQuestion();
        }
    };

    /**
     * Convenience method for generating mug and mugType, calling UI and throwing
     * it the 'question' object
     *
     * @param qType = type of question to be created.
     */
    var createQuestion = function (qType) {
        var mugType, mug, createQuestionEvent = {};
        mugType = that.getMugTypeByQuestionType(qType);
        mug = mugType.mug;

        //this allows the mug to respond to certain events in a common way.
        //see method docs for further info
        formdesigner.util.setStandardMugEventResponses(mug);


        var oldSelected = that.getCurrentlySelectedMugType();
        var isDataNodeSelected = that.getCurrentlySelectedMugType() && !that.getCurrentlySelectedMugType().properties.controlElement;
        if (isDataNodeSelected) {
            //select the lowest not-data-node and continue
            var tmpSelector = formdesigner.ui.getQuestionJSTree().find('li[rel!="dataNode"]');
            if (tmpSelector.length > 0) {
                var newSelectEl = $(tmpSelector[tmpSelector.length - 1]);
                formdesigner.ui.getQuestionJSTree().jstree("select_node", newSelectEl, false);
            } else {
                formdesigner.ui.getQuestionJSTree().jstree("deselect_all");
                that.setCurrentlySelectedMugType(null);
                that.curSelUfid = null;
            }
        }
        insertMugTypeIntoForm(that.getCurrentlySelectedMugType(),mugType);
        // update the itext values
        formdesigner.model.Itext.updateForNewMug(mugType);
        
        createQuestionInUITree(mugType);
//        createQuestionInDataTree(mugType);
        
        
        // events
        createQuestionEvent.type = "question-creation";
        createQuestionEvent.mugType = mugType;
        this.fire(createQuestionEvent);


        //re-select what was originally selected at the start of this method (which gets changed when dealing with Data Nodes)
        if (isDataNodeSelected) {
            formdesigner.ui.getQuestionJSTree().jstree("deselect_all");
            formdesigner.ui.getQuestionJSTree().jstree("select_node", $('#' + oldSelected.ufid));
        }

        return mugType;

    };
    that.createQuestion = createQuestion;
    
    that.changeQuestionType = function (mugType, questionType) {
        if (questionType !== mugType.typeSlug) {
            // get the new mug type
            var newMugType = that.getMugTypeByQuestionType(questionType);
            
            // check preconditions - if this is a select question with
            // select items, you're only allowed to change it to another
            // select question
            var children = that.getChildren(mugType);
            if (children.length > 0) {
                if (!formdesigner.util.isSelect(newMugType)) {
                    throw "you can't change a select-style question to a non-select-style " +
                          "question if it has select items. Please remove all select items " +
                          "and try again."
                }
            }
            
            // copy everything over
            newMugType.ufid = mugType.ufid;
            var elems = ["dataElement", "bindElement", "controlElement"];
            for (var i = 0; i < elems.length; i ++) {
	            if (mugType.mug.properties[elems[i]] && newMugType.mug.properties[elems[i]]) {
	                formdesigner.util.copySafely(mugType.mug.properties[elems[i]].properties,
	                                             newMugType.mug.properties[elems[i]].properties,
	                                             ["nodeID"]);
	            }
            }
            // magic special cases
            if (formdesigner.util.isSelect(newMugType) || newMugType.typeSlug === "trigger") {
                newMugType.mug.properties.bindElement.properties.dataType = "";
            } 
            
            // update trees
            that.form.replaceMugType(mugType, newMugType, 'data');
            that.form.replaceMugType(mugType, newMugType, 'control');
            
            // update UI
            that.reloadUI();
            formdesigner.ui.selectMugTypeInUI(newMugType);
            formdesigner.controller.form.fire({ 
                type: "form-property-changed"
            }); 
        } 
    };
    var loadMugTypeIntoUI = function (mugType) {

        var mug, controlTree, parentMT, parentMTUfid, loadMTEvent = {};

        mug = mugType.mug;

        //set the 'currently selected mugType' to be that of this mugType's parent.
        controlTree = that.form.controlTree;
        parentMT = controlTree.getParentMugType(mugType);

        if(parentMT && mugType.properties.controlElement){ //check for control element because we want data nodes to be a flat list at bottom.
            parentMTUfid = parentMT.ufid;
            $('#fd-question-tree').jstree('select_node',$('#'+parentMTUfid), true);
        }else{
            parentMTUfid = null;
            $('#fd-question-tree').jstree('deselect_all');
        }
        createQuestionInUITree(mugType);

        loadMTEvent.type= "mugtype-loaded";
        loadMTEvent.mugType = mugType;
        formdesigner.controller.fire(loadMTEvent);

        return mug;
    };
    that.loadMugTypeIntoUI = loadMugTypeIntoUI;


    var loadMugTypeIntoDataUITree = function (mugType) {
        var mug, dataTree, parentMT, parentMTUfid, loadMTEvent = {};

        mug = mugType.mug;

        //this allows the mug to respond to certain events in a common way.
        //see method docs for further info
//        formdesigner.util.setStandardMugEventResponses(mug);

        //set the 'currently selected mugType' to be that of this mugType's parent.
        dataTree = formdesigner.controller.form.dataTree;
        parentMT = dataTree.getParentMugType(mugType);
        if(parentMT){
            parentMTUfid = parentMT.ufid;
            $('#fd-data-tree').jstree('select_node',$('#'+parentMTUfid + '_data'), true);
        }else{
            parentMTUfid = null;
            $('#fd-data-tree').jstree('deselect_all');
        }

        createQuestionInDataTree(mugType);
        loadMTEvent.type= "mugtype-loaded";
        loadMTEvent.mugType = mugType;
        that.fire(loadMTEvent);

        return mug;
    };
    that.loadMugTypeIntoDataUITree = loadMugTypeIntoDataUITree;

    that.XMLWriter = null;
    var initXMLWriter = function () {
        var xw = new XMLWriter( 'UTF-8', '1.0' );
        xw.writeStartDocument();
        that.XMLWriter = xw;
    };
    that.initXMLWriter = initXMLWriter;

    /**
     * Shows the source XML in a dialog window for editing, optionally
     * not displaying if there are validation errors and the user chooses
     * not to continue.
     */ 
     
    var showSourceXMLDialog = function () {
        function showFormInLightBox () {
            // callback to actually render the form
            
            var output = $('#fd-source'),
                controls = $("#fd-source-controls"),
                help = $("#fd-source-help");
            
            // clear controls
            controls.empty();
            help.text("This is the raw XML. You can edit or paste into this box to make changes " +
                      "to your form. Press 'Update Source' to save changes, or 'Close' to cancel.");
            
            
            // populate text
            if(!formdesigner.controller.formLoadingFailed){
                output.val(that.form.createXForm());
            } else {
                output.val(formdesigner.loadMe);
            }
            
            // add controls
            var loadButton = $('<button class="btn btn-primary" id ="fd-loadsource-button">Update Source</button>').appendTo(controls).button();
	        loadButton.click(function () {
	            that.loadXForm(output.val());
                formdesigner.controller.form.fire('form-property-changed');
	            $.fancybox.close();
	        });
	
	        var closeButton = $('<button class="btn" id ="fd-close-popup-button">Close</button>').appendTo(controls).button();
	        closeButton.click(function () {
	            $.fancybox.close();
	        });
	        
	        
            $('#inline').click();
        }

        // There are validation errors but user continues anyway
        function onContinue () {
            formdesigner.ui.hideConfirmDialog();
            showFormInLightBox();

        }

        function onAbort () {
            formdesigner.ui.hideConfirmDialog();
        }

        
        var msg = "There are validation errors in the form.  Do you want to continue anyway? WARNING:" +
            "The form will not be valid and likely not perform correctly on your device!";

        formdesigner.ui.setDialogInfo(msg,'Continue',onContinue,'Abort',onAbort);
        if (!that.form.isFormValid()) {
            formdesigner.ui.showConfirmDialog();
        } else {
            showFormInLightBox();
        }
    };
    that.showSourceXMLDialog = showSourceXMLDialog;


    var parseXLSItext = function (str) {
        var rows = str.split('\n'),
                i, j, cells, lang,iID, form, val, Itext;
        
        // TODO: should this be configurable? 
        var exportCols = ["default", "audio", "image" , "video"];
                
        Itext = formdesigner.model.Itext;
        for (i = 0; i < rows.length; i++) {
            cells = rows[i].split('\t');
            lang = cells[0];
            iID = cells[1];
            for (j = 2; j < cells.length && j < exportCols.length + 2; j++) {
                if (cells[j]) {
                    form = exportCols[j - 2];
                    val = cells[j];
                    Itext.getOrCreateItem(iID).getOrCreateForm(form).setValue(lang, val);
                }
            }
        }
        that.fire({type: "global-itext-changed"});
    };
    
    that.parseXLSItext = parseXLSItext;

    var generateItextXLS = function () {
        var idata, row, iID, lang, form, val, Itext,
                out = '';
        
        that.removeCruftyItext();
        Itext = formdesigner.model.Itext;
        
        /**
         * Cleans Itext so that it fits the csv spec. For now just replaces newlines with ''
         * @param val
         */
        
        function makeRow (language, item, forms) {
            var values = forms.map(function (form) {
                return item.hasForm(form) ? item.getForm(form).getValueOrDefault(language) : "";
            });
            var row = [language, item.id].concat(values);
            return formdesigner.util.tabSeparate(row);
        }
        
        var ret = [];
        // TODO: should this be configurable? 
        var exportCols = ["default", "audio", "image" , "video"];
        var languages = Itext.getLanguages();
        // deduplicate
        Itext.deduplicateIds();
        var allItems = Itext.getNonEmptyItems();
        var language, item, i, j;
        if (languages.length > 0) {
            for (i = 0; i < languages.length; i++) {
                language = languages[i];
                for (j = 0; j < allItems.length; j++) {
                    item = allItems[j];
                    ret.push(makeRow(language, item, exportCols));
                }       
            }
        }
        return ret.join("\n");
    };
    that.generateItextXLS = generateItextXLS;

    var generateExportXLS = function () {
        
        var languages = formdesigner.model.Itext.getLanguages();
        var i;
        // deduplicate
        formdesigner.model.Itext.deduplicateIds();
        
        var mugTypeToExportRow = function (mugType) {
            
            var defaultOrNothing = function (item, language, form) {
                return item.hasForm(form) ? item.getForm(form).getValueOrDefault(language) : "";
            }
            var fillBlanks = function (array, count) {
                for (var i = 0; i < count; i++) {
                    row.push("");
                }
            }
            
            var row = [];
            var i;
            // Question ID
            row.push(mugType.getDefaultItextRoot());
            if (mugType.hasControlElement()) {
                // Question Type   
                row.push(mugType.mug.properties.controlElement.properties.tagName);
                // IText ID
                var itext = mugType.getItext();
                row.push(itext.id);
                // [language texts]
                for (i = 0; i < languages.length; i++) {
                    row.push(defaultOrNothing(itext, languages[i], "default"));
                }
                // Audio File
                row.push(defaultOrNothing(itext, formdesigner.model.Itext.getDefaultLanguage(), "audio"));
                // Image File  
                row.push(defaultOrNothing(itext, formdesigner.model.Itext.getDefaultLanguage(), "image"));
            } else {
                fillBlanks(row, 3 + languages.lengths);
            }
            if (mugType.hasBindElement()) {
                // Skip Condition
                row.push(mugType.mug.properties.bindElement.properties.relevantAttr || "");
                // Constraint Condition                
                row.push(mugType.mug.properties.bindElement.properties.constraintAttr || "");
            } else {
                fillBlanks(row, 2);
            }
            return formdesigner.util.tabSeparate(row);
        };
        
        var headers = ["Question", "Type", "IText ID", "Audio", "Image", "Display Condition", "Validation Condition"];
        for (i = 0; i < languages.length; i++) {
            headers.splice(3 + i, 0, "Text (" + languages[i] + ")");
        } 
        var ret = that.getMugTypeList(true).map(mugTypeToExportRow);
        ret.splice(0, 0, formdesigner.util.tabSeparate(headers));
        return ret.join("\n");
    };
    that.generateExportXLS = generateExportXLS;

    var showItextDialog = function () {
    
        var input = $('#fd-source'),
            controls = $("#fd-source-controls"),
            help = $("#fd-source-help");
            
        // clear controls
        controls.empty();
        help.text("Copy these translations into a spreadsheet program like Excel. " + 
                  "You can edit them there and then paste them back here when you're " +
                  "done. These will update the translations used in your form. Press " + 
                  "'Update Translations' to save changes, or 'Close' to cancel.");
        
        // display current values
        input.val(that.generateItextXLS());
        
        // add controls
        var updateButton = $('<button class="btn btn-primary" id ="fd-parsexls-button">Update Translations</button>').appendTo(controls).button();
        updateButton.click(function () {
            that.parseXLSItext(input.val());
            formdesigner.controller.form.fire('form-property-changed');
            $.fancybox.close();
        });
        
        var closeButton = $('<button class="btn" id ="fd-close-popup-button">Close</button>').appendTo(controls).button();
        closeButton.click(function () {
            $.fancybox.close();
        });
        
        // this shows the popup
        $('#inline').click();
    };
    that.showItextDialog = showItextDialog;


    var showExportDialog = function () {
    
        var input = $('#fd-source'),
            controls = $("#fd-source-controls"),
            help = $("#fd-source-help");
            
        // clear controls
        controls.empty();
        help.text("Copy and paste this content into a spreadsheet program like Excel " +
                  "to easily share your form with others."); 
        
        // display current values
        input.val(that.generateExportXLS());
        
        // add controls
        var closeButton = $('<button class="btn" id ="fd-close-popup-button">Close</button>').appendTo(controls).button();
        closeButton.click(function () {
            $.fancybox.close();
        });
        
        // this shows the popup
        $('#inline').click();
    };
    that.showExportDialog = showExportDialog;

    var setFormName = function (name) {
        that.form.formName = name;
    };
    that.setFormName = setFormName;

    var loadXForm = function (formString) {
        $.fancybox.showActivity();

        //universal flag for indicating that there's something wrong enough with the form that vellum can't deal.
        formdesigner.controller.formLoadingFailed = false;

        //Things to do to gracefully deal with a form loading failure
        function formLoadFailed(e) {
            var showSourceButton = $('#fd-editsource-button');
            formdesigner.controller.formLoadingFailed = true;

            //populate formdesigner.loadMe (var used when loading a form given during initialization)
            //with the broken form, so that it can be viewed/edited by the showSource view
            formdesigner.loadMe = formString;

            //disable all buttons and inputs
            formdesigner.ui.disableUI();
            showSourceButton.button('enable'); //enable the view source button so the form can be tweaked by hand.
            
            // ok to hard code this because it's public
            var validator_url = "https://www.commcarehq.org/formtranslate/";
            
            var msg = "We're sorry, Vellum cannot load your form.  You can edit your form directly by clicking the " +
                      '"Edit Source XML" button or go back to download your form. <br>' +
                      "It is likely that your form contains errors.  You can check to see if " +
                      "your form is valid by pasting your entire form into the " +
                      '<a href="' + validator_url + '" target="_blank">Form Validator (link)</a>';
            
            formdesigner.model.form.updateError(formdesigner.model.FormError({
                key: "global-parse-fail",
                message: msg,
                level: "error"
            }), {updateUI: true});
        }

        formdesigner.on('load-form-error', formLoadFailed); 

        window.setTimeout(function () { //wait for the spinner to come up.
            formdesigner.fire({
                    type: 'load-form-start',
                    form : formString
            });

            try {
                that.resetFormDesigner();
                formdesigner.model.Itext.resetItext(); //Clear out any ideas about itext since we'll be loading in that information now.
                that.parseXML(formString);
                that.reloadUI();
            } catch (e) {
                formdesigner.fire({
                    type: 'load-form-error',
                    errorObj : e,
                    form : formString
                });
                console.log('E OBJ', e);
                // hack: don't display the whole invalid XML block if it
                // was a parse error
                var msg = e.toString();
                if (msg.indexOf("Invalid XML") === 0) {
                    msg = "Parsing Error. Please check that your form is valid XML.";
                }
                
                formdesigner.ui.setDialogInfo(msg, 
                    'ok', function() {
                        formdesigner.ui.hideConfirmDialog();
                    }, 
                    'cancel', function(){
                        formdesigner.ui.hideConfirmDialog();
                    });
                formdesigner.ui.showConfirmDialog();
            }

            formdesigner.fire({
                    type: 'load-form-complete',
                    form : formString
                });
            if(!formdesigner.controller.formLoadingFailed) {
                //re-enable all buttons and inputs in case they were disabled before.
                formdesigner.ui.enableUI();
            }
            $.fancybox.hideActivity();


        },
        500);

    };
    that.loadXForm = loadXForm;


    var removeMugTypeByUFID = function (ufid) {
        var MT = that.form.getMugTypeByUFID(ufid);
        that.removeMugTypeFromForm(MT);
    };
    that.removeMugTypeByUFID = removeMugTypeByUFID;

    var removeMugTypeFromForm = function (mugType) {
        var removeEvent = {}, Itext, children, i;
        Itext = formdesigner.model.Itext;
        formdesigner.ui.removeMugTypeFromUITree(mugType);

        var fromTree = formdesigner.controller.form.controlTree.getNodeFromMugType(mugType);
        if (fromTree) {
	        children = formdesigner.controller.form.controlTree.getNodeFromMugType(mugType).getChildrenMugTypes();
	        for (i in children) {
	            if(children.hasOwnProperty(i)) {
	                removeMugTypeFromForm(children[i]); //recursively remove MugTypes.
	            }
	        }
        }
        
        that.form.dataTree.removeMugType(mugType);
        that.form.controlTree.removeMugType(mugType);

        removeEvent.type = "question-removed";
        removeEvent.mugType = mugType;
        that.fire(removeEvent);
        formdesigner.ui.forceUpdateUI();
    };
    that.removeMugTypeFromForm = removeMugTypeFromForm;

    /**
    * use getErrorMsg() and addErrorMsg() to deal with error msgs!
    */
    that.parseErrorMsgs = [];
    that.parseWarningMsgs = [];

    var addParseErrorMsg = function (msg) {
        that.parseErrorMsgs.push(msg);
        that.fire({
              type: 'parse-error',
              exceptionData: msg
        });
    };
    that.addParseErrorMsg = addParseErrorMsg;

    var addParseWarningMsg = function (msg) {
        that.parseWarningMsgs.push(msg);
        that.fire({
              type: 'parse-warning',
              exceptionData: msg
        });
    };
    that.addParseWarningMsg = addParseWarningMsg;

    var getParseErrorMsgs = function () {
        return that.parseErrorMsgs;
    };
    that.getParseErrorMsgs = getParseErrorMsgs;

    var resetParseErrorMsgs = function () {
        that.parseErrorMsgs = [];
        formdesigner.model.form.clearErrors("error", {updateUI: true}); 
    };
    that.resetParseErrorMsgs = resetParseErrorMsgs;

    var resetParseWarningMsgs = function () {
        that.parseWarningMsgs = [];
        formdesigner.model.form.clearErrors("parse-warning", {updateUI: true}); 
    };
    that.resetParseWarningMsgs = resetParseWarningMsgs;

    /**
     * The big daddy function of parsing.
     * Pass in the XML String and this function
     * will create all the right stuff in the trees
     * and set everything up for editing.
     * @param xmlString
     */
    var parseXML = function (xmlString) {
        // for convenience
        var Itext = formdesigner.model.Itext;
        var pError = that.addParseErrorMsg;
        var ParseException = function (msg) {
            this.name = 'XMLParseException';
            this.message = msg;
        };

        // some helper functions used by the parser
        var lookForNamespaced = function (element, reference) {
            // due to the fact that FF and Webkit store namespaced
            // values slightly differently, we have to look in 
            // a couple different places.
            return element.attr("jr:" + reference) || element.attr("jr\\:" + reference);
        };
        
        /**
         * Get and itext reference from a value. Returns nothing if it can't
         * parse it as a valid itext reference.
         */
        var getITextReference = function (value) {
            try {
                var parsed = xpath.parse(value);
                if (parsed instanceof xpathmodels.XPathFuncExpr && parsed.id === "jr:itext") {
                    return parsed.args[0].value;
                } 
            } catch (err) {
                // this seems like a real error since the reference should presumably
                // have been valid xpath, but don't deal with it here
            }
            return false;
        };
        
        function parseDataTree (dataEl) {
            function parseDataElement (el) {
                var nodeID, nodeVal, mug, parentMugType, extraXMLNS, keyAttr,mType,parentNodeName,rootNodeName,dataTree;
                
                nodeID = el.nodeName;
                mType = formdesigner.util.getNewMugType(formdesigner.model.mugTypes.dataOnly);
                parentNodeName = $(el).parent()[0].nodeName;
                rootNodeName = $(dataEl)[0].nodeName;
                dataTree = that.form.dataTree;

                if($(el).children().length === 0) {
                    nodeVal = $(el).text();
                }else {
                    nodeVal = null;
                }

                extraXMLNS = $(el).attr('xmlns');
                keyAttr = $(el).attr('key');

                mType.typeName = "Data Node";
                mug = formdesigner.model.createMugFromMugType(mType);

                mug.properties.dataElement.properties.nodeID = nodeID;
                mug.properties.dataElement.properties.dataValue = nodeVal;
                if(extraXMLNS && (extraXMLNS !== formdesigner.formUuid)) {
                    mug.properties.dataElement.properties.xmlnsAttr = extraXMLNS;
                }
                if(keyAttr) {
                    mug.properties.dataElement.properties.keyAttr = keyAttr;
                }
                // add arbitrary attributes
                mug.properties.dataElement.properties._rawAttributes = formdesigner.util.getAttributes(el);
                
                mType.mug = mug;
                if ( parentNodeName === rootNodeName ) {
                    parentMugType = null;
                }else {
                    parentMugType = that.form.getMugTypeByIDFromTree(parentNodeName,'data')[0];
                }

                dataTree.insertMugType(mType,'into',parentMugType);
            }
            var root = $(dataEl), recFunc;

            recFunc = function () {
                    parseDataElement(this);
                    $(this).children().each(recFunc);

            };

            if(root.children().length === 0) {
                pError('Data block has no children elements! Please make sure your form is a valid JavaRosa XForm and try again!');
            }
            root.children().each(recFunc);
            //try to grab the JavaRosa XForm Attributes in the root data element...
            formdesigner.formUuid = root.attr("xmlns");
            formdesigner.formJRM = root.attr("xmlns:jrm");
            formdesigner.formUIVersion = root.attr("uiVersion");
            formdesigner.formVersion = root.attr("version");
            formdesigner.formName = root.attr("name");
            that.form.formID = $(root)[0].tagName;
            
            if (!formdesigner.formUuid) {
                that.addParseWarningMsg('Form does not have a unique xform XMLNS (in data block). Will be added automatically');
            }
            if (!formdesigner.formJRM) {
                that.addParseWarningMsg('Form JRM namespace attribute was not found in data block. One will be added automatically');
            }
            if (!formdesigner.formUIVersion) {
                that.addParseWarningMsg('Form does not have a UIVersion attribute, one will be generated automatically');
            }
            if (!formdesigner.formVersion) {
                that.addParseWarningMsg('Form does not have a Version attribute (in the data block), one will be added automatically');
            }
            if (!formdesigner.formName) {
                that.addParseWarningMsg('Form does not have a Name! The default form name will be used');
            }

        }

        function parseBindList (bindList) {



            /**
             * Takes in a path and converts it to an absolute path (if it isn't one already)
             * @param path - a relative or absolute nodeset path
             * @param rootNodeName - the name of the model root (used to create the absolute path)
             * @return absolute nodeset path.
             */
            function processPath (path, rootNodeName) {
                var newPath;
                var parsed = xpath.parse(path);
                if (!(parsed instanceof xpathmodels.XPathPathExpr)) {
                    return null;
                }

                if (parsed.initial_context == xpathmodels.XPathInitialContextEnum.RELATIVE) {
                    parsed.steps.splice(0, 0, xpathmodels.XPathStep({axis: "child", test: rootNodeName}));
                    parsed.initial_context = xpathmodels.XPathInitialContextEnum.ROOT;
                }
                newPath = parsed.toXPath();
                return newPath
            }

            formdesigner.processPath = processPath;

            function eachFunc () {
                var el = $(this),
                    attrs = {},
                    mType = formdesigner.util.getNewMugType(formdesigner.model.mugTypes.dataBind),
                    mug = formdesigner.model.createMugFromMugType(mType),
                    path, nodeID, bindElement, oldMT;
                path = el.attr('nodeset');
                if (!path) {
                   path = el.attr('ref');
                }
                nodeID = formdesigner.util.getNodeIDFromPath(path);
                if(el.attr('id')) {
                    attrs.nodeID = el.attr('id');
                    attrs.nodeset = path;
                } else {
                    attrs.nodeID = nodeID;
                }

                attrs.dataType = el.attr('type');
                if(attrs.dataType && attrs.dataType.toLowerCase() === 'xsd:integer') {  //normalize this dataType ('int' and 'integer' are both valid).
                    attrs.dataType = 'xsd:int';
                }
                attrs.relevantAttr = el.attr('relevant');
                attrs.calculateAttr = el.attr('calculate');
                attrs.constraintAttr = el.attr('constraint');

                var constraintMsg = lookForNamespaced(el, "constraintMsg");
                
                var constraintItext = getITextReference(constraintMsg);
                if (constraintItext) {
                    attrs.constraintMsgItextID = Itext.getOrCreateItem(constraintItext);
                } else {
                    attrs.constraintMsgItextID = Itext.createItem("");
                    attrs.constraintMsgAttr = constraintMsg;    
                }
                                
                // TODO: parse constraint itext
                attrs.requiredAttr = formdesigner.util.parseBoolAttributeValue(el.attr('required'));
                
                attrs.preload = lookForNamespaced(el, "preload");
                attrs.preloadParams = lookForNamespaced(el, "preloadParams");
                
                bindElement = new formdesigner.model.BindElement(attrs);
                mug.properties.bindElement = bindElement;

                path = processPath(path,that.form.dataTree.getRootNode().getID());
                oldMT = that.getMugByPath(path,'data');
                if(!oldMT && attrs.nodeset) {
                    oldMT = that.form.getMugTypeByIDFromTree(
                                                formdesigner.util.getNodeIDFromPath(attrs.nodeset),
                                                'data'
                    )[0];
                }
                if(!oldMT){
                    that.addParseWarningMsg("Bind Node [" + path + "] found but has no associated Data node. This bind node will be discarded!");
//                    throw 'Parse error! Could not find Data MugType associated with this bind!'; //can't have a bind without an associated dataElement.
                    return;
                }
                mType.ufid = oldMT.ufid;
                mType.properties.dataElement = oldMT.properties.dataElement;
                mType.mug = mug;
                mType.mug.properties.dataElement = oldMT.mug.properties.dataElement;
                // clear relevant itext for bind
                // this is ugly, and should be moved somewhere else
                if (oldMT.hasBindElement()) {
                    Itext.removeItem(oldMT.mug.properties.bindElement.properties.constraintMsgItextID);
                }
                that.form.replaceMugType(oldMT, mType, 'data');
            }
            bindList.each(eachFunc);
        }

        function parseControlTree (controlsTree) {
            function eachFunc(){
                /**
                 * Determines what MugType this element should be
                 * and creates it.  Also modifies any existing mug that is associated
                 * with this element to fit the new type.
                 * @param nodePath
                 * @param controlEl
                 */
                function classifyAndCreateMugType (nodePath, cEl) {

                    var oldMT = that.getMugByPath(nodePath, 'data'), //check the date node to see if there's a related MT already present
                        mugType, mug, tagName, bindEl, dataEl, dataType, MTIdentifier, mediaType,
                        //flags
                        hasBind = true;

                    tagName = $(cEl)[0].nodeName;
                    if (oldMT) {
                        bindEl = oldMT.mug.properties.bindElement;
                        if (bindEl) {
                            dataType = bindEl.properties.dataType;
                            mediaType = cEl.attr('mediatype') ? cEl.attr('mediatype') : null;
                            if (dataType) {
                                dataType = dataType.replace('xsd:',''); //strip out extranous namespace
                                dataType = dataType.toLowerCase();
                            }
                            if(mediaType) {
                                mediaType = mediaType.toLowerCase();
                            }
                        }else{
                            hasBind = false;
                        }
                    }

                    function MTIdentifierFromInput () {
                        // TODO: Add appearance attribute support here?
                        if (!dataType) { return 'stdTextQuestion'; }
                        var MTID = '';
                        if(dataType === 'long') {
                            MTID = 'stdLong';
                        }else if(dataType === 'int') {
                            MTID = 'stdInt';
                        }else if(dataType === 'double') {
                            MTID = 'stdDouble';
                        }else if(dataType === 'geopoint') {
                            MTID = 'stdGeopoint';
                        }else if(dataType === 'barcode') {
                            MTID = 'stdBarcode';
                        }else if(dataType === 'string') {
                            MTID = 'stdTextQuestion';
                        }else if(dataType === 'date') {
                            MTID = 'stdDate';
                        }else if(dataType === 'datetime') {
                            MTID = 'stdDateTime';
                        }else {
                            MTID = 'stdTextQuestion';
                        }
                        return MTID;
                    }

                    function MTIdentifierFromGroup () {
                        if($(cEl).children('repeat').length > 0){
                                tagName = 'repeat';
                                return 'stdRepeat';
                        } else {
                            return 'stdGroup';
                        }
                    }

                    function MTIdentifierFromUpload () {
                        if(!mediaType) {
                            throw 'Unable to parse binary question type. Path: ' +
                                    formdesigner.controller.form.dataTree.getAbsolutePath(oldMT) +
                                    'The question has no MediaType attribute assigned to it!'
                        }
                        if (mediaType === 'video/*') {
                            /* fix buggy eclipse syntax highlighter (because of above string) */ 
                            return 'stdVideo';
                        } else if (mediaType === 'image/*') {
                            /* fix buggy eclipse syntax highlighter (because of above string) */ 
                            return 'stdImage';
                        } else if (mediaType === 'audio/*') {
                            /* fix buggy eclipse syntax highlighter (because of above string) */ 
                            return 'stdAudio';
                        } else {
                            throw 'Unrecognized upload question type for Element: ' + nodePath + '!';
                        }
                    }
                    
                    //broadly categorize
                    tagName = tagName.toLowerCase();
                    if(tagName === 'select') {
                        MTIdentifier = 'stdMSelect';
                    }else if (tagName === 'select1') {
                        MTIdentifier = 'stdSelect';
                    }else if (tagName === 'trigger') {
                        MTIdentifier = 'stdTrigger';
                    }else if (tagName === 'input') {
                        MTIdentifier = MTIdentifierFromInput();
                    }else if (tagName === 'item') {
                        MTIdentifier = 'stdItem';
                    }else if (tagName === 'group') {
                        MTIdentifier = MTIdentifierFromGroup();
                    }else if (tagName === 'secret') {
                        MTIdentifier = 'stdSecret';
                    }else if (tagName === 'upload') {
                        MTIdentifier = MTIdentifierFromUpload();
                    }

                    try{
                        mugType = formdesigner.model.mugTypeMaker[MTIdentifier]();
                    }catch (e) {
                        console.log ("Exception Control Element", cEl);
                        throw 'New Control Element classified as non-existent MugType! Please create a rule for this case' +
                            ' in formdesigner.model.mugTypeMaker! IdentString:' + MTIdentifier + ",tagName:" + tagName +
                                ",cEl:" + cEl + ",nodePath:" + nodePath;
                    }

                    if(oldMT) { //copy oldMT data to newly generated MT
                        mugType.ufid = oldMT.ufid;
                        mugType.mug.properties.dataElement = oldMT.mug.properties.dataElement;
                        mugType.mug.properties.bindElement = oldMT.mug.properties.bindElement;

                        //replace in dataTree
                        that.form.replaceMugType(oldMT,mugType,'data');
                    }
                    
                    //check flags
                    if(!hasBind){
                        mugType.type = mugType.type.replace ('b',''); //strip 'b' from type string
                        delete mugType.properties.bindElement;
                        delete mugType.mug.properties.bindElement;
                    }

                    return mugType;
                }

                function populateMug (MugType, cEl) {
                    var labelEl, hintEl, Itext, repeat_count, repeat_noaddremove;
                    Itext = formdesigner.model.Itext;
                    function parseLabel (lEl, MT) {
                        var labelVal = formdesigner.util.getXLabelValue($(lEl)),
                            labelRef = $(lEl).attr('ref'),
                            cProps = MT.mug.properties.controlElement.properties,
                            asItext;
                        var labelItext;
                        cProps.label = labelVal;
                        
                        var newLabelItext = function (mugType) {
                            var item = formdesigner.model.ItextItem({
				                id: mugType.getDefaultLabelItextId()
				            });
				            Itext.addItem(item);
				            return item;
                        };
                        
                        if (labelRef){
                            //strip itext incantation
                            asItext = getITextReference(labelRef);
                            if (asItext) {
                                labelItext = Itext.getOrCreateItem(asItext);
                            } else {
                                // this is likely an error, though not sure what we should do here
                                // for now just populate with the default
                                labelItext = newLabelItext(MT);
                            }
                        } else {
                            labelItext = newLabelItext(MT);
                        }
                        
                        cProps.labelItextID = labelItext;
                        if (cProps.labelItextID.isEmpty()) {
                            //if no default Itext has been set, set it with the default label
                            if (labelVal) {
                                cProps.labelItextID.setDefaultValue(labelVal);
                            } else {
                                // or some sensible deafult
                                cProps.labelItextID.setDefaultValue(MT.getDefaultLabelValue());
                            }
                        }
                    }

                    function parseHint (hEl, MT) {
                        var hintVal = formdesigner.util.getXLabelValue($(hEl)),
                            hintRef = $(hEl).attr('ref'),
                            cProps = MT.mug.properties.controlElement.properties;

                        //strip itext incantation
                        var asItext = getITextReference(hintRef);
                        if (asItext) {
                            cProps.hintItextID = Itext.getOrCreateItem(asItext);
                        } else {
                            // couldn't parse the hint as itext.
                            // just create an empty placeholder for it
                            cProps.hintItextID = Itext.createItem(""); 
                        }
                        cProps.hintLabel = hintVal;
                    }

                    function parseDefaultValue (dEl, MT) {
                        var dVal = formdesigner.util.getXLabelValue($(dEl)),
                                cProps = MT.mug.properties.controlElement.properties;
                        if(dVal){
                            cProps.defaultValue = dVal;
                        }
                    }

                    function parseRepeatVals (r_count, r_noaddremove, MT) {
                        //MT.mug.properties.controlElement.properties
                        if (r_count) {
                            MT.mug.properties.controlElement.properties.repeat_count = r_count;
                        }

                        if(r_noaddremove) {
                            MT.mug.properties.controlElement.properties.no_add_remove = r_noaddremove;
                        }
                    }
                    var tag = MugType.mug.properties.controlElement.properties.tagName;
                    if(tag === 'repeat'){
                        labelEl = $($(cEl).parent().children('label'));
                        hintEl = $(cEl).parent().children('hint');
                        repeat_count = $(cEl).attr('jr:count');
                        repeat_noaddremove = formdesigner.util.parseBoolAttributeValue($(cEl).attr('jr:noAddRemove'));

                    } else {
                        labelEl = $(cEl).children('label');
                        hintEl = $(cEl).children('hint');
                    }

                    var cannottHaveDefaultValue = ['select', 'select1', 'repeat', 'group', 'trigger'];
                    if (labelEl.length > 0) {
                        parseLabel(labelEl, MugType);
                    }
                    if (hintEl.length > 0) {
                        parseHint (hintEl, MugType);
                    }
                    if (tag === 'item') {
                        parseDefaultValue($(cEl).children('value'),MugType);
                    }

                    if (tag === 'repeat') {
                        parseRepeatVals(repeat_count, repeat_noaddremove, MugType);
                    }
                    
                    // add any arbitrary attributes that were directly on the control
                    MugType.mug.properties.controlElement.properties._rawAttributes = formdesigner.util.getAttributes(cEl);
                }

                function insertMTInControlTree (MugType, parentMT) {
                    that.form.controlTree.insertMugType(MugType,'into',parentMT);
                }

                //figures out if this control DOM element is a repeat
                function isRepeatTest(groupEl) {
                    if($(groupEl)[0].tagName !== 'group') {
                        return false;
                    }
                    return $(groupEl).children('repeat').length === 1;
                }

                var el = $ ( this ), oldEl,
                    path,
                    nodeID,
                    mType,
                    parentNode,
                    parentMug,
                    tagName,
                    couldHaveChildren = ['repeat', 'group', 'select', 'select1'],
                    children,
                    bind,
                    isRepeat;

                isRepeat = isRepeatTest(el);
                //do the repeat switch thing
                if(isRepeat) {
                    oldEl = el;
                    el = $(el.children('repeat')[0]);
                }

                parentNode = oldEl ? oldEl.parent() : el.parent();
                if($(parentNode)[0].nodeName === 'h:body') {
                    parentNode = null;
                }

                var mugFromControlEl = function (el) {
	                var nodeId, bind;
	                var path = formdesigner.util.getPathFromControlElement(el);

	                if (path) {
	                    var nodeId = formdesigner.util.getNodeIDFromPath(path);
	                } else {
	                    // try looking for a control with a bind attribute
                        bind = $(el).attr('bind');
                        if (bind) {
                            nodeId = bind;
                        }
	                }
	                if (path) {
	                    return that.getMugByPath(path, 'data');
	                } else if (nodeId) {
	                    try {
	                        return that.getSingularMugTypeByNodeId(nodeId);
	                    } catch (err) {
	                        // may be fine if this was a parent lookup, 
	                        // or will fail hard later if this creates an illegal move
	                        return null;
	                    }
	                }
	                return null;
	            }
                
                if (parentNode) {
                    parentMug = mugFromControlEl(parentNode);
                }
                
                path = formdesigner.util.getPathFromControlElement(el);
                if (path) {
                    nodeID = formdesigner.util.getNodeIDFromPath(path);
                } else {
	                var existingMug = mugFromControlEl(el);
	                if (existingMug) {
	                    path = that.form.dataTree.getAbsolutePath(existingMug);
	                    nodeID = existingMug.mug.getBindElementID() || existingMug.mug.getDataElementID();
	                }
                }
                
                if (oldEl) {
                    mType = classifyAndCreateMugType(path,oldEl);
                } else {
                    mType = classifyAndCreateMugType(path,el);
                }
                populateMug(mType,el);
                insertMTInControlTree(mType, parentMug);

                tagName = mType.mug.properties.controlElement.properties.tagName.toLowerCase();
                if(couldHaveChildren.indexOf(tagName) !== -1) {
                    children = $(el).children().not('label').not('value').not('hint');
                    children.each(eachFunc); //recurse down the tree
                }
                
                // update any remaining itext
                Itext.updateForExistingMug(mType);
            }
            controlsTree.each(eachFunc);
        }

        function parseItextBlock (itextBlock) {
            function eachLang() {
                
                var el = $(this), defaultExternalLang;
                var lang = el.attr('lang');
                var argument_langs = formdesigner.opts["langs"];
                
                function eachText() {
                    var textEl = $ (this);
	                var id = textEl.attr('id');
	                var item = Itext.getOrCreateItem(id);
	                
	                function eachValue() {
                        var valEl = $(this);
                        var curForm = valEl.attr('form');
                        if(!curForm) {
                            curForm = "default";
                        }
                        item.getOrCreateForm(curForm).setValue(lang, formdesigner.util.getXLabelValue(valEl));
                    }
	                textEl.children().each(eachValue);
	            }


                //if we were passed a list of languages (in order of preference from outside)...
                if (argument_langs) {  //we make sure this is a valid list with things in it or null at init time.
                    for (var i = 0; i < argument_langs; i++) {
                        if (argument_langs.hasOwnProperty(i)) {
                            Itext.addLanguage(argument_langs[i]);
                        }
                    }
                    //grab the new 'default' language. (Opts languages listing takes precedence over form specified default)
                    defaultExternalLang = argument_langs[0];
                }


                if (argument_langs && argument_langs.indexOf(lang) === -1) { //this language does not exist in the list of langs provided in launch args
                    that.addParseWarningMsg("The Following Language will be deleted from the form as it is not listed as a language in CommCareHQ: <b>" + lang + "</b>");
                    return; //the data for this language will be dropped.
                }
                Itext.addLanguage(lang);
                if (el.attr('default') !== undefined) {
                    Itext.setDefaultLanguage(lang);
                }

                if (defaultExternalLang) {
                    Itext.setDefaultLanguage(defaultExternalLang); //set the form default to the one specified in initialization options.
                }

                //loop through children
                el.children().each(eachText)
            }
            
            Itext.clear();
            if (formdesigner.opts.langs && formdesigner.opts.langs.length > 0) {
	            // override the languages with whatever is passed in
	            for (var i = 0; i < formdesigner.opts.langs.length; i++) {
	                formdesigner.model.Itext.addLanguage(formdesigner.opts.langs[i]);
	            }
	            formdesigner.model.Itext.setDefaultLanguage(formdesigner.opts.langs[0]);
            }
            $(itextBlock).children().each(eachLang);
            if (Itext.getLanguages().length === 0) {
                // there likely wasn't itext in the form or config. At least
                // set a default language
                Itext.addLanguage("en");
                Itext.setDefaultLanguage("en");
            }
            if (!formdesigner.currentItextDisplayLanguage) {
                formdesigner.currentItextDisplayLanguage = formdesigner.model.Itext.getDefaultLanguage();
            }
        }

        that.fire('parse-start');
        try {
            var _getInstances = function (xml) {
                // return all the instances in the form.
                // if there's more than one, guarantee that the first item returned
                // is the main instance.
                var instances = xml.find("instance");
                var foundMain = false;
                var ret = [];
                for (var i = 0; i < instances.length; i++) {
                    // the main should be the one without an ID
                    if (!$(instances[i]).attr("id")) {
                        if (foundMain) {
                            throw "multiple unnamed instance elements found in the form! this is not allowed. please add id's to all but 1 instance.";
                        }
                        ret.splice(0, 0, instances[i]);
                        foundMain = true;
                    } else {
                        ret.push(instances[i]);
                    }
                }
                return ret;
            };
            var xmlDoc = $.parseXML(xmlString),
                xml = $(xmlDoc),
                binds = xml.find('bind'),
                instances = _getInstances(xml),
                controls = xml.find('h\\:body').children(),
                itext = xml.find('itext'),
                formID, formName, title;

            var data = $(instances[0]).children();
            if($(xml).find('parsererror').length > 0) {
                throw 'PARSE ERROR! Message follows:' + $(xml).find('parsererror').find('div').html();
            }
            
            // NOTE: this is a bit odd - but seems to assume there's only one 
            // child of the main instance, or that the last child should be 
            // used as the form id
            data.each(function () {
                formID = this.nodeName;
            });
            
            title = xml.find('title');
            if(title.length === 0) {
                title = xml.find('h\\:title');
            }

            if(title.length > 0) {
                title = $(title).text();
                that.form.formName = title;
            }
            
            // set all instance metadatas
            that.form.instanceMetadata = instances.map(function (instance) {
                return formdesigner.model.InstanceMetadata(formdesigner.util.getAttributes(instance)); 
            });
            
            if(data.length === 0) {
                pError('No Data block was found in the form.  Please check that your form is valid!');
            }
            
            // parse itext first so all the other functions can access it
            parseItextBlock(itext);
            
            parseDataTree (data[0]);
            parseBindList (binds);

            if(controls.length === 0) {
                controls = xml.find('body').children();
            }
            parseControlTree(controls);
            

            that.fire({
                type: 'parse-finish'
            });

        } catch (e) {
            that.fire({
              type: 'parse-error',
              exceptionData: e
            });
            throw e;
        }
        
    };
    that.parseXML = parseXML;

    /**
     * Checks that the specified move is legal. returns false if problem is found.
     *
     * THIS IS FOR NODES THAT HAVE A CONTROLELEMENT ONLY!
     * @param oType - The type of ControlElement being moved (use tagName!) e.g. "input" or "group"
     * @param position - position, can be "before', "after", "into"
     * @param rType - The type of the Reference controlElement being moved (use tagName!) e.g. "input" or "group"
     *                  if -1 is given, assumes rootNode.
     */
    var checkMoveOp = that.checkMoveOp =function (mugType, position, refMugType, treeType) {
        if(treeType === 'data'){
            return true;
        }
        
        // for now don't allow data nodes to move
        if (!mugType || !mugType.mug.properties.controlElement) {
            return false;
        }
        
        // NOTE: why is this here?
        if(position === 'inside'){
            position = 'into';
        }
        
        var oType = mugType.mug.properties.controlElement.properties.tagName,
            rType = (!refMugType || refMugType === -1) ? 'group' : refMugType.mug.properties.controlElement.properties.tagName,
            oIsGroupOrRepeat = (oType === 'repeat' || oType === 'group'),
            oIsItemOrInputOrTrigger = (oType === 'item' || oType === 'input' || oType === 'trigger' || oType === 'secret'),
            oIsSelect = (oType === 'select1' || oType === 'select'),
            oIsItem = (oType === 'item'),
            rIsSelect = (rType === 'select1' || rType === 'select'),
            rIsItemOrInputOrTrigger = (rType === 'item' || rType === 'input' || rType === 'trigger' || rType === 'secret'),
            rIsGroupOrRepeat = (rType === 'repeat' || rType === 'group');

        if (position !== 'into') {
            if (!refMugType) {
                return true;
            }
            var pRefMugType = that.form.controlTree.getParentMugType(refMugType);
            return checkMoveOp(mugType,'into',pRefMugType);
        }

        //from here it's safe to assume that position is always 'into'
        if (rIsItemOrInputOrTrigger) {
            return false;
        }

        if (rIsGroupOrRepeat) {
            return !oIsItem;
        }

        if (rIsSelect) {
            return oIsItem;
        }

        //we should never get here.
        console.error("checkMoveOp error..",mugType,position,refMugType,treeType);
        throw "Unknown controlElement type used, can't check if the MOVE_OP is valid or not!";
    };




    /**
     * Move a mugType from its current place (in both the Data and Control trees) to
     * the position specified by the arguments,
     * @param mugType - The MT to be moved
     * @param position - The position relative to the refMugType (can be 'before','after' or 'into')
     * @param refMugType
     * @param treeType - Optional - either 'data' or 'control' or 'both'. Indicates which tree to do the move op in.  defaults to 'both'
     */
    var moveMugType = function (mugType, position, refMugType, treeType) {
        var dataTree = that.form.dataTree, 
            controlTree = that.form.controlTree, 
            isDataTreeOp;
        
        treeType = treeType || 'both';
        
        if (!checkMoveOp(mugType, position, refMugType, treeType)) {
            throw 'MOVE NOT ALLOWED!  MugType Move for MT:' + mugType + ', refMT:' + refMugType + ", position:" + position + " ABORTED";
        }

        isDataTreeOp = refMugType && refMugType.typeName !== "Select Item";

        var preMovePath = formdesigner.controller.form.dataTree.getAbsolutePath(mugType);
        if (treeType === 'both') {
            if (isDataTreeOp) {
                dataTree.insertMugType(mugType, position, refMugType);
            }
            controlTree.insertMugType(mugType, position, refMugType);
        } else if (treeType === 'control') {
            controlTree.insertMugType(mugType, position, refMugType);
        } else if (treeType === 'data') {
            if (isDataTreeOp) {
                dataTree.insertMugType(mugType, position, refMugType);
            }
        } else {
           throw 'Invalid/Unrecognized TreeType specified in moveMugType: ' + treeType;
        }

        
        var postMovePath = formdesigner.controller.form.dataTree.getAbsolutePath(mugType);
        // update logic expressions that reference this
        if (preMovePath !== postMovePath) {
            formdesigner.model.LogicManager.updatePath(mugType.ufid, preMovePath, postMovePath);
            // update UI
            var currSelected = formdesigner.controller.getCurrentlySelectedMugType();
            that.reloadUI();
            formdesigner.ui.selectMugTypeInUI(currSelected);
        }
        
        //fire an form-property-changed event to sync up with the 'save to server' button disabled state
        formdesigner.controller.form.fire({
            type: 'form-property-changed'
        });


    };
    that.moveMugType = moveMugType;
    /**
     * Gets the label used to represent this mug in the UI tree
     * @param mugOrMugType - mug or mugType
     */
    var getTreeLabel = function (mugOrMugType) {
        var mug;
        if (mugOrMugType instanceof formdesigner.model.Mug) {
            mug = mugOrMugType;
        }else if (typeof mugOrMugType.validateMug === 'function') {
            mug = mugOrMugType.mug;
        }else{
            throw 'getTreeLabel() must be given either a Mug or MugType as argument!';
        }

        var retVal = mug.getBindElementID() ? mug.getDataElementID() : mug.getBindElementID();
        if (!retVal) {
            retVal = mug.properties.controlElement.properties.label;
        }
        return retVal;
    };
    that.getTreeLabel = getTreeLabel;


    /**
     * Returns the Tree Model object specified by treeType from the Form object
     * @param treeType - string - either 'data' or 'control'
     */
    var getTree = function getTree(treeType) {
        if (treeType === 'data') {
            return that.form.dataTree;
        }else if (treeType === 'control') {
            return that.form.controlTree;
        }else{
            throw "controller.getTree must be given a treeType of either 'data' or 'control'!";
        }
    };

    var getCurrentlySelectedMug = function () {
        var curMug = that.getCurrentlySelectedMugType();
        if (curMug) {
            return curMug.mug;
        } else {
            return null;
        }
    };
    that.getCurrentlySelectedMug = getCurrentlySelectedMug;

    var getCurrentlySelectedMugType = function () {
        if (!formdesigner.ui.getJSTreeCurrentlySelected().length) {
            curSelMugType = null;
        }
        return curSelMugType;
    };
    that.getCurrentlySelectedMugType = getCurrentlySelectedMugType;

    /**
     * Returns a JSON representation of the
     * Control Tree (tweak this method for data tree)
     * returns it as well as logging it to console.
     */
    that.get_form_data = function(){
        var trees = [], wTree, i,j, data;
        trees.push(getTree('data'));
        trees.push(getTree('control'));

        function printMug(mType){
            return mType.mug;
        }

        function recurse(node){
            var i,d = {}, children;
            d.parent = printMug(node.getValue());
            d.children = {};
            children = node.getChildren();
            for(i in children){
                if(children.hasOwnProperty(i)){
                    d.children[i] = (recurse(children[i]));
                }
            }

            return d;
        }

        data = JSON.stringify(recurse(trees[0].rootNode),null,'\t');

        return data;
    };


    var sendXForm = function (url) {
        if (!url) {
            url = formdesigner.saveUrl;
        }
        if (!url) {
            formdesigner.ui.setDialogInfo("Error: Cannot send form, no save url specified!",
            'OK', function () {
                        $ (this) .dialog("close");
                    },
            'Cancel', function () {
                        $ (this) .dialog("close");
            });
        }
        $('body').ajaxStart(formdesigner.ui.showWaitingDialog);
        $('body').ajaxStop(formdesigner.ui.hideConfirmDialog);

        formdesigner.XFORM_STRING = that.form.createXForm();
        saveButton.ajax({
            type: "POST",
            url: url,
            data: {xform: formdesigner.XFORM_STRING},
            success: function (data) {
                formdesigner.ui.hideConfirmDialog();
                formdesigner.fire({
                    type: 'form-saved',
                    response: data
                });
            }
        });
    };
    that.sendXForm = sendXForm;

    /**
     * Used to reset the state of the controller if a FD wide reset is called
     * (see resetFormDesigner)
     */
    function resetControllerInternal () {
            formdesigner.util.question_counter = 1;
            //reset Options passed in to the initializer
            that.setCurrentlySelectedMugType(null);
            that.curSelUfid = null;
    }

    /**
     * Used to clear out the state of the FormDesigner
     * to represent how things were just after the first
     * init call was made (used for example when wanting
     * to create a 'New Form'
     *
     * @param opts - pass a new set of launch options to be used for reset.
     */
    that.resetFormDesigner = function (opts) {
        resetControllerInternal();
        formdesigner.model.reset();
        formdesigner.ui.resetUI();
    };
    
    // tree drag and drop stuff, used by xpath
    var handleTreeDrop = function(source, target) {
        var target = $(target), sourceUid = $(source).attr("id");
        if (target) {
            var mug = that.form.getMugTypeByUFID(sourceUid);
            // the .change fires the validation controls
            target.val(target.val() + formdesigner.util.mugToXPathReference(mug)).change();
        }
    };
    that.handleTreeDrop = handleTreeDrop;
    
    // here is the xpath stuff
    var displayXPathEditor = function(options) {
        formdesigner.ui.hideQuestionProperties();
        formdesigner.ui.hideTools();
        formdesigner.ui.showXPathEditor(options);
    };
    that.displayXPathEditor = displayXPathEditor;
    
    var doneXPathEditor = function(options) {
        var mug = that.getCurrentlySelectedMugType();
        if (!options.cancel) {
            that.setMugPropertyValue(mug.mug, options.group, options.property, options.value, mug) 
        }
        formdesigner.ui.hideXPathEditor();
        formdesigner.ui.showTools();
        formdesigner.ui.displayMugProperties(mug);
    };
    that.doneXPathEditor = doneXPathEditor;
    
    
    //make controller event capable
    formdesigner.util.eventuality(that);



    return that;
})();