/**
 * Just some useful JS tools and idioms
 */

if(typeof Object.create !== 'function') {
    Object.create = function(obj) {
        var Blank_Function = function(){};
        Blank_Function.prototype = obj;
        return new Blank_Function();
    };
}


//Trim dogpunch
if(typeof(String.prototype.trim) === "undefined")
{
    String.prototype.trim = function()
    {
        return String(this).replace(/^\s+|\s+$/g, '');
    };
}

if(typeof formdesigner === 'undefined'){
    var formdesigner = {};
}

formdesigner.util = (function(){
    var that = {};

    //VERIFY_RETURN_CODES:
    var VERIFY_CODES = {
            VERIFY_SUCCESS : 0,
            VERIFY_FAIL : 1,
            VERIFY_NO_DEFINITION : 2,
            VERIFY_ERROR : 3
    };
    that.VERIFY_CODES = VERIFY_CODES;
    that.XPATH_REFERENCES = ["bindElement/relevantAttr",
                             "bindElement/calculateAttr",
                             "bindElement/constraintAttr"]; 
    
    var GROUP_OR_REPEAT_VALID_CHILDREN = that.GROUP_OR_REPEAT_VALID_CHILDREN = [
        "group",
        "repeat",
        "question",
        "date",
        "datetime",
        "int",
        "barcode",
        "geopoint",
        "long",
        "double",
        "selectQuestion",
        "trigger",
        "secret",
        "default",
        "image",
        "audio",
        "video"
    ];
    
    that.QUESTIONS = {
        //in the format: {question_slug: question_label}
        'text': 'Text Question',
        'secret': 'Password Question',
        'group': 'Group',
        'select': 'Multi-Select Question',
        'item': 'Select Item',
        '1select': 'Single Select',
        'trigger': 'Label',
        'repeat': 'Repeat',
        'barcode': 'Barcode Question',
        'geopoint': 'Geopoint Question',
        'int': 'Integer Number',
        'double': 'Decimal Number',
        'long': 'Long Number',
        'image': 'Image Question',
        'audio': 'Audio Question',
        'video': 'Video Question',
        'date': 'Date',
        'datetime': 'Date and Time',
        'datanode': 'Data Node'
    };
    
    that.getQuestionList = function () {
        var ret = [];
        for (var q in that.QUESTIONS) {
            if (that.QUESTIONS.hasOwnProperty(q)) {
                ret.push([q, that.QUESTIONS[q]]);
            }
        }
        return ret;
    }
    /**
     * Grabs the value between the tags of the element passed in
     * and returns a string of everything inside.
     *
     * This method is kindy of hacky, so buyer beware.
     *
     * Motivation: Jquery's selector can't do this.  We need to be able to
     * grab the value of label tags, even if it includes <output> tags inside
     * of it (since the tag may need to be displayed to the user).
     * @param el - jquery selector or string used in the selector pointing to a DOM element.
     */
    var xmls = new XMLSerializer();
    function getXLabelValue (el){
        var resStr, resEl;
        function getEndTag (str) {
            var res, reo, last;
            reo = /<\/(?:"[^"]*"['"]*|'[^']*'['"]*|[^'">])+>/g;
            res = reo.exec(str);
            last = res;
            while(res !== null) {
                last = res;
                res = reo.exec(str);
            }
            if(last){
                return last[0];
            }else{
                return null;
            }
            
        }

        function getStartTag (str) {
            var re, res;
            re = /<(?:"[^"]*"['"]*|'[^']*'['"]*|[^'">])+>/;
            res = re.exec(str);
            return res[0];
        }

        resEl = $(el)[0];
        if(!resEl) { return; }
        resStr = xmls.serializeToString(resEl);
        resStr = resStr.replace(getStartTag(resStr),'').replace(getEndTag(resStr),'');
        return resStr;
    }
    that.getXLabelValue = getXLabelValue;

    var dumpFormTreesToConsole = function () {
        var vObj = [], vOut = [], i, invalidMT = [], mt;
                console.group("Tree Pretty Print");
                console.log("Control Tree:"+formdesigner.controller.form.controlTree.printTree());
                console.log("Data Tree:   "+formdesigner.controller.form.dataTree.printTree());
                console.log("TREE VALIDATION RESULT",formdesigner.controller.form.controlTree.isTreeValid());
                invalidMT = formdesigner.controller.form.getInvalidMugTypes();

                console.log("TREE MAP INVALID UFIDS", formdesigner.controller.form.getInvalidMugTypeUFIDs());
                for (i in invalidMT){
                    if(invalidMT.hasOwnProperty(i)){
                        mt = invalidMT[i];
                        vOut.push(mt);
                        vOut.push(mt.validateMug());
                    }
                }
                console.log("INVALID MTs,VALIDATION OBJ",vOut);
                console.groupEnd();
    };
    that.dumpFormTreesToConsole = dumpFormTreesToConsole;
    
    /*
     * Copies all properties from one object to another under the following rules:
     *  - If the property doesn't exist on the destination object it is not copied
     *  - If the property exists but is different on the destination object it is not copied
     *
     * This is used to attempt to copy as much as possible from one mug to 
     * another while preserving the core structure.
     * 
     */
    that.copySafely = function (from, to, forceOverride) {
        if (!forceOverride) forceOverride = [];
        if (to) {
            for (var prop in from) {
                if (from.hasOwnProperty(prop)) {
                    if (forceOverride.indexOf(prop) !== -1 || 
                        (to.hasOwnProperty(prop) && !to[prop])) {
                        to[prop] = from[prop];
                    } 
                }
            }
        }
    };
    
    /**
     * From http://stackoverflow.com/questions/4149276/javascript-camelcase-to-regular-form
     * @param myString
     */
    function fromCamelToRegularCase(myString){
        var ret;
        // insert a space before all caps
        ret = myString.replace(/([A-Z])/g, ' $1')
        // uppercase the first character
                .replace(/^./, function(str){ return str.toUpperCase(); });

        return ret;
    }
    that.fromCamelToRegularCase = fromCamelToRegularCase;

    /**
     * Given two lists, creates a new array (and returns it)
     * that contains only unique values
     * based on comparing the two argument arrays.
     * @param arrA
     * @param arrB
     */
    var mergeArray = function (arrA, arrB) {
        var result = [], i;
        for(i in arrA){
            if(arrA.hasOwnProperty(i)){
                if(arrA.slice(0,arrA.indexOf(i)).indexOf(i) === -1){ //check to see if there aren't dupes in arrA
                    result.push(arrA[i]);
                }
            }
        }

        for(i in arrB){
            if(arrB.hasOwnProperty(i)){
                if(result.indexOf(arrB[i]) === -1){
                    result.push(arrB[i]); //grab only anything that hasn't shown up yet
                }
            }
        }

        return result;
    };
    that.mergeArray = mergeArray;

    /**
     * Given a (nodeset or ref) path, will figure out what the implied NodeID is.
     * @param path
     */
    function getNodeIDFromPath (path) {
        if (!path) {
            return null;
        }
        var arr = path.split('/');
        return arr[arr.length-1];
    }
    that.getNodeIDFromPath = getNodeIDFromPath;

    /**
     * Figures out what the xpath is of a controlElement
     * by looking at the ref or nodeset attributes.
     * @param el - a jquery selector or DOM node of an xforms controlElement.
     * @return - a string of the ref/nodeset value
     */
    function getPathFromControlElement (el) {
        if(!el){
            return null;
        }
        el = $(el); //make sure it's jquerified
        var path = el.attr('ref');
        if(!path){
            path = el.attr('nodeset');
        }
        return path || null;
    }
    that.getPathFromControlElement = getPathFromControlElement;


    //taken from http://stackoverflow.com/questions/728360/copying-an-object-in-javascript
    //clones a 'simple' object (see link for full description)
    function clone(obj) {
        var copy, i;
        // Handle the 3 simple types, and null or undefined
        if (null === obj || "object" !== typeof obj) return obj;

        // Handle Date
        if (obj instanceof Date) {
            copy = new Date();
            copy.setTime(obj.getTime());
            return copy;
        }

        // Handle Array
        if (obj instanceof Array) {
            var len;
            copy = [];
            for (i = 0, len = obj.length; i < len; ++i) {
                copy[i] = clone(obj[i]);
            }
            return copy;
        }

        // Handle Object
        if (obj instanceof Object) {
            copy = {};
            for (var attr in obj) {
                if (obj.hasOwnProperty(attr)) copy[attr] = clone(obj[attr]);
            }
            return copy;
        }

        throw new Error("Unable to copy obj! Its type isn't supported.");
    }
    that.clone = clone;

    that.question_counter = 1;
    /**
     * Private method for constructing unique questionIDs, labels for items, etc
     * @param prefixStr
     */
    var label_maker = function (prefixStr) {
        var ret = prefixStr + that.question_counter;
        that.question_counter += 1;
        return ret;
    };

    /**
     * Generates a unique question ID (unique in this form) and
     * returns it as a string.
     */
    that.generate_question_id = function () {
        return label_maker('question');
    };


    var generate_item_label = function () {
        return label_maker('item');
    };
    that.generate_item_label = generate_item_label;

    that.getAttributes = function (element) {
        var attributes = $(element)[0].attributes;
        var attrMap = {};
        for (var i = 0; i < attributes.length; i++) {
            attrMap[attributes[i].nodeName] = attributes[i].nodeValue;
        }
        return attrMap;
    }; 
    
    that.throwAndLogValidationError = function(vResult,mType,mug){
//            console.group("Failed Validation Objectss");
//            console.log("Validation Object:");
//            console.log(vResult);
//            console.log("MugType");
//            console.log(mType);
//            console.log("Mug");
//            console.log(mug);
//            console.groupEnd();
            throw 'Newly created mug did not validate! MugType and Mug logged to console...'
    }


    that.parseXml = function (xml) {
       var dom = null;
       if (window.DOMParser) {
          try {
             dom = (new DOMParser()).parseFromString(xml, "text/xml");
          }
          catch (e) { dom = null; }
       }
       else if (window.ActiveXObject) {
          try {
             dom = new ActiveXObject('Microsoft.XMLDOM');
             dom.async = false;
             if (!dom.loadXML(xml)) // parse error ..

                window.alert(dom.parseError.reason + dom.parseError.srcText);
          }
          catch (e) { dom = null; }
       }
       else
          alert("cannot parse xml string!");
       return dom;
    };
    /**
     * Takes in a reference mugType and makes a copy of
     * the object (the copy is returned).
     * @param refMug
     */
    var getNewMugType = function(refMugType){
        var newMugType = formdesigner.util.clone(refMugType);
        formdesigner.util.give_ufid(newMugType);
        return newMugType;
    };
    that.getNewMugType = getNewMugType;

    var DefinitionValidationException = function(message){
        this.message = message;
        this.name = "DefinitionValidationException";
    };
    that.DefinitionValidationException = DefinitionValidationException;

    var verify_mug = function(mug, definition){
        return VERIFY_CODES.VERIFY_ERROR; //not implemented yet!
    };
    that.verify_mug = verify_mug;

    //Simple Event Framework
    //Just run your object through this function to make it event aware
    //Taken from 'JavaScript: The Good Parts'
    var eventuality = function (that) {
        var registry = {};
        that.fire = function (event) {
    // Fire an event on an object. The event can be either
    // a string containing the name of the event or an
    // object containing a type property containing the
    // name of the event. Handlers registered by the 'on'
    // method that match the event name will be invoked.
            var array,
                func,
                handler,
                i,
                type = typeof event === 'string' ?
                        event : event.type;
    // If an array of handlers exist for this event, then
    // loop through it and execute the handlers in order.
            if (registry.hasOwnProperty(type)) {
                array = registry[type];
                for (i = 0; i < array.length; i += 1) {
                    handler = array[i];
    // A handler record contains a method and an optional
    // array of parameters. If the method is a name, look
    // up the function.
                    func = handler.method;
                    if (typeof func === 'string') {
                        func = this[func];
                    }
    // Invoke a handler. If the record contained
    // parameters, then pass them. Otherwise, pass the
    // event object.
                    func.apply(this,
                        handler.parameters || [event]);
                }
            }
            return this;
        };
        that.on = function (type, method, parameters) {
    // Register an event. Make a handler record. Put it
    // in a handler array, making one if it doesn't yet
    // exist for this type.
            var handler = {
                method: method,
                parameters: parameters
            };
            if (registry.hasOwnProperty(type)) {
                registry[type].push(handler);
            } else {
                registry[type] = [handler];
            }
            return this;
        };
        return that;
    };
    that.eventuality = eventuality;

    /**
     * Answers the question of whether
     * the refMugType can have children of type ofTypeMug.
     * @return list of strings indicating the allowed children types (if any).
     * can be any of 'group' 'repeat' 'select' 'item' 'question'
     */
    var canMugTypeHaveChildren = function(refMugType,ofTypeMug){
        var allowedChildren, n, targetMugTagName, refMugTagName,
                makeLower = function(s){
                    return s.toLowerCase();
                };

        if (!refMugType || !ofTypeMug || !refMugType.properties.controlElement) {
            throw 'Cannot pass null argument or MugType without a controlElement!';
        }
        if(!refMugType.controlNodeCanHaveChildren){ return false; }
        allowedChildren = refMugType.controlNodeAllowedChildren;
        allowedChildren = allowedChildren.map(makeLower);
        if (ofTypeMug.mug.properties.controlElement) {
            targetMugTagName = ofTypeMug.mug.properties.controlElement.properties.tagName.toLowerCase();
        } else if (ofTypeMug.typeName === "Data Node") {
            targetMugTagName = 'data';
        }
        refMugTagName = refMugType.mug.properties.controlElement.properties.tagName.toLowerCase();

        if(allowedChildren.indexOf(targetMugTagName) === -1 && targetMugTagName != 'data'){
            return false;
        }else{
            return true;
        }
    
    };
    that.canMugTypeHaveChildren = canMugTypeHaveChildren;

    var capitaliseFirstLetter = function (string) {
        return string.charAt(0).toUpperCase() + string.slice(1);
    };
    that.capitaliseFirstLetter = capitaliseFirstLetter;

    /**
     * Determines where the newMugType should be inserted relative
     * to the refMugType.
     * @param refMugType - the reference MT already in the tree
     * @param newMugType - the new MT you want a relative position for
     * @return - String: 'first', 'inside' or 'after'
     */
    var getRelativeInsertPosition = function(refMugType, newMugType){
            var canHaveChildren;
            if(!refMugType){
                return "into";
            }

            canHaveChildren = formdesigner.util.canMugTypeHaveChildren(refMugType,newMugType);

            if(canHaveChildren){
                return "into";
            }else{
                return "after";
            }
    };
    that.getRelativeInsertPosition = getRelativeInsertPosition;

    
    var generate_guid = function() {
        // http://stackoverflow.com/questions/105034/how-to-create-a-guid-uuid-in-javascript
        var S4 = function() {
            return (((1+Math.random())*0x10000)|0).toString(16).substring(1);
        };
        return (S4()+S4()+S4()+S4()+S4()+S4()+S4()+S4());
    };

    var CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz";
    var generate_xmlns_uuid = function () {
        var uuid = [], r, i;

		// rfc4122 requires these characters
		uuid[8] = uuid[13] = uuid[18] = uuid[23] = '-';
		uuid[14] = '4';

		// Fill in random data.  At i==19 set the high bits of clock sequence as
		// per rfc4122, sec. 4.1.5
		for (i = 0; i < 36; i++) {
			if (!uuid[i]) {
				r = Math.floor((Math.random()*16));
				uuid[i] = CHARS[(i == 19) ? (r & 0x3) | 0x8 : r & 0xf];
			}
		}
		return uuid.toString().replace(/,/g,'');
    }
    that.generate_xmlns_uuid = generate_xmlns_uuid;

    /**
     * This method gives the passed object
     * a Unique Mug ID plus standardized method(s)
     * for accessing the ID.
     * @param that
     */
    var give_ufid = function(that){
        that.ufid = generate_guid();
    };
    that.give_ufid = give_ufid;

    that.XSD_DATA_TYPES = [
            'xsd:boolean',
            'xsd:byte',
            'xsd:date',
            'xsd:dateTime',
            'xsd:decimal',
            'xsd:double',
            'xsd:float',
            'xsd:int',
            'xsd:long',
            'xsd:short',
            'xsd:string',
            'xsd:time',
            'geopoint',
            'barcode'
    ];

    that.VALID_CONTROL_TAG_NAMES = [
            'input',
            '1select',
            'select',
            'group',
            'repeat',
            'trigger',
            'item',
            'output',
            'secret'
    ];


    // TODO: what is this for?
    that.VALID_QUESTION_TYPE_NAMES = [
            'Text',
            'Group',
            'Repeat',
            'Trigger',
            'Single-Select',
            'Multi-Select',
            'Integer',
            'Decimal', // one of these shouldn't be here
            'Double',  // one of these shouldn't be here
            'Long',
            'Float',
            'Date',
            'DateTime',
            'Time',
            'Picture',
            'Audio',
            'GPS',
            'Barcode',
            'Secret',
            'Geopoint'
    ];

    /**
     * Shortcut func because I'm tired of typing this out all the time.
     * @param obj
     */
    var exists = function(obj){
        return typeof obj !== 'undefined';
    };
    that.exists = exists;

    var getLabelItextID = function (mug) {
        if(mug.properties.controlElement) {
            return mug.properties.controlElement.properties.labelItextID
        }
    }
    that.getLabelItextID = getLabelItextID;

    
    (function($) {
              // duck-punching to make attr() return a map
              var _old = $.fn.attr;
              $.fn.attr = function() {
                  var a, aLength, attributes,	map;
                  if (this[0] && arguments.length === 0) {
                            map = {};
                            attributes = this[0].attributes;
                            aLength = attributes.length;
                            for (a = 0; a < aLength; a++) {
                                      map[attributes[a].name] = attributes[a].value;
                            }
                            return map;
                  } else {
                            return _old.apply(this, arguments);
                  }
        }
    }(jQuery));


    /**
     * Bind a number of standard event responses to a mug
     * so that it responds in a pre-determined fashion to default things
     *
     * Add stuff here when you want most/all mugs to behave in a certain
     * fashion on FD events.
     * @param mug
     */
    that.setStandardMugEventResponses = function (mug) {
        //NOTE: 'this' is the mug responding to the event.

        //bind dataElement.nodeID and bindElement.nodeID together
        mug.on('property-changed',function (e) {
            if(e.property === 'nodeID'){
                if(this.properties.dataElement){
                    this.properties.dataElement.properties.nodeID = e.val;
                }
                if(this.properties.bindElement){
                    this.properties.bindElement.properties.nodeID = e.val;
                }
            }
        });

        //Update the status of the indicator icons indicating where validation has failed
        mug.on('property-changed', function (e) {
            var MT = formdesigner.controller.getMTFromFormByUFID(e.mugTypeUfid);
            formdesigner.ui.showVisualValidation(MT);
            formdesigner.ui.setTreeValidationIcon(MT);
        });

        
        // update the logic properties that reference the mug
        mug.on('property-changed', function (e) {
            if (e.previous !== e.val) {
	            var mug = formdesigner.controller.getMTFromFormByUFID(e.mugTypeUfid);
	            if (e.property === 'nodeID') {
	                var currentPath = formdesigner.controller.form.dataTree.getAbsolutePath(mug);
	                var parsed = xpath.parse(currentPath);
	                parsed.steps[parsed.steps.length - 1].name = e.previous;
	                formdesigner.model.LogicManager.updatePath(mug.ufid, parsed.toXPath(), currentPath);
	            } else {
                    var propertyPath = [e.element, e.property].join("/");
                    if (mug.getPropertyDefinition(propertyPath).uiType === "xpath") {
	                    formdesigner.model.LogicManager.updateReferences(mug, propertyPath);
	                }
	            }
	        }
        });


    }

    /**
     * Bind some standard responses to the 'form-property-changed' event.
     * @param form - formdesigner.model.Form object.
     */
    that.setStandardFormEventResponses = function (form) {
        form.on('form-property-changed', function (e) {
            var MT = formdesigner.controller.getCurrentlySelectedMugType();
            if (MT) {
                formdesigner.ui.showVisualValidation(MT);
                formdesigner.ui.setTreeValidationIcon(MT);
            }
        });

        form.on('form-property-changed', function() {
            formdesigner.controller.setFormChanged();
        });
    }

    /**
     * Renames a node in the JSTree display tree
     * @param ufid - MugType ufid
     * @param val - New value of the display label
     */
    that.changeUITreeNodeLabel = function (ufid, val) {
        var el = $('#' + ufid);
        $('#fd-question-tree').jstree('rename_node',el,val);
    }

    that.getDataMugDisplayName = function (mugType) {
        var mugProps, dEl;

        if(!mugType || !mugType.mug) {
            return 'No Name!'
        }

        mugProps = mugType.mug.properties;
        if (mugProps.dataElement) {
            dEl = mugProps.dataElement.properties;
        } else {
            return 'Has no Data Element!';
        }

        return dEl.nodeID;
    }

    that.getMugDisplayName = function (mugType) {
        var itextItem, nodeID, cEl,dEl,bEl, mugProps, disp, lang, Itext;
        if(!mugType || !mugType.mug) {
            return 'No Name!'
        }
        mugProps = mugType.mug.properties;
        if (mugProps.controlElement) {
            cEl = mugProps.controlElement.properties;
        }
        if (mugProps.dataElement) {
            dEl = mugProps.dataElement.properties;
        }
        if (mugProps.bindElement) {
            bEl = mugProps.bindElement.properties;
        }
        Itext = formdesigner.model.Itext;

        if(cEl) {
            itextItem = cEl.labelItextID;
        }

        if(!itextItem) {
            if(bEl) {
                nodeID = bEl.nodeID;
            }
            if(!nodeID){
                if(dEl) {
                    nodeID = dEl.nodeID;
                }
            }
            if(nodeID) {
                disp = nodeID;
            } else {
                disp = 'No Display Name!';
            }
            return disp;
        }

        lang = formdesigner.currentItextDisplayLanguage;
        if(!lang) {
            lang = Itext.getDefaultLanguage();
        }

        if(!lang) {
            return 'No Translation Data';
        }

        if (!itextItem) {
            return cEl.defaultValue || "";
        } else {
            disp = itextItem.getValue("default", lang);
            return disp ? disp : itextItem.getValue("long", lang);
        }
    };
    
    /*
     * Utility to check if something is a valid element name
     */
    that.isValidElementName = function (name) {
        // HT: http://stackoverflow.com/questions/2519845/how-to-check-if-string-is-a-valid-xml-element-name
        var elementNameRegex = /^(?!XML)[a-zA-Z][\w0-9-]*$/;
        return elementNameRegex.test(name);
    };
    
    /*
     * Assumes we're in a quoted string, and replaces special characters
     * so that they don't break xml
     * 
     */
    that.escapeQuotedXML = function (text, options) {
        // force to string
        text = "" + text; 
        
        if (!text) {
            return "";
        }
        
        // special case this because we want the default to be true
        var escapeQuotes = (options && options.hasOwnProperty("escapeQuotes")) ? options.escapeQuotes : true;
        
        // have to do these first
        if (options && options.escapeAmpersands) {
            text = text.replace(/&/,'&amp;');
        }
        // these are required
        text = text.replace(/</g,'&lt;');
        text = text.replace(/>/g,'&gt;');
        // these are optional
        if (options && options.escapeApostrophes) {
            text = text.replace(/'/g, "&apos;");
        }
        if (escapeQuotes) {
            text = text.replace(/"/g,'&quot;');
        }
        return text;
    };
    
    // monkey patch the xmlwriter for convenience
    XMLWriter.prototype.writeAttributeStringSafe = function (name, value, options) {
        return this.writeAttributeString(name, that.escapeQuotedXML(value, options));
    }; 
    
    /**
     * Turns a list of strings into a single tab separated straing.
     * Replaces newlines with ' ' so they don't affect the spacing.
     * @param list
     */
    
    that.tabSeparate = function (list) {
        var cleanVal = function (val) {
            return val.replace(/\n/g, ' ');
        };
        return list.map(cleanVal).join("\t");
    };
    
        
    that.mugToXPathReference = function (mug) {
        // for select items, return the quoted value.
        // for everything else return the path
        if (mug.typeName === "Select Item") {
            return '"' + mug.mug.properties.controlElement.properties.defaultValue + '"';
        } else {
            // for the currently selected mug, return a "."
            return (mug.ufid === formdesigner.controller.getCurrentlySelectedMugType().ufid) ? "." : formdesigner.controller.form.dataTree.getAbsolutePath(mug);
        }
    };
    
    that.mugToAutoCompleteUIElement = function (mug) {
        return {id:   that.mugToXPathReference(mug),
                uid:  mug.ufid,
                name: that.getMugDisplayName(mug) };
    };
        
    that.isSelect = function (mug) {
        return (mug.typeSlug === "select" ||
                mug.typeSlug === "1select");
    };
    
    that.isSelectItem = function (mug) {
        return (mug.typeSlug === "item");
    };

    /**
     * Parses the required attribute string (expecting either "true()" or "false()" or nothing
     * and returns either true, false or null
     * @param attrString - string
     */
    that.parseBoolAttributeValue = function (attrString) {
        if (!attrString) {
            return null;
        }
        var str = attrString.toLowerCase().replace(/\s/g, '');
        if (str === 'true()') {
            return true;
        } else if (str === 'false()') {
            return false;
        } else {
            return null;
        }
    };

    /**
     * Converts true to 'true()' and false to 'false()'. Returns null for all else.
     * @param req
     */
    that.createXPathBoolFromJS = function(req) {
        if(req === true || req === 'true') {
            return 'true()';
        }else if (req === false || req === 'false') {
            return 'false()';
        } else {
            return null;
        }
    };
    
    /**
     * Filter a list based on a function
     */
    that.filterList = function (list, func) {
        var ret = [];
        for (var i = 0; i < list.length; i++) {
            if (func(list[i])) {
                ret.push(list[i]);
            }
        }
        return ret;
    };
    
    that.getOneOrFail = function (list, infoMsg) {
        if (list.length === 0) {
            throw ("No match for " + infoMsg + " found!");
        } else if (list.length > 1) {
            throw ("Multiple matches for " + infoMsg + " found!");
        }
        return list[0];
    };
    
    that.reduceToOne = function (list, func, infoMsg) {
        return that.getOneOrFail(that.filterList(list, func), infoMsg);
    };
    return that;

}());