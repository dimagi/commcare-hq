/*jslint browser: true, maxerr: 50, indent: 4 */
/**
 * Model classes and functions for the FormDesigner
 */
if (typeof formdesigner === 'undefined') {
    var formdesigner = {};
}

function stacktrace() {
  function st2(f) {
    return !f ? [] :
        st2(f.caller).concat([f.toString().split('(')[0].substring(9) + '(' + f.arguments.join(',') + ')']);
  }
  return st2(arguments.callee.caller);
}

formdesigner.model = function () {
    var that = {};
    var exists = formdesigner.util.exists; //jack it from the util module
    /**
     * A mug is the standard object within a form
     * and represents the combined Data, Bind and Control
     * elements (accessible through the Mug) in all their
     * valid combinations. Validity of a mug is determined
     * by the Definition object.
     *
     * possible constructor params:
     * {
     *  bindElement,
     *  dataElement,
     *  controlElement,
     *  definition  //this is the definitionObject that specifies this mug's validation rules
     *  }
     */
    var Mug = function (spec) {
        var that = {}, mySpec, dataElement, bindElement, controlElement;

        //give this object a unqiue fd id
        formdesigner.util.give_ufid(that);

        that.properties = {};
        if (typeof spec === 'undefined') {
            mySpec = {};
        } else {
            mySpec = spec;
        }

        /**
         * This constructor will take in a spec
         * consisting of various elements (see Mug comments)
         */
        (function construct(spec) {
            var i;
            for (i in spec) {
                if (spec.hasOwnProperty(i)) {
                    that.properties[i] = spec[i];
                }
            }
        }(mySpec));

        that.getBindElementID = function () {
            if (this.properties.bindElement) {
                return this.properties.bindElement.properties.nodeID;
            } else {
                return null;
            }
        };

        that.getDataElementID = function () {
            if (this.properties.dataElement) {
                return this.properties.dataElement.properties.nodeID;
            } else {
                return null;
            }
        };

        that.getDisplayName = function () {
            var retName = this.getBindElementID();
            if (!retName) {
                retName = this.getDataElementID();
            }
            if (!retName) {
                if (this.properties.controlElement) {
                    retName = this.properties.controlElement.properties.label;
                }
            }
            return retName;
        };

        that.toString = function () {
            return "Mug";
        };

        //make the object event aware
        formdesigner.util.eventuality(that);
        return that;
    };
    that.Mug = Mug;

    var Xhtml = function () {
        var that = {};
        //make the object event aware
        formdesigner.util.eventuality(that);
    };
    that.xhtml = Xhtml;

    var Localization = function () {
        var that = {};
        //make the object event aware
        formdesigner.util.eventuality(that);
    };
    that.Localization = Localization;

    /**
     * The bind object (representing the object
     * that transforms data and hands it off to the
     * dataElement object).
     *
     * Constructor object (spec) can have the following attributes
     * {
     *  dataType, //typically the xsd:dataType
     *  relevant,
     *  calculate,
     *  constraint,
     *  constraintMsg, //jr:constraintMsg
     *  nodeID //optional
     * }
     *
     * @param spec
     */
    var BindElement = function (spec) {
        var that = {};
        that.properties = {};


        //give this object a unqiue fd id
        formdesigner.util.give_ufid(that);
        var attributes;

        (function constructor(the_spec) {
            if (typeof the_spec === 'undefined') {
                return null; //nothing to be done.
            } else {
                var i;
                //also attach the attributes to the root 'that' object:
                for (i in the_spec) {
                    if (the_spec.hasOwnProperty(i)) {
                        that.properties[i] = the_spec[i];
                    }
                }
            }
        }(spec));

        that.toString = function () {
            return 'Bind Element: ' + this.properties.nodeID;
        }

        //make the object event aware
        formdesigner.util.eventuality(that);
        return that;
    };
    that.BindElement = BindElement;

    /**
     * A LiveText object is able to
     * take in Strings and Objects (with their specified
     * callback functions that produce strings) in order
     * render a LiveString with the latest changes to the objects
     * it is tracking, on command (call renderString on this object
     * to get a... rendered string).
     */
    var LiveText = function () {
        //Todo eventually: add checking for null pointer tokens

        var that = {};

        var phrases = [];

        /**
         * Renders the token in the phrases list specified by tokenIndex
         * and returns it as a string
         * @param tokenIndex
         */
        var getRenderedToken = function (tokenIndex) {
            var tObj;
            var outString = '';
            if (tokenIndex > phrases.length - 1) {
                return undefined;
            }
            tObj = phrases[tokenIndex];
            if (typeof tObj.refObj === 'undefined') {
                throw "incorrect Live Object added to LiveText! Can't render string.";
            } else if (typeof tObj.refObj === 'string') {
                outString += tObj.refObj;
            } else {
                outString += tObj.callback.apply(tObj.refObj, tObj.params);
            }
            return outString;
        };

        /**
         * Get the string this liveText represents
         * with all the function/object references replaced with
         * their textual representations (use add()
         * to add strings/objects when building a liveText)
         */
        that.renderString = function () {
            var outString = "";
            var i;
            for (i = 0; i < phrases.length; i++) {
                outString += getRenderedToken(i);
            }
            return outString;
        };


        //////TODO REMOVE CALLBACK PARAMS


        /**
         * Add a token to the list
         * of this liveText object.
         * When adding a string,
         * the callback param is optional.  When
         * adding anything else, specify a callback function
         * to call (with or without params). If no callback
         * is specified in that case, an exception will be thrown
         * @param token - the object (or string) that represents the string data
         * @param callback - the callback function that should be used on the token obj to retrieve a string (if token is an object)
         * @param params is an array of arguments to be applied to the callback function (if a callback was specified)
         */
        that.addToken = function (token, callback, params) {
            var tObj = {};
            if (typeof token === 'string') {
                tObj.refObj = token;
            } else {
                tObj.refObj = token;
                tObj.callback = callback;
                tObj.params = params;
            }
            phrases.push(tObj);
        };

        /**
         * Returns the list of token objects
         * (an array of mixed strings and/or objects)
         */
        that.getTokenList = function () {
            return phrases;
        };


        //make this object event aware.
        formdesigner.util.eventuality(that);
        return that;
    };
    that.LiveText = LiveText;

    /**
     * DataElement is the object representing the final resting (storage)
     * place of data entered by the user and/or manipulated by the form.
     *
     * Constructor spec:
     * {
     *  name,
     *  defaultData,
     * }
     */
    var DataElement = function (spec) {
        var that = {};
        that.properties = {};

        (function constructor(mySpec) {
            if (typeof mySpec === 'undefined') {
                return null; //nothing to be done.
            } else {
                var i;
                //also attach the attributes to the root 'that' object:
                for (i in mySpec) {
                    if (mySpec.hasOwnProperty(i)) {
                        that.properties[i] = mySpec[i];
                    }
                }
            }
        }(spec));

        //give this object a unqiue fd id
        formdesigner.util.give_ufid(that);

        //make the object event aware
        formdesigner.util.eventuality(that);
        return that;
    };
    that.DataElement = DataElement;

    /**
     * The controlElement represents the object seen by the user during
     * an entry session.  This object usually takes the form of a question
     * prompt, but can also be a notification message, or some other type
     * of user viewable content.
     * spec:
     * {
     *  typeName, //the type string indicating what type of Control Element this is
     *            //see the control_definitions (tag_name) object e.g. "input"
     *  controlName //control_definition.controlElement.controlType.name; e.g. "text"
     *  //optional:
     *  label
     *  hintLabel
     *  labelItext
     *  hintItext
     *  defaultValue
     *
     * }
     */
    var ControlElement = function (spec) {
        var that = {};
        that.properties = {};

        var typeName, controlName, label, hintLabel, labelItext, hintItext, defaultValue;
        //give this object a unique fd id
        formdesigner.util.give_ufid(that);

        (function constructor(mySpec) {
            if (typeof mySpec === 'undefined') {
                return null; //nothing to be done.
            } else {
                var i;
                //also attach the attributes to the root 'that' object:
                for (i in mySpec) {
                    if (mySpec.hasOwnProperty(i)) {
                        that.properties[i] = mySpec[i];
                    }
                }
            }
        }(spec));

        //make the object event aware
        formdesigner.util.eventuality(that);
        return that;
    };
    that.ControlElement = ControlElement;


    ///////////////////////////////////////////////////////////////////////////////////////
    //////    DEFINITION (MUG TYPE) CODE //////////////////////////////////////////////////
    ///////////////////////////////////////////////////////////////////////////////////////

    /**
     * Creates a new mug (with default init values)
     * based on the template (MugType) given by the argument.
     *
     * @return the new mug associated with this mugType
     */
    that.createMugFromMugType = function (mugType) {
        /**
         * Walks through the properties (block) and
         * procedurally generates a spec that can be passed to
         * various constructors.
         * Default values are null (for OPTIONAL fields) and
         * "" (for REQUIRED fields).
         * @param block - rule block
         * @param name - name of the spec block being generated
         * @return a dictionary: {spec_name: spec}
         */
        function getSpec(properties){
            var i,j, spec = {};
            for(i in properties){
                if(properties.hasOwnProperty(i)){
                    var block = properties[i];
                    spec[i] = {}
                    for (j in block){
                        if(block.hasOwnProperty(j)){
                            var p = block[j];
                            if(p.presence === 'required' || p.presence === 'optional'){
                                spec[i][j] = null;
                            }
                        }
                    }
                }
            }
            return spec;
        }

        //loop through mugType.properties and construct a spec to be passed to the Mug Constructor.
        //BE CAREFUL HERE.  This is where the automagic architecture detection ends, some things are hardcoded.
        var mugSpec, dataElSpec, bindElSpec, controlElSpec, i,
                mug,dataElement,bindElement,controlElement,
                specBlob = {}, validationResult, mugProps, defaultItextValue;

        specBlob = getSpec(mugType.properties);
        mugSpec = specBlob || undefined;
        dataElSpec = specBlob.dataElement || undefined;
        bindElSpec = specBlob.bindElement || undefined;
        controlElSpec = specBlob.controlElement || undefined;

        //create the various elements, mug itself, and linkup.
        if (mugSpec) {
            mug = new Mug(mugSpec);
            if (controlElSpec) {
                if (formdesigner.util.isSelectItem(mugType) &&
                    typeof controlElSpec.defaultValue !== 'undefined') {
                    controlElSpec.defaultValue = formdesigner.util.generate_item_label();
                }
                mug.properties.controlElement = new ControlElement(controlElSpec);
            }
            if (dataElSpec) {
                if (typeof dataElSpec.nodeID !== 'undefined') {
                    dataElSpec.nodeID = formdesigner.util.generate_question_id();
                }
                mug.properties.dataElement = new DataElement(dataElSpec);
            }
            if (bindElSpec) {
                if (typeof bindElSpec.nodeID !== 'undefined') {
                    if (dataElSpec.nodeID) {
                        bindElSpec.nodeID = dataElSpec.nodeID; //make bind id match data id for convenience
                    }else{
                        bindElSpec.nodeID = formdesigner.util.generate_question_id();
                    }
                }
                mug.properties.bindElement = new BindElement(bindElSpec);
            }


        }
        //Bind the mug to it's mugType
        mugType.mug = mug || undefined;
        
        // utility functions
        mugType.hasControlElement = function () {
            return Boolean(this.mug.properties.controlElement);
        }
        mugType.hasDataElement = function () {
            return Boolean(this.mug.properties.dataElement);
        }
        mugType.hasBindElement = function () {
            return Boolean(this.mug.properties.bindElement);
        }
        
        mugType.getDefaultItextRoot = function () {
            var nodeID, parent;
            if (this.hasBindElement()) { //try for the bindElement nodeID
                nodeID = this.mug.properties.bindElement.properties.nodeID;
            } else if (this.hasDataElement()) {
                // if nothing, try the dataElement nodeID
                nodeID = this.mug.properties.dataElement.properties.nodeID;
            } else if (formdesigner.util.isSelectItem(this)) {
                // if it's a select item, generate based on the parent and value
                parent = formdesigner.controller.form.controlTree.getParentMugType(this);
                if (parent) {
                    nodeID = parent.getDefaultItextRoot() + "-" + this.mug.properties.controlElement.properties.defaultValue;
                }
            } 
            if (!nodeID) {
                // all else failing, make a new one
                nodeID = formdesigner.util.generate_item_label();
            }
            return nodeID;
        };
        
        mugType.getDefaultLabelItextId = function () {
            // Default Itext ID
            return this.getDefaultItextRoot() + "-label";
        };
        
        /*
         * Gets a default label, auto-generating if necessary
         */
        mugType.getDefaultLabelValue = function () {
            if (this.hasControlElement() && this.mug.properties.controlElement.properties.label) {
                return this.mug.properties.controlElement.properties.label;
            } 
            else if (this.hasDataElement()) {
                return this.mug.properties.dataElement.properties.nodeID;
            } else if (this.hasBindElement()) {
                return this.mug.properties.bindElement.properties.nodeID;
            } else if (formdesigner.util.isSelectItem(this)) {
                return this.mug.properties.controlElement.properties.defaultValue;
            } else {
                // fall back to generating an ID
                return formdesigner.util.generate_item_label();
            } 
        };
        
        /*
         * Gets the actual label, either from the control element or an empty
         * string if not found.
         */
        mugType.getLabelValue = function () {
            if (this.mug.properties.controlElement.properties.label) {
                return this.mug.properties.controlElement.properties.label;
            } else {
                return "";
            } 
            
        };
        
        mugType.getDefaultLabelItext = function (defaultValue) {
            var formData = {};
            formData[that.Itext.getDefaultLanguage()] = defaultValue;
            return new that.ItextItem({
                id: this.getDefaultLabelItextId(),
                forms: [new that.ItextForm({
                            name: "default",
                            data: formData
                        })]
            });
        };
        
        // Add some useful functions for dealing with itext.
        mugType.setItextID = function (val) {
            if (this.hasControlElement()) {
                this.mug.properties.controlElement.properties.labelItextID.id = val;
            }
        };
        
        mugType.getItext = function () {
            if (this.hasControlElement()) {
                return this.mug.properties.controlElement.properties.labelItextID;
            } 
        };
        mugType.getHintItext = function () {
            if (this.hasControlElement()) {
                return this.mug.properties.controlElement.properties.hintItextID;
            }
        }
        mugType.getConstraintMsgItext = function () {
            if (this.hasBindElement()) {
                return this.mug.properties.bindElement.properties.constraintMsgItextID;
            }
        };
        
        return mug;
    };

    var validateElementName = function (value, displayName) {
        if (!formdesigner.util.isValidElementName(value)) {
            return value + " is not a legal " + displayName + ". Must start with a letter and contain only letters, numbers, and '-' or '_' characters.";
        }
        return "pass";            
    };
    
    var validateItextItem = function (itextItem, name) {
        if (itextItem) {
	        var val = itextItem.defaultValue();
	        if (itextItem.id && !val) {
	            return "Question has " + name + " ID but no " + name + " label!";
	        }
	        if (val && !itextItem.id) {
	            return "Question has " + name + " label but no " + name + " ID!";
	        }
        }
        return "pass";
    };
        
    var validationFuncs = {
        //should be used to figure out the logic for label, defaultLabel, labelItext, etc properties
        nodeID: function (mugType, mug) {
            var qId = mug.properties.dataElement.properties.nodeID;
            var res = validateElementName(qId, "Question ID");
            if (res !== "pass") {
                return res;
            }
            // check for dupes
            var hasDuplicateId = function (qId) {
                var allMugs = formdesigner.controller.getMugTypeList();
                var hasDupeArray = allMugs.map(function (node) {
                    // skip ourselves, checking for dupes
                    return node.hasDataElement() && node.ufid != mugType.ufid && 
                           node.mug.properties.dataElement.properties.nodeID === qId;
                });
                return hasDupeArray.indexOf(true) !== -1;
            }
            if (hasDuplicateId(qId)) {
                return qId + " is a duplicate ID in the form. Question IDs must be unique.";
            }
            return "pass";
        }, 
        label: function (mugType, mug) {
            var controlBlock, hasLabel, hasLabelItextID, missing, hasItext, Itext;
            Itext = formdesigner.model.Itext;
            controlBlock = mug.properties.controlElement.properties;
            hasLabel = Boolean(controlBlock.label);
            var itextBlock = mugType.getItext();
            hasLabelItextID = Boolean(itextBlock && itextBlock.id);
            
            if (hasLabelItextID){
                var res = validateElementName(itextBlock.id, "Label IText ID");
	            if (res !== "pass") {
	                return res;
	            }
                hasItext = itextBlock.hasHumanReadableItext();
            } else {
                hasItext = false;
            }
            if (hasLabel) {
                return 'pass';
            } else if (!hasLabel && !hasItext && (mugType.properties.controlElement.label.presence === 'optional' || 
                       mugType.properties.controlElement.labelItextID.presence === 'optional')) {
                //make allowance for questions that have label/labelItextID set to 'optional'
                return 'pass';
            } else if (hasLabelItextID && hasItext) {
                return 'pass';
            } else if (hasLabelItextID && !hasItext) {
                missing = 'a display label';
            } else if (!hasLabel && !hasLabelItextID) {
                missing = 'a display label ID';
            } else if (!hasLabel) {
                missing = 'a display label'
            } else if (!hasLabelItextID) {
                missing = 'a display label ID';
            }
            return 'Question is missing ' + missing + ' value!';
        },
        hintItextID: function (mugType, mug) {
            var controlBlock, hintItext, itextVal, Itext, controlElement;
            controlBlock = mugType.properties.controlElement;
            controlElement = mug.properties.controlElement.properties;
            Itext = formdesigner.model.Itext;
            hintItext = controlElement.hintItextID;
            if (hintItext && hintItext.id) {
                var res = validateElementName(hintItext.id, "Hint IText ID");
                if (res !== "pass") {
                    return res;
                }
                
            }
            if(controlBlock.hintItextID === 'required' && !hintIID) {
                return 'Hint Itext ID is required but not present in this question!';
            }
            
            return validateItextItem(hintItext, "Hint Itext");
        },
        constraintItextId: function (mugType, mug) {
            var bindElement = mug.properties.bindElement.properties;
            var IT = formdesigner.model.Itext;
            
            var constraintItext = bindElement.constraintMsgItextID;
            if (constraintItext && constraintItext.id) {
                var res = validateElementName(constraintItext.id, "Constraint IText ID");
                if (res !== "pass") {
                    return res;
                }
            }
            if (constraintItext && constraintItext.id && !bindElement.constraintAttr) {
                return "Can't have a constraint Itext ID without a constraint";
            }
            return validateItextItem(constraintItext, "Constraint Itext");
        },
        defaultValue: function (mugType, mug) {
            if (/\s/.test(mug.properties.controlElement.properties.defaultValue)) {
                return "Whitespace in values is not allowed.";
            } 
            return "pass";
        }
        
    };

    that.validationFuncs = validationFuncs;


    var RootMugType = {
        typeName: "The Abstract Mug Type Definition", //human readable Type Name (Can be anything)
        type : "root", //easier machine readable value for the above;
        //type var can contain the following values: 'd', 'b', 'c', ('data', 'bind' and 'control' respectively)
        // or any combination of them. For example, a Mug that contains a dataElement and a controlElement (but no bindElement)
        // would be of type 'dc'.  'root' is the exception for the abstract version of the MugType (which should never be directly used anyway).
        // use: formdesigner.util.clone(RootMugType); instead. (As done below in the mugTypes object).

        //set initial properties
        /**
         * A property is a key:value pair.
         * Properties values can take one of 4 forms.
         * Property keys are the name of the field in the actual mug to be looked at during validation.
         * The four (4) forms of property values:
         *  - One of the type flags (e.g. TYPE_FLAG_REQUIRED)
         *  - A string, representing the actual string value a field should have in the mug
         *  - A dictionary (of key value pairs) illustrating a 'block' (e.g. see the bindElement property below)
         *  - a function (taking a block of fields from the mug as its only argument). The function MUST return either
         *     the string 'pass' or an error string.
         *
         *     PropertyValue = {
         *          editable: 'r|w|rw', //(read) or (write) or (read and write) (by the user)
         *          visibility: 'hidden|visible', //show as a user editable property?
         *          presence: 'required|optional|notallowed' //must this property be set, optional or should not be present?
         *          [values: [arr of allowable vals]] //list of allowed values for this property
         *          [validationFunc: function(mugType,mug)] //special validation function, optional, return errorMessage string or 'pass'
         *          lstring: "Human Readable Property Description" //Optional
         *      }
         *
         */
        properties : {
            dataElement: {
                nodeID: {
                    editable: 'w',
                    visibility: 'visible',
                    presence: 'required',
                    lstring: 'Question ID',
                    validationFunc : validationFuncs.nodeID
                },
                dataValue: {
                    editable: 'w',
                    visibility: 'advanced',
                    presence: 'optional',
                    lstring: 'Default Data Value'
                },
                keyAttr: {
                    editable: 'w',
                    visibility: 'advanced',
                    presence: 'optional',
                    lstring: 'JR:Preload key value'
                },
                xmlnsAttr: {
                    editable: 'w',
                    visibility: 'advanced',
                    presence: 'optional',
                    lstring: "Special Data Node XMLNS attribute"
                }
            },
            bindElement: {
                nodeID: {
                    editable: 'w',
                    visibility: 'advanced',
                    presence: 'optional',
                    lstring: 'Bind Node ID'
                },
                dataType: {
                    editable: 'w',
                    visibility: 'visible',
                    presence: 'optional',
                    values: formdesigner.util.XSD_DATA_TYPES,
                    uiType: 'select',
                    lstring: 'Data Type'
                },
                relevantAttr: {
                    editable: 'w',
                    visibility: 'visible',
                    presence: 'optional',
                    uiType: "xpath",
                    xpathType: "bool",
                    lstring: 'Display Condition'
                },
                calculateAttr: {
                    editable: 'w',
                    visibility: 'visible',
                    presence: 'optional',
                    uiType: "xpath",
                    xpathType: "generic",
                    lstring: 'Calculate Condition'
                },
                constraintAttr: {
                    editable: 'w',
                    visibility: 'visible',
                    presence: 'optional',
                    uiType: "xpath",
                    xpathType: "bool",
                    lstring: 'Validation Condition'
                },
                constraintMsgItextID: {
                    editable: 'w',
                    visibility: 'advanced',
                    presence: 'optional',
                    lstring: "Constraint Itext ID",
                    uiType: "itext-id",
                    validationFunc: validationFuncs.constraintItextId
                },
                constraintMsgAttr: {
                    editable: 'w',
                    visibility: 'hidden',
                    presence: 'optional',
                    validationFunc : function (mugType, mug) {
                        var bindBlock = mug.properties.bindElement.properties;
                        var hasConstraint = (typeof bindBlock.constraintAttr !== 'undefined');
                        var hasConstraintMsg = (bindBlock.constraintMsgAttr || 
                                                (bindBlock.constraintMsgItextID && bindBlock.constraintMsgItextID.id));
                        if (hasConstraintMsg && !hasConstraint) {
                            return 'ERROR: Bind cannot have a Constraint Message with no Constraint!';
                        } else {
                            return 'pass';
                        }
                    },
                    lstring: 'Constraint Message'
                },
                requiredAttr: {
                    editable: 'w',
                    visibility: 'visible',
                    presence: 'optional',
                    lstring: "Is this Question Required?",
                    uiType: "checkbox"
                },
                preload: {
                    editable: 'w',
                    visibility: 'advanced',
                    presence: 'optional',
                    lstring: "JR Preload"
                },
                preloadParams: {
                    editable: 'w',
                    visibility: 'advanced',
                    presence: 'optional',
                    lstring: "JR Preload Param"
                },
                nodeset: {
                    editable: 'r',
                    visibility: 'hidden',
                    presence: 'optional' //if not present one will be generated... hopefully.
                }
            },
            controlElement: {
                name: { //internal use
                    editable: 'w',
                    visibility: 'hidden',
                    presence: 'required',
                    values: formdesigner.util.VALID_QUESTION_TYPE_NAMES
                },
                defaultValue: {
		            lstring: 'Item Value',
		            visibility: 'hidden',
		            editable: 'w',
		            presence: 'optional',
		            validationFunc: validationFuncs.defaultValue
                },
        
                tagName: { //internal use
                    editable: 'r',
                    visibility: 'hidden',
                    presence: 'required',
                    values: formdesigner.util.VALID_CONTROL_TAG_NAMES
                },
                label: {
                    editable: 'w',
                    visibility: 'hidden',
                    presence: 'optional',
                    validationFunc : validationFuncs.label,
                    lstring: "Default Label"
                },
                hintLabel: {
                    editable: 'w',
                    visibility: 'advanced',
                    presence: 'optional',
                    lstring: "Hint Label"
                },
                labelItextID: {
                    editable: 'w',
                    visibility: 'advanced',
                    presence: 'optional',
                    lstring: "Question Itext ID",
                    uiType: "itext-id",
                    validationFunc : validationFuncs.label
                },
                hintItextID: {
                    editable: 'w',
                    visibility: 'advanced',
                    presence: 'optional',
                    lstring: "Question HINT Itext ID",
                    uiType: "itext-id",
                    validationFunc: validationFuncs.hintItextID
                }
            }
        },
        
        getPropertyDefinition: function (index) {
            // get a propery definition by a string or list index
            // assumes strings are split by the "/" character
            if (!(index instanceof Array)) {
                index = index.split("/");
            } 
            // this will raise a reference error if you give it a bad value
            var ret = this.properties;
            for (var i = 0; i < index.length; i++) {
                ret = ret[index[i]];
            }
            return ret;
        },
        getPropertyValue: function (index) {
            // get a propery value by a string or list index
            // assumes strings are split by the "/" character
            if (!(index instanceof Array)) {
                index = index.split("/");
            } 
            // this will raise a reference error if you give it a bad value
            var ret = this.mug;
            for (var i = 0; i < index.length; i++) {
                ret = ret["properties"];
                ret = ret[index[i]];
            }
            return ret;
        },
        //for validating a mug against this internal definition we have.
        validateMug : function () {
            /**
             * Takes in a key-val pair like {"controlNode": 'required'}
             * and an object to check against, and tell you if the object lives up to the rule
             * returns true if the object abides by the rule.
             *
             * For example, if the rule above is used, we pass in a mug to check if it has a controlNode.
             * If a property with the name of "controlNode" exists, true will be returned since it is required and present.
             *
             * if the TYPE_FLAG is 'optional', true will always be returned.
             * if 'notallowed' and a property with it's corresponding key IS present in the testing object,
             * false will be returned.
             *
             * if a TYPE_FLAG is not used, check the value. (implies that this property is required)
             * @param ruleKey
             * @param ruleValue
             * @param testingObj
             */
            var validateRule = function (ruleKey, ruleValue, testingObj, blockName, curMugType, curMug) {
                var retBlock = {},
                        visible = ruleValue.visibility,
                        editable = ruleValue.editable,
                        presence = ruleValue.presence;

                retBlock.ruleKey = ruleKey;
                retBlock.ruleValue = ruleValue;
                retBlock.objectValue = testingObj;
                retBlock.blockName = blockName;
                retBlock.result = 'unchecked';

                if (!testingObj) {
                    return retBlock;
                }

                if (presence === 'optional') {
                    retBlock.result = 'pass';
                    retBlock.resultMessage = '"' + ruleKey + '" is Optional in block:' + blockName;
                } else if (presence === 'required') {
                    if (testingObj[ruleKey]) {
                        retBlock.result = 'pass';
                        retBlock.resultMessage = '"' + ruleKey + '" is Required and Present in block:' + blockName;
                    } else {
                        retBlock.result = 'fail';
                        retBlock.resultMessage = '"' + ruleKey + '" value is required in:' + blockName + ', but is NOT present!';
                    }
                } else if (presence === 'notallowed') {
                    if (!testingObj[ruleKey]) { //note the equivalency modification from the above
                        retBlock.result = 'pass';
                    } else {
                        retBlock.result = 'fail';
                        retBlock.resultMessage = '"' + ruleKey + '" IS NOT ALLOWED IN THIS OBJECT in:' + blockName;
                    }
                } else {
                    retBlock.result = 'fail';
                    retBlock.resultMessage = '"' + ruleKey + '" MUST BE OF TYPE_OPTIONAL, REQUIRED, NOT_ALLOWED or a "string" in block:' + blockName;
                    retBlock.ruleKey = ruleKey;
                    retBlock.ruleValue = ruleValue;
                    retBlock.testingObj = testingObj;
                }

                if (retBlock.result !== "fail" && ruleValue.validationFunc) {
                    var funcRetVal = ruleValue.validationFunc(curMugType,curMug);
                    if (funcRetVal === 'pass') {
                        retBlock.result = 'pass';
                        retBlock.resultMessage = '"' + ruleKey + '" is a string value (Required) and Present in block:' + blockName;
                    } else {
                        retBlock.result = 'fail';
                        retBlock.resultMessage = funcRetVal;
                    }
                }

                return retBlock;
            };

            /**
             * internal method that loops through the properties in this type definition
             * recursively and compares that with the state of the mug (using validateRule
             * to run the actual comparisons).
             *
             * The object that is returned is a JSON object that contains information
             * about the validation. returnObject["status"] will be either "pass" or "fail"
             * "status" will be set to fail if any one property is not in the required state
             * in the mug.
             * @param propertiesObj
             * @param testingObj - the Mug properties block.
             * @param blockName
             */
            var checkProps = function (mugT,propertiesObj, testingObj, blockName) {
                var i, j,y,z, results, testObjProperties,
                        mug = mugT.mug,
                        mugProperties = mug.properties;
                results = {"status": "pass"}; //set initial status
                results.blockName = blockName;
                if (!(testingObj || undefined)) {
                    results.status = "fail";
                    results.message = "No testing object passed for propertiesObj " + JSON.stringify(propertiesObj);
                    results.errorType = "NullPointer";
                    return results;
                }
                for (i in propertiesObj) {
                    if(propertiesObj.hasOwnProperty(i)){
                        var block = propertiesObj[i],
                                tResults = {};
                        for(y in block){
                            if(block.hasOwnProperty(y)){
                                if(!testingObj[i]){
                                    throw 'No Mug.properties??'
                                }
                                tResults[y] = validateRule(y,block[y],testingObj[i].properties,i,mugT,mugT.mug);
                                if (tResults[y].result === "fail") {
                                    results.status = "fail";
                                    results.message = tResults[y].resultMessage;
                                    results.errorBlockName = tResults[y].blockName;
                                    results[i] = tResults;
                                }

                            }
                        }
                        results[i] = tResults;
                    }
                }

                for(j in mugProperties){
                    if(mugProperties.hasOwnProperty(j)){
                        var pBlock = mugProperties[j];
                        for (z in pBlock.properties){
                            // allow "_propertyName" convention for system properties
                            if(pBlock.properties.hasOwnProperty(z) && z.indexOf("_") !== 0){
                                var p = pBlock.properties[z],
                                        rule = propertiesObj[j][z];
                                if(p && (!rule || rule.presence === 'notallowed')){
                                    results.status = "fail";
                                    results.message = j + " has property '" + z + "' but no rule is present for that property in the MugType!";
                                    results.errorBlockName = j;
                                    results.errorProperty = z;
                                    results.errorType = 'MissingRuleValidation';
                                    results.propertiesBlock = pBlock;
                                }

                            }
                        }
                    }
                }
                return results;

            },

            /**
             * Checks the type string of a MugType (i.e. the mug.type value)
             * to see if the correct properties block Elements are present (and
             * that there aren't Elements there that shouldn't be).
             * @param mugT - the MugType to be checked
             */
            checkTypeString = function (mugT) {
                        var typeString = mugT.type, i,
                                hasD = (mugT.properties.dataElement ? true : false),
                                hasC = (mugT.properties.controlElement ? true : false),
                                hasB = (mugT.properties.bindElement ? true : false);

                        if (hasD) {
                            if (typeString.indexOf('d') === -1) {
                                return {status: 'fail', message: "MugType.type has a 'dataElement' in its properties block but no 'd' char in its type value!"};
                            }
                        } else {
                            if (typeString.indexOf('d') !== -1) {
                                return {status: 'fail', message: "MugType.type has a 'd' char in it's type value but no 'd' !"};
                            }
                        }
                        if (hasB) {
                            if (typeString.indexOf('b') === -1) {
                                return {status: 'fail', message: "MugType.type has a 'bindElement' in its properties block but no 'b' char in its type value!"};
                            }
                        } else {
                            if (typeString.indexOf('b') !== -1) {
                                return {status: 'fail', message: "MugType.type has a 'b' char in it's type value but no 'b' !"};
                            }
                        }
                        if (hasC) {
                            if (typeString.indexOf('c') === -1) {
                                return {status: 'fail', message: "MugType.type has a 'controlElement' in its properties block but no 'c' char in its type value!"};
                            }
                        } else {
                            if (typeString.indexOf('c') !== -1) {
                                return {status: 'fail', message: "MugType.type has a 'c' char in it's type value but no 'c' !"};
                            }
                        }


                        return {status: 'pass', message: "typeString for MugType validates correctly"};
                    },

            mug = this.mug || null;

            if (!mug) {
                throw 'MUST HAVE A MUG TO VALIDATE!';
            }
            var selfValidationResult = checkTypeString(this);
            var validationResult = checkProps(this,this.properties, mug.properties, "Mug Top Level");

            if (selfValidationResult.status === 'fail') {
                validationResult.status = 'fail';
            }
            validationResult.typeCheck = selfValidationResult;
            return validationResult;
        },

        //OBJECT FIELDS//
        controlNodeCanHaveChildren: false,

        /** A list of controlElement.tagName's that are valid children for this control element **/
        controlNodeAllowedChildren : [],
        dataNodeCanHaveChildren: true,

        mug: null,
        toString: function () {
            if (this.mug && this.mug.properties.dataElement) {
                return this.mug.properties.dataElement.properties.nodeID;
            } else {
                return this.typeName;
            }
        }

    };
    formdesigner.util.eventuality(RootMugType);
    that.RootMugType = RootMugType;

    /**
     * WARNING: These are 'abstract' MugTypes!
     * To bring them kicking and screaming into the world, you must call
     * formdesigner.util.getNewMugType(someMT), this will return a fully init'd mugType,
     * where someMT can be either one of the below abstract MugTypes or a 'real' MugType.
     *
     */
    var mugTypes = {
        //the four basic valid combinations of Data, Bind and Control elements
        //when rolling your own, make sure the 'type' variable corresponds
        //to the Elements and other settings in your MugType (e.g. in the 'db' MT below
        //the controlElement is deleted.
        dataBind: function () {
            var mType = formdesigner.util.clone(RootMugType);
            mType.typeSlug = "datanode";
            mType.typeName = "Data Node";
            mType.type = "db";
            delete mType.properties.controlElement;
            return mType;
        }(),
        dataBindControlQuestion: function () {
            var mType = formdesigner.util.clone(RootMugType);
            mType.typeName = "Data Bind Control Question Mug";
            mType.type = "dbc";
            return mType;
        }(),
        dataControlQuestion: function () {
            var mType = formdesigner.util.clone(RootMugType);
            mType.typeName = "Data + Control Question Mug";
            mType.type = "dc";
            delete mType.properties.bindElement;
            return mType;
        }(),
        dataOnly: function () {
            var mType = formdesigner.util.clone(RootMugType);
            mType.typeName = "Data ONLY Mug";
            mType.type = "d";
            delete mType.properties.controlElement;
            delete mType.properties.bindElement;
            return mType;
        }(),
        controlOnly: function () {
            var mType = formdesigner.util.clone(RootMugType);
            mType.typeName = "Control ONLY Mug";
            mType.type = "c";
            delete mType.properties.dataElement;
            delete mType.properties.bindElement;
            return mType;
        }()
    };
    that.mugTypes = mugTypes;

    /**
     * This is the output for MugTypes.  If you need a new Mug or MugType (with a mug)
     * use these functions.  Each of the below functions will create a new MugType and a
     * new associated mug with some  values initialized according to what kind of
     * MugType is requested.
     */
    that.mugTypeMaker = {};
    that.mugTypeMaker.stdTextQuestion = function () {
        var mType = formdesigner.util.getNewMugType(mugTypes.dataBindControlQuestion),
                mug;
        mType.typeSlug = "text";
        mType.typeName = formdesigner.util.QUESTIONS[mType.typeSlug];
        
        mType.controlNodeAllowedChildren = false;
        mug = that.createMugFromMugType(mType);
        mType.mug = mug;
        mType.mug.properties.controlElement.properties.name = "Text";
        mType.mug.properties.controlElement.properties.tagName = "input";
        mType.mug.properties.bindElement.properties.dataType = "xsd:string";
        return mType;
    };

    that.mugTypeMaker.stdDataBindOnly = function () {
        var mType = formdesigner.util.getNewMugType(mugTypes.dataBind),
        mug;
        mType.typeSlug = "datanode";
        mType.typeName = formdesigner.util.QUESTIONS[mType.typeSlug];
        
        mType.controlNodeAllowedChildren = false;
        mug = that.createMugFromMugType(mType);
        mType.mug = mug;
        return mType;
    };

    that.mugTypeMaker.stdSecret = function () {
        var mType = formdesigner.util.getNewMugType(mugTypes.dataBindControlQuestion),
                mug;
        mType.typeSlug = "secret";
        mType.typeName = formdesigner.util.QUESTIONS[mType.typeSlug];
        
        mType.controlNodeAllowedChildren = false;
        mug = that.createMugFromMugType(mType);
        mType.mug = mug;
        mType.mug.properties.controlElement.properties.name = "Secret";
        mType.mug.properties.controlElement.properties.tagName = "secret";

        mType.properties.bindElement.dataType.validationFunc = function (mt,m) {
            var dtype = m.properties.bindElement.properties.dataType;
            if (formdesigner.util.XSD_DATA_TYPES.indexOf(dtype) !== -1) {
                return 'pass';
            } else {
                return 'Password question data type must be a valid XSD Datatype!';
            }
        };
        mType.properties.bindElement.dataType.lstring = 'Data Type';
        mType.mug.properties.bindElement.properties.dataType = "xsd:string";
        return mType;
    };

    that.mugTypeMaker.stdInt = function () {
        var mType = formdesigner.util.getNewMugType(mugTypes.dataBindControlQuestion),
                mug;
        mType.typeSlug = "int";
        mType.typeName = formdesigner.util.QUESTIONS[mType.typeSlug];
        
        mType.controlNodeAllowedChildren = false;
        mug = that.createMugFromMugType(mType);
        mType.mug = mug;
        mType.mug.properties.controlElement.properties.name = "Integer";
        mType.mug.properties.controlElement.properties.tagName = "input";
        mType.mug.properties.bindElement.properties.dataType = "xsd:int";
        return mType;
    };

    that.mugTypeMaker.stdAudio = function () {
        var mType = formdesigner.util.getNewMugType(mugTypes.dataBindControlQuestion),
                mug;
        mType.typeSlug = "audio";
        mType.typeName = formdesigner.util.QUESTIONS[mType.typeSlug];
        mType.controlNodeAllowedChildren = false;
        mType.properties.controlElement.mediaType = {
            lstring: 'Media Type',
            visibility: 'visible',
            editable: 'w',
            presence: 'required'
        };

        mug = that.createMugFromMugType(mType);
        mType.mug = mug;
        mType.mug.properties.controlElement.properties.name = "Audio";
        mType.mug.properties.controlElement.properties.tagName = "upload";
        mType.mug.properties.controlElement.properties.mediaType = "audio/*";
        /* fix buggy eclipse syntax highlighter (because of above string) */ 
        mType.mug.properties.bindElement.properties.dataType = "binary";

        return mType;
    };

    that.mugTypeMaker.stdImage = function () {
        var mType = formdesigner.util.getNewMugType(that.mugTypeMaker.stdAudio()),
                mug;
        mType.typeSlug = "image";
        mType.typeName = formdesigner.util.QUESTIONS[mType.typeSlug];
        mug = that.createMugFromMugType(mType);
        mType.mug = mug;
        mType.mug.properties.controlElement.properties.name = "Image";
        mType.mug.properties.controlElement.properties.tagName = "upload";
        mType.mug.properties.controlElement.properties.mediaType = "image/*";
        /* fix buggy eclipse syntax highlighter (because of above string) */ 
        mType.mug.properties.bindElement.properties.dataType = "binary";
        return mType;
    };

    that.mugTypeMaker.stdVideo = function () {
        var mType = formdesigner.util.getNewMugType(that.mugTypeMaker.stdAudio()),
                mug;
        mType.typeSlug = "video";
        mType.typeName = formdesigner.util.QUESTIONS[mType.typeSlug];
        mug = that.createMugFromMugType(mType);
        mType.mug = mug;
        mType.mug.properties.controlElement.properties.name = "Video";
        mType.mug.properties.controlElement.properties.tagName = "upload";
        mType.mug.properties.controlElement.properties.mediaType = "video/*";
        /* fix buggy eclipse syntax highlighter (because of above string) */ 
        mType.mug.properties.bindElement.properties.dataType = "binary";
        return mType;
    };

    that.mugTypeMaker.stdGeopoint = function () {
        var mType = formdesigner.util.getNewMugType(mugTypes.dataBindControlQuestion),
                mug;
        mType.typeSlug = "geopoint";
        mType.typeName = formdesigner.util.QUESTIONS[mType.typeSlug];
        mType.controlNodeAllowedChildren = false;
        mug = that.createMugFromMugType(mType);
        mType.mug = mug;
        mType.mug.properties.controlElement.properties.name = "Geopoint";
        mType.mug.properties.controlElement.properties.tagName = "input";
        mType.mug.properties.bindElement.properties.dataType = "geopoint";
        return mType;
    };

    that.mugTypeMaker.stdBarcode = function () {
        var mType = formdesigner.util.getNewMugType(mugTypes.dataBindControlQuestion),
                mug;
        mType.typeSlug = "barcode";
        mType.typeName = formdesigner.util.QUESTIONS[mType.typeSlug];
        mType.controlNodeAllowedChildren = false;
        mug = that.createMugFromMugType(mType);
        mType.mug = mug;
        mType.mug.properties.controlElement.properties.name = "Barcode";
        mType.mug.properties.controlElement.properties.tagName = "input";
        mType.mug.properties.bindElement.properties.dataType = "barcode";
        return mType;
    };

    that.mugTypeMaker.stdDate = function () {
        var mType = formdesigner.util.getNewMugType(mugTypes.dataBindControlQuestion),
                mug;
        mType.typeSlug = "date";
        mType.typeName = formdesigner.util.QUESTIONS[mType.typeSlug];
        mType.controlNodeAllowedChildren = false;
        mug = that.createMugFromMugType(mType);
        mType.mug = mug;
        mType.mug.properties.controlElement.properties.name = "Date";
        mType.mug.properties.controlElement.properties.tagName = "input";
        mType.mug.properties.bindElement.properties.dataType = "xsd:date";
        return mType;
    };

    that.mugTypeMaker.stdDateTime = function () {
        var mType = formdesigner.util.getNewMugType(mugTypes.dataBindControlQuestion),
                mug;
        mType.typeSlug = "datetime";
        mType.typeName = formdesigner.util.QUESTIONS[mType.typeSlug];
        mType.controlNodeAllowedChildren = false;
        mug = that.createMugFromMugType(mType);
        mType.mug = mug;
        mType.mug.properties.controlElement.properties.name = "DateTime";
        mType.mug.properties.controlElement.properties.tagName = "input";
        mType.mug.properties.bindElement.properties.dataType = "xsd:dateTime";
        return mType;
    };

    that.mugTypeMaker.stdLong = function () {
        var mType, mug;
        mType = formdesigner.model.mugTypeMaker.stdInt();
        mug = mType.mug;
        mType.typeSlug = "long";
        mType.typeName = formdesigner.util.QUESTIONS[mType.typeSlug];
        mType.mug.properties.controlElement.properties.name = "Long";
        mType.mug.properties.bindElement.properties.dataType = "xsd:long";
        return mType;
    };

    that.mugTypeMaker.stdDouble = function () {
        var mType, mug;
        mType = formdesigner.model.mugTypeMaker.stdInt();
        mug = mType.mug;
        mType.typeSlug = "double";
        mType.typeName = formdesigner.util.QUESTIONS[mType.typeSlug];
        mType.mug.properties.controlElement.properties.name = "Double";
        mType.mug.properties.bindElement.properties.dataType = "xsd:double";
        return mType;
    };


    that.mugTypeMaker.stdItem = function () {
        var mType = formdesigner.util.getNewMugType(mugTypes.controlOnly),
                mug,
                vResult,
                controlProps;

        mType.typeSlug = "item";
        mType.typeName = formdesigner.util.QUESTIONS[mType.typeSlug];
        mType.controlNodeAllowedChildren = false;


        controlProps = mType.properties.controlElement;
        controlProps.hintLabel.presence = 'notallowed';
        controlProps.hintItextID.presence = 'notallowed';
        
        controlProps.defaultValue.visibility = 'visible';
        controlProps.defaultValue.presence = 'required';
         
        mug = that.createMugFromMugType(mType);
        mType.mug = mug;
        mType.mug.properties.controlElement.properties.name = "Item";
        mType.mug.properties.controlElement.properties.tagName = "item";
        return mType;
    };

    that.mugTypeMaker.stdTrigger = function () {
        var mType = formdesigner.util.getNewMugType(mugTypes.dataBindControlQuestion),
                mug,
                vResult, controlProps, bindProps;

        mType.typeSlug = "trigger";
        mType.typeName = formdesigner.util.QUESTIONS[mType.typeSlug];
        mType.controlNodeAllowedChildren = false;
        mType.properties.bindElement.dataType.presence = 'notallowed';
        mType.properties.dataElement.dataValue.presence = 'optional';

        controlProps = mType.properties.controlElement;
        controlProps.hintLabel.presence = 'notallowed';
        controlProps.hintItextID.presence = 'notallowed';

        mug = that.createMugFromMugType(mType);
        mType.mug = mug;
        mType.mug.properties.controlElement.properties.name = "Trigger";
        mType.mug.properties.controlElement.properties.tagName = "trigger";
        return mType;
    };

    that.mugTypeMaker.stdMSelect = function () {
        var mType = formdesigner.util.getNewMugType(mugTypes.dataBindControlQuestion),
                allowedChildren,
                mug,
                vResult;
        mType.controlNodeCanHaveChildren = true;
        mType.typeSlug = "select";
        mType.typeName = formdesigner.util.QUESTIONS[mType.typeSlug];
        allowedChildren = ['item'];
        mType.controlNodeAllowedChildren = allowedChildren;
        mType.properties.bindElement.dataType.visibility = "hidden";
        mug = that.createMugFromMugType(mType);
        mType.mug = mug;
        mType.mug.properties.controlElement.properties.name = "Multi-Select";
        mType.mug.properties.controlElement.properties.tagName = "select";
        return mType;
    };

    that.mugTypeMaker.stdSelect = function () {
        var mType = formdesigner.model.mugTypeMaker.stdMSelect(), mug;
        mug = mType.mug;
        mType.typeSlug = "1select";
        mType.typeName = formdesigner.util.QUESTIONS[mType.typeSlug];
        mType.mug.properties.controlElement.properties.name = 'Single-Select';
        mType.mug.properties.controlElement.properties.tagName = "select1";
        return mType;
    };

    that.mugTypeMaker.stdGroup = function () {
        var mType = formdesigner.util.getNewMugType(mugTypes.dataBindControlQuestion),
                allowedChildren,
                mug,
                vResult;
        mType.controlNodeCanHaveChildren = true;
        mType.typeSlug = "group";
        mType.typeName = formdesigner.util.QUESTIONS[mType.typeSlug];
        allowedChildren = ['repeat', 'input', 'select', 'select1', 'group', 'trigger'];
        mType.controlNodeAllowedChildren = allowedChildren;
        mType.properties.bindElement.dataType.presence = "notallowed";
        mType.properties.controlElement.hintItextID.presence = "notallowed";
        mType.properties.controlElement.hintLabel.presence = "notallowed";
        mType.properties.controlElement.label.presence = "optional";
        mType.properties.controlElement.labelItextID.presence = "optional";
        mType.properties.dataElement.dataValue.presence = "notallowed";
        mug = that.createMugFromMugType(mType);
        mType.mug = mug;
        mType.mug.properties.controlElement.properties.name = "Group";
        mType.mug.properties.controlElement.properties.tagName = "group";
        
        vResult = mType.validateMug();
//        if(vResult.status !== 'pass'){
//            formdesigner.util.throwAndLogValidationError(vResult,mType,mType.mug);
//        }
        return mType;
    };

    that.mugTypeMaker.stdRepeat = function () {
        var mType;

        mType = formdesigner.model.mugTypeMaker.stdGroup();
        mType.properties.controlElement.repeat_count = {
            lstring: 'Repeat Count',
            visibility: 'visible',
            editable: 'w',
            presence: 'optional'
        };
        mType.properties.controlElement.no_add_remove = {
            lstring: 'Allow Repeat Add and Remove?',
            visibility: 'visible',
            editable: 'w',
            presence: 'optional',
            uiType: 'checkbox'
        };
        mType.typeSlug = "repeat";
        mType.typeName = formdesigner.util.QUESTIONS[mType.typeSlug];
        mType.mug.properties.controlElement.properties.name = "Repeat";
        mType.mug.properties.controlElement.properties.tagName = "repeat";

        return mType;
    };



    /**
     * A regular tree (with any amount of leafs per node)
     * @param tType - is this a DataElement tree or a controlElement tree (use 'data' or 'control' for this argument, respectively)
     * tType defaults to 'data'
     */
    var Tree = function (tType) {
        var that = {}, rootNode, treeType = tType;
        if (!treeType) {
            treeType = 'data';
        }

        /**
         * Children is a list of objects.
         * @param children - optional
         * @param value - that value object that this node should contain (should be a MugType)
         */
        var Node = function (Children, value) {
            var that = {}, isRootNode = false, nodeValue, children = Children;

            var init = function (nChildren, val) {
                if (!val) {
                    throw 'Cannot create a node without specifying a value object for the node!';
                }
                children = nChildren || [];
                nodeValue = val;
            }(children, value);

            that.getChildren = function () {
                return children;
            };

            that.getValue = function () {
                return nodeValue;
            };

            that.setValue = function (val) {
                nodeValue = val;
            }

            /**
             * DOES NOT CHECK TO SEE IF NODE IS IN TREE ALREADY!
             * Adds child to END of children!
             */
            that.addChild = function (node) {
                if (!children) {
                    children = [];
                }
                children.push(node);
            };

            /**
             * Insert child at the given index (0 means first)
             * if index > children.length, will insert at end.
             * -ve index will result in child being added to first of children list.
             */
            that.insertChild = function (node, index) {
                if (node === null) {
                    return null;
                }

                if (index < 0) {
                    index = 0;
                }

                children.splice(index, 0, node);
            };

            /**
             * Given a mugType, finds the node that the mugType belongs to.
             * if it is not the current node, will recursively look through 
             * children node (depth first search)
             */
            that.getNodeFromMugType = function (MugType) {
                if (MugType === null) {
                    return null;
                }
                var retVal, thisVal;
                thisVal = this.getValue();
                if (thisVal === MugType) {
                    return this;
                } else {
                    for (var i in children) {
                        if (children.hasOwnProperty(i)) {
                            retVal = children[i].getNodeFromMugType(MugType);
                            if (retVal) {
                                return retVal;
                            }
                        }
                    }
                }
                return null; //we haven't found what we're looking for
            };

            /**
             * Given a ufid, finds the mugType that it belongs to.
             * if it is not the current node, will recursively look through children node (depth first search)
             *
             * Returns null if not found.
             */
            that.getMugTypeFromUFID = function (ufid) {
                if (!ufid) {
                    return null;
                }
                var retVal, thisUfid;
                if (this.getValue() !== ' ') {
                    thisUfid = this.getValue().ufid || '';
                } else {
                    thisUfid = '';
                }

                if (thisUfid === ufid) {
                    return this.getValue();
                } else {
                    for (var i in children) {
                        if (children.hasOwnProperty(i)) {
                            retVal = children[i].getMugTypeFromUFID(ufid);
                            if (retVal) {
                                return retVal;
                            }
                        }
                    }
                }
                return null; //we haven't found what we're looking for
            };

            that.removeChild = function (node) {
                if (!node) {
                    throw 'Null child specified! Cannot remove \'null\' from child list';
                }
                var childIdx = children.indexOf(node);
                if (childIdx !== -1) { //if arg node is a member of the children list
                    children.splice(childIdx, 1); //remove it
                }

                return node;
            };

            /**
             * Finds the parentNode of the specified node (recursively going through the tree/children of this node)
             * Returns the parent if found, else null.
             */
            that.findParentNode = function (node) {
                if (!node) {
                    throw {name: "NoNodeFound",
                           message: "No node specified, can't find 'null' in tree!"};
                }
                var i, parent = null;
                if (!children || children.length === 0) {
                    return null;
                }
                if (children.indexOf(node) !== -1) {
                    return this;
                }

                for (i in children) {
                    if (children.hasOwnProperty(i)) {
                        parent = children[i].findParentNode(node);
                        if (parent !== null) {
                            return parent;
                        }
                    }
                }
                return parent;
            };

            /**
             * An ID used during prettyPrinting of the Node. (a human readable value for the node)
             */
            that.getID = function () {
                var id;
                if (this.isRootNode) {
                    id = formdesigner.controller.form.formID;
                    if (id) {
                        return id;
                    } else {
                        return 'RootNode';
                    }
                }
                if (!this.getValue() || typeof this.getValue().validateMug !== 'function') {
                    return 'NodeWithNoValue!';
                }
                if (treeType === 'data') {
                    return this.getValue().mug.getDataElementID();
                } else if (treeType === 'control') {
                    return formdesigner.util.getMugDisplayName(this.getValue());
                } else {
                    throw 'Tree does not have a specified treeType! Default is "data" so must have been forcibly removed!';
                }
            };

            /**
             * Get all children MUG TYPES of this node (not recursive, only the top level).
             * Return a list of MugType objects, or empty list for no children.
             */
            that.getChildrenMugTypes = function () {
                var i, retList = [];
                for (i in children) {
                    if (children.hasOwnProperty(i)) {
                        retList.push(children[i].getValue());
                    }
                }
                return retList;
            };


            that.toString = function () {
                return this.getID();
            };

            that.prettyPrint = function () {
                var arr = [], i;
                for (i in children) {
                    if (children.hasOwnProperty(i)) {
                        arr.push(children[i].prettyPrint());
                    }
                }
                if (!children || children.length === 0) {
                    return this.getID();
                } else {
                    return '' + this.getID() + '[' + arr + ']';
                }
            };

            /**
             * calls the given function on each node (the node
             * is given as the only argument to the given function)
             * and appends the result (if any) to a flat list
             * (the store argument) which is then returned
             * @param nodeFunc
             * @param store
             */
            that.treeMap = function (nodeFunc, store, afterChildFunc) {
                var result, child;
                result = nodeFunc(this); //call on self
                if(result){
                    store.push(result);
                }
                for(child in this.getChildren()){
                    if(this.getChildren().hasOwnProperty(child)){
                        this.getChildren()[child].treeMap(nodeFunc, store, afterChildFunc); //have each children also perform the func
                    }
                }
                if(afterChildFunc){
                    afterChildFunc(this, result);
                }
                return store; //return the results
            };

            /**
             * See docs @ Tree.validateTree()
             */
            var validateTree = function () {
                var thisResult, thisMT, i, childResult;
                if(!this.getValue()){
                    throw 'Tree contains node with no values!'
                }
                thisMT = this.getValue();
                thisResult = thisMT.validateMug();
                if(thisResult.status === 'fail'){
                    return false;
                }

                for (i in this.getChildren()) {
                    if (this.getChildren().hasOwnProperty(i)) {
                        childResult = this.getChildren()[i].validateTree();
                        if(!childResult){
                            return false;
                        }
                    }
                }

                //If we got this far, everything checks out.
                return true;


            }
            that.validateTree = validateTree;

            return that;
        };

        var init = function (type) {
            rootNode = new Node(null, ' ');
            rootNode.isRootNode = true;
            treeType = type || 'data';
        }(treeType);
        that.rootNode = rootNode;

        /** Private Function
         * Adds a node to the top level (as a child of the abstract root node)
         *
         * @param parentNode - the parent to which the specified node should be added
         * if null is given, the node will be added to the top level of the tree (as a child
         * of the abstract rootNode).
         * @param node - the specified node to be added to the tree.
         */
        var addNode = function (node, parentNode) {
            if (parentNode) {
                parentNode.addChild(node);
            } else {
                rootNode.addChild(node);
            }
        };

        that.getParentNode = function (node) {
            if (this.rootNode === node) { //special case:
                return this.rootNode;
            } else { //regular case
                return this.rootNode.findParentNode(node);
            }
        };

        /**
         * Given a mugType, finds the node that the mugType belongs to (in this tree).
         * Will return null if nothing is found.
         */
        that.getNodeFromMugType = function (MugType) {
            return rootNode.getNodeFromMugType(MugType);
        };

        that.getParentMugType = function (MugType) {
            var node = this.getNodeFromMugType(MugType);
            if (!node) {
                return null;
            }
            var pNode = that.getParentNode(node),
                    pMT = pNode.getValue();
            return (pMT === ' ') ? null : pMT;
        };

        /**
         * Removes a node (and all it's children) from the tree (regardless of where it is located in the
         * tree) and returns it.
         *
         * If no such node is found in the tree (or node is null/undefined)
         * null is returned.
         */
        var removeNodeFromTree = function (node) {
            if (!node) {
                return null;
            }
            if (!that.getNodeFromMugType(node.getValue())) {
                return null;
            } //node not in tree
            var parent = that.getParentNode(node);
            if (parent) {
                parent.removeChild(node);
                return node;
            } else {
                return null;
            }
        };

        /**
         * Insert a MugType as a child to the node containing parentMugType.
         *
         * Will MOVE the mugType to the new location in the tree if it is already present!
         * @param mugType - the MT to be inserted into the Tree
         * @param position - position relative to the refMugType. Can be 'null', 'before', 'after' or 'into'
         * @param refMugType - reference MT.
         *
         * if refMugType is null, will default to the last child of the root node.
         * if position is null, will default to 'after'.  If 'into' is specified, mugType will be inserted
         * as a ('after') child of the refMugType.
         *
         * If an invalid move is specified, no operation will occur.
         */
        that.insertMugType = function (mugType, position, refMugType) {
            var refNode, refNodeSiblings, refNodeIndex, refNodeParent, node;
            
            if (!formdesigner.controller.checkMoveOp(mugType, position, refMugType, treeType)) {
                throw { 
                    name: "IllegalMove",
                    message: 'Illegal Tree move requested! Doing nothing instead.',
                    mugType: mugType,
                    position: position,
                    refMugType: refMugType 
                };
            }

            if (position !== null && typeof position !== 'string') {
                throw "position argument must be a string or null! Can be 'after', 'before' or 'into'";
            }
            if (!position) {
                position = 'after';
            }

            if (!refMugType) {
                refNode = rootNode;
                position = 'into';
            } else {
                refNode = this.getNodeFromMugType(refMugType);
            }

            //remove it from tree if it already exists
            node = removeNodeFromTree(this.getNodeFromMugType(mugType)); 
            if (!node) {
                node = new Node(null, mugType);
            }
            
            if (position !== 'into') {
                refNodeParent = that.getParentNode(refNode);
                refNodeSiblings = refNodeParent.getChildren();
                refNodeIndex = refNodeSiblings.indexOf(refNode);
            }

            switch (position) {
                case 'before':
                    refNodeParent.insertChild(node, refNodeIndex);
                    break;
                case 'after':
                    refNodeParent.insertChild(node, refNodeIndex + 1);
                    break;
                case 'into':
                    refNode.addChild(node);
                    break;
                case 'first':
                    refNode.insertChild(node, 0);
                    break;
                case 'last':
                    refNode.insertChild(node, refNodeSiblings.length + 1);
                    break;
                default:
                    throw "in insertMugType() position argument MUST be null, 'before', 'after', 'into', 'first' or 'last'.  Argument was: " + position;
            }
        };

        /**
         * Returns a list of nodes that are in the top level of this tree (i.e. not the abstract rootNode but it's children)
         */
        var getAllNodes = function () {
            return rootNode.getChildren();
        };

        /**
         * returns the absolute path, in the form of a string separated by slashes ('/nodeID/otherNodeID/finalNodeID'),
         * the nodeID's are those given by the Mugs (i.e. the node value objects) according to whether this tree is a
         * 'data' (DataElement) tree or a 'bind' (BindElement) tree.
         *
         * @param nodeOrMugType - can be a tree Node or a MugType that is a member of this tree (via a Node)
         */
        that.getAbsolutePath = function (mugType) {
            var node, output, nodeParent;
            if (typeof mugType.validateMug === 'function') { //a loose way of checking that it's a MugType...
                node = this.getNodeFromMugType(mugType);
            } else {
                throw 'getAbsolutePath argument must be a MugType!';
            }
            if (!node) {
//                console.log('Cant find path of MugType that is not present in the Tree!');
                return null;
            }
            nodeParent = this.getParentNode(node);
            output = '/' + node.getID();

            while (nodeParent) {
                output = '/' + nodeParent.getID() + output;
                if(nodeParent.isRootNode){
                    break;
                }
                nodeParent = this.getParentNode(nodeParent);

            }
                        
            return output;

        };

        that.printTree = function (toConsole) {
            var t = rootNode.prettyPrint();

            return t;
        };

        /**
         * Removes the specified MugType from the tree. If it isn't in the tree
         * does nothing.  Does nothing if null is specified
         *
         * If the MugType is successfully removed, returns that MugType.
         */
        that.removeMugType = function (MugType) {
            var node = this.getNodeFromMugType(MugType);
            if (!MugType || !node) {
                return;
            }
            removeNodeFromTree(node);
            return node;
        };

        /**
         * Given a UFID searches through the tree for the corresponding MugType and returns it.
         * @param ufid of a mug
         */
        that.getMugTypeFromUFID = function (ufid) {
            return rootNode.getMugTypeFromUFID(ufid);
        };

        /**
         * Returns all the children MugTypes (as a list) of the
         * root node in the tree.
         */
        that.getRootChildren = function () {
            return rootNode.getChildrenMugTypes();
        };

        /**
         * Method for testing use only.  You should never need this information beyond unit tests!
         *
         * Gets the ID used to identify a node (used during Tree prettyPrinting)
         */
        that._getMugTypeNodeID = function (MugType) {
            if (!MugType) {
                return null;
            }
            return this.getNodeFromMugType(MugType).getID();
        };

        /**
         * Method for testing use only.  You should never need this information beyond unit tests!
         *
         * Gets the ID string used to identify the rootNode in the tree. (used during Tree prettyPrinting)
         */
        that._getRootNodeID = function () {
            return rootNode.getID();
        };

        /**
         * Performs the given func on each
         * node of the tree (the Node is given as the only argument to the function)
         * and returns the result as a list.
         * @param func - a function called on each node, the node is the only argument
         * @param afterChildFunc - a function called after the above function is called on each child of the current node.
         */
        that.treeMap = function (func, afterChildFunc) {
            return rootNode.treeMap(func, [], afterChildFunc);
        };

        /**
         * Looks through all the nodes in the tree
         * and runs ValidateMugType on each.
         * If any fail (i.e. result === 'fail')
         * will return false, else return true.
         */
        var isTreeValid = function() {
            var rChildren = rootNode.getChildren(),
                i, retVal;
            for (i in rChildren){
                if(rChildren.hasOwnProperty(i)){
                    retVal = rChildren[i].validateTree();
                    if(!retVal){
                        return false;
                    }
                }
            }
            return true;
        }
        that.isTreeValid = isTreeValid;


        that.getRootNode = function () {
            return rootNode;
        }

        return that;
    };
    that.Tree = Tree;
    
    var InstanceMetadata = function (attributes) {
        var that = {};
        that.attributes = attributes;
        return that;
    };
    that.InstanceMetadata = InstanceMetadata;
    
    var FormError = function (options) {
        var that = {};
        that.message = options.message;
        // the key is how uniqueness is determined
        that.key = options.key; 
        that.level = options.level || "form-warning";
        that.options = options;
        
        that.isMatch = function (other) {
            if (this.key && other.key) {
                return this.key === other.key;
            }
            return false;
        };
        
        return that;
    };
    that.FormError = FormError;
    
    var Form = function () {
        var that = {}, dataTree, controlTree;

        var init = (function () {
            that.formName = 'New Form';
            that.formID = 'data';
            that.dataTree = dataTree = new Tree('data');
            that.controlTree = controlTree = new Tree('control');
            that.instanceMetadata = [InstanceMetadata({})];
            that.errors = [];
        })();

        /**
         * Loops through the data and the control trees and picks out all the unique bind elements.
         * Returns a list of MugTypes
         */
        that.getBindList = function(){
            var bList = [],
                dataTree,controlTree,dBindList,cBindList,i,
                getBind = function(node){ //the function we will pass to treeMap
                    if(!node.getValue() || node.isRootNode){
                        return null;
                    }
                    var MT = node.getValue(),
                            M = MT.mug,
                            bind;
                    if(!MT.properties.bindElement){
                        return null;
                    }else{
                        bind = MT;
                        return bind;
                    }
                };

            dataTree = this.dataTree;
            controlTree = this.controlTree;
            dBindList = dataTree.treeMap(getBind);
            cBindList = controlTree.treeMap(getBind);

            //compare results, grab uniques
            for(i in dBindList){
                if(dBindList.hasOwnProperty(i)){
                    bList.push(dBindList[i]);
                }
            }

            for(i in cBindList){
                if(cBindList.hasOwnProperty(i)){
                    if(bList.indexOf(cBindList[i]) === -1){
                        bList.push(cBindList[i]); //grab only anything that hasn't shown up in the dBindList
                    }
                }
            }
            return bList;
        }

        /**
         * Searches through BOTH trees and returns
         * a MT if found (null if nothing found)
         */
        var getMugTypeByUFID = function (ufid) {
            var MT = dataTree.getMugTypeFromUFID(ufid);
            if(!MT) {
                MT = controlTree.getMugTypeFromUFID(ufid);
            }

            return MT;
        };
        that.getMugTypeByUFID = getMugTypeByUFID;

        var getInvalidMugTypes = function () {
            var MTListC, MTListD, result, controlTree, dataTree,
                mapFunc = function (node) {
                    if (node.isRootNode) {
                        return;
                    }
                    var MT = node.getValue(),
                        validationResult = MT.validateMug();

                    if(validationResult.status !== 'pass'){
                        return MT;
                    }else{
                        return null;
                    }
                }

            dataTree = this.dataTree;
            controlTree = this.controlTree;
            MTListC = controlTree.treeMap(mapFunc);
            MTListD = dataTree.treeMap(mapFunc);
            result = formdesigner.util.mergeArray(MTListC, MTListD);

            return result;
        }
        that.getInvalidMugTypes = getInvalidMugTypes;

        /**
         * Goes through both trees and picks out all the invalid
         * MugTypes and returns a dictionary with the MT.ufid as the key
         * and the validation object as the value
         */
        var getInvalidMugTypeUFIDs = function () {
            var badMTs = this.getInvalidMugTypes(), result = {}, i;
            for (i in badMTs){
                if(badMTs.hasOwnProperty(i)){
                    result[badMTs[i].ufid] = badMTs[i].validateMug();
                }
            }
            return result;
        }
        that.getInvalidMugTypeUFIDs = getInvalidMugTypeUFIDs;
        
        that.updateError = function (errObj, options) {
            options = options || {};
            if (!errObj.key) {
                that.errors.push(errObj);
            }
            else {
                var removed = null;
                for (var i = 0; i < that.errors.length; i++) {
                    if (errObj.isMatch(that.errors[i])) {
                        removed = that.errors.splice(i, 1, errObj);
                    }
                }
                if (!removed) {
                    that.errors.push(errObj);
                }
            }
            if (options.updateUI) {
                formdesigner.ui.resetMessages(that.errors);
            }
            
        };
        
        that.clearErrors = function (type, options) {
            options = options || {};
            for (var i = 0; i < that.errors.length; i++) {
                that.errors = that.errors.filter(function (err) {
                    return err.level !== type;
                });
            }
            if (options.updateUI) {
                formdesigner.ui.resetMessages(that.errors);
            }
        };
        
        
        that.clearError = function (errObj, options) {
            options = options || {};
            var removed = null;
            for (var i = 0; i < that.errors.length; i++) {
                if (errObj.isMatch(that.errors[i])) {
                    removed = that.errors.splice(i, 1);
                    break;
                }
            }
            if (removed && options.updateUI) {
                formdesigner.ui.resetMessages(that.errors);
            }
        };
        
        /**
         * Generates an XML Xform and returns it as a string.
         */
        var createXForm = function () {
            var createDataBlock = function () {
                // use dataTree.treeMap(func,listStore,afterChildfunc)
                // create func that opens + creates the data tag, that can be recursively called on all children
                // create afterChildfunc which closes the data tag
                function mapFunc (node) {
                    var xw = formdesigner.controller.XMLWriter,
                        defaultVal, extraXMLNS, keyAttr,
                        MT = node.getValue();

                    xw.writeStartElement(node.getID());
                    
                    if (node.isRootNode) {
                        createModelHeader();
                    } else {
                        // Write any custom attributes first
	                    for (var k in MT.mug.properties.dataElement.properties._rawAttributes) {
	                        if (MT.mug.properties.dataElement.properties._rawAttributes.hasOwnProperty(k)) {
	                            xw.writeAttributeStringSafe(k, MT.mug.properties.dataElement.properties._rawAttributes[k]);
	                        }
	                    }
	                    
	                    if (MT.mug.properties.dataElement.properties.dataValue){
	                        defaultVal = MT.mug.properties.dataElement.properties.dataValue;
	                        xw.writeString(defaultVal);
	                    }
	                    if (MT.mug.properties.dataElement.properties.keyAttr){
	                        keyAttr = MT.mug.properties.dataElement.properties.keyAttr;
	                        xw.writeAttributeStringSafe("key", keyAttr);
	                    }
	                    if (MT.mug.properties.dataElement.properties.xmlnsAttr){
	                        extraXMLNS = MT.mug.properties.dataElement.properties.xmlnsAttr;
	                        xw.writeAttributeStringSafe("xmlns", extraXMLNS);
	                    }
	                    if (MT.typeName === "Repeat"){
	                        xw.writeAttributeStringSafe("jr:template","");
	                    }
                    }
                }

                function afterFunc (node) {
                    var xw = formdesigner.controller.XMLWriter;
                    xw.writeEndElement();
                    //data elements only require one close element call with nothing else fancy.
                }

                dataTree.treeMap(mapFunc, afterFunc);
            };

            var createBindList = function () {
                var xw = formdesigner.controller.XMLWriter,
                    bList = formdesigner.controller.form.getBindList(),
                    MT,
                        //vars populated by populateVariables()
                        bEl,cons,consMsg,nodeset,type,relevant,required,calc,preld,preldParams,
                    i, attrs, j;



                function populateVariables (MT){
                    bEl = MT.mug.properties.bindElement;
                    if (bEl) {
                        return {
                            nodeset: dataTree.getAbsolutePath(MT),
                            'type': bEl.properties.dataType,
                            constraint: bEl.properties.constraintAttr,
                            constraintMsg: bEl.properties.constraintMsgAttr,
                            constraintMsgItextID: bEl.properties.constraintMsgItextID.id,
                            relevant: bEl.properties.relevantAttr,
                            required: formdesigner.util.createXPathBoolFromJS(bEl.properties.requiredAttr),
                            calculate: bEl.properties.calculateAttr,
                            preload: bEl.properties.preload,
                            preloadParams: bEl.properties.preloadParams
                        }
                    } else {
                        return null;
                    }
                }

                for (i in bList) {
                    if(bList.hasOwnProperty(i)){
                        MT = bList[i];
                        attrs = populateVariables(MT);
                        if(attrs.nodeset){
                            xw.writeStartElement('bind');
                        }
                        for (j in attrs) { //for each populated property
                            if(attrs.hasOwnProperty(j)){
                                if(attrs[j]){ //if property has a useful bind attribute value
                                    if (j === "constraintMsg"){
                                        xw.writeAttributeStringSafe("jr:constraintMsg",attrs[j]); //write it
                                    } else if (j === "constraintMsgItextID") {
                                        xw.writeAttributeStringSafe("jr:constraintMsg",  "jr:itext('" + attrs[j] + "')")
                                    } else if (j === "preload") {
                                        xw.writeAttributeStringSafe("jr:preload", attrs[j]);
                                    } else if (j === "preloadParams") {
                                        xw.writeAttributeStringSafe("jr:preloadParams", attrs[j]);
                                    } else {
                                        xw.writeAttributeStringSafe(j,attrs[j]);
                                    } //write it
                                }
                            }
                        }
                        if(attrs.nodeset) {
                            xw.writeEndElement();
                        }

                    }
                }
            }

            var createControlBlock = function () {
                var mapFunc, afterFunc;

                function mapFunc(node) {
                    if(node.isRootNode) { //skip
                        return;
                    }

                    var mugType = node.getValue(),
                        cProps = mugType.mug.properties.controlElement.properties,
                        label,
                        xmlWriter = formdesigner.controller.XMLWriter,
                        hasItext,
                        isItextOptional;

                    /**
                     * @param tagName
                     * @param elLabel - dictionary: {ref: 'itext ref string', defText: 'default label text'} both are optional
                     */
                    function createOpenControlTag(tagName,elLabel){
                        tagName = tagName.toLowerCase();
                        var isGroupOrRepeat = (tagName === 'group' || tagName === 'repeat');
                        var isODKMedia = (tagName === 'upload');
                        /**
                         * Creates the label tag inside of a control Element in the xform
                         */
                        function createLabel() {
                            if (elLabel.ref || elLabel.defText) {
                                xmlWriter.writeStartElement('label');
                                if (elLabel.ref) {
                                    xmlWriter.writeAttributeStringSafe('ref',elLabel.ref);
                                }
                                if (elLabel.defText) {
                                    xmlWriter.writeString(elLabel.defText);
                                }
                                xmlWriter.writeEndElement(); //close Label tag;
                            }
                        }

                        //////Special logic block to make sure the label ends up in the right place
                        if (isGroupOrRepeat) {
                            xmlWriter.writeStartElement('group');
                            createLabel();
                            if (tagName === 'repeat') {
                                xmlWriter.writeStartElement('repeat');
                            }
                        } else {
                            xmlWriter.writeStartElement(tagName);
                        }
                        if (tagName !== 'group' && tagName !== 'repeat') {
                            createLabel();
                        }
                        //////////////////////////////////////////////////////////////////////////
                        if (tagName === 'item' && cProps.defaultValue) {
                            //do a value tag for an item MugType
                            xmlWriter.writeStartElement('value');
                            xmlWriter.writeString(cProps.defaultValue);
                            xmlWriter.writeEndElement();
                        }
                        
                        // Write any custom attributes first
                        for (var k in cProps._rawAttributes) {
                            if (cProps._rawAttributes.hasOwnProperty(k)) {
                                xmlWriter.writeAttributeStringSafe(k, cProps._rawAttributes[k]);
                            }
                        }
                        
                        ///////////////////////////////////////////////////////////////////////////
                        ///Set the nodeset/ref attribute correctly
                        if (tagName !== 'item') {
                            var attr, absPath;
                            if (tagName === 'repeat') {
                                attr = 'nodeset';
                            } else {
                                attr = 'ref';
                            }
                            absPath = formdesigner.controller.form.dataTree.getAbsolutePath(mugType);
                            xmlWriter.writeAttributeStringSafe(attr, absPath);
                        }
                        //////////////////////////////////////////////////////////////////////
                        ///Set other relevant attributes

                        if (tagName === 'repeat') {
                            var r_count = cProps.repeat_count,
                                r_noaddrem = cProps.no_add_remove;

                            //make r_noaddrem an XPath bool
                            r_noaddrem = formdesigner.util.createXPathBoolFromJS(r_noaddrem);

                            if (r_count) {
                                xmlWriter.writeAttributeStringSafe("jr:count",r_count);
                            }
                            if (r_noaddrem) {
                                xmlWriter.writeAttributeStringSafe("jr:noAddRemove", r_noaddrem);
                            }
                        } else if (isODKMedia) {
                            var mediaType = cProps.mediaType;
                            if (mediaType) {
                                xmlWriter.writeAttributeStringSafe("mediatype", mediaType);
                            }
                        }
                        //////////////////////////////////////////////////////////////////////
                        //Do hint label
                        if( tagName !== 'item' && tagName !== 'repeat'){
                            if(cProps.hintLabel || (cProps.hintItextID && cProps.hintItextID.id)) {
                                xmlWriter.writeStartElement('hint');
                                if(cProps.hintLabel){
                                    xmlWriter.writeString(cProps.hintLabel);
                                }
                                if(cProps.hintItextID.id){
                                    var ref = "jr:itext('" + cProps.hintItextID.id + "')";
                                    xmlWriter.writeAttributeStringSafe('ref',ref);
                                }
                                xmlWriter.writeEndElement();
                            }
                        }
                        ///////////////////////////////////////
                    }


                    //create the label object (for createOpenControlTag())
                    if (cProps.label) {
                        label = {};
                        label.defText = cProps.label;
                    }
                    if (cProps.labelItextID) {
                        if (!label) {
                            label = {};
                        }
                        
                        
                        label.ref = "jr:itext('" + cProps.labelItextID.id + "')";
                        isItextOptional = mugType.properties.controlElement.labelItextID.presence == 'optional'; //iID is optional so by extension Itext is optional.
                        if (cProps.labelItextID.isEmpty() && isItextOptional) {
                            label.ref = '';
                        }
                    }
                    ////////////

                    createOpenControlTag(cProps.tagName, label);

                }


                function afterFunc(node) {
                    if (node.isRootNode) {
                        return;
                    }

                    var xmlWriter = formdesigner.controller.XMLWriter,
                        mugType = node.getValue(),
                        tagName = mugType.mug.properties.controlElement.properties.tagName;
                    //finish off
                    xmlWriter.writeEndElement(); //close control tag.
                    if(tagName === 'repeat'){
                        xmlWriter.writeEndElement(); //special case where we have to close the repeat as well as the group tag.
                    }

                }

                controlTree.treeMap(mapFunc, afterFunc);
            };

            var createITextBlock = function () {
                var xmlWriter = formdesigner.controller.XMLWriter, lang, id,
                        langData, val, formData, form, i, allLangKeys, question, form;
                
                // here are the rules that govern itext
                // 0. iText items which aren't referenced by any questions are 
                // cleared from the form.
                // 1. iText nodes for which values in _all_ languages are empty/blank 
                // will be removed entirely from the form.
                // 2. iText nodes that have a single value in _one_ language 
                // but not others, will automatically have that value copied 
                // into the remaining languages. TBD: there should be a UI to 
                // disable this feature
                // 3. iText nodes that have multiple values in multiple languages 
                // will be properly set as such.
                // 4. duplicate itext ids will be automatically updated to create
                // non-duplicates
                
                formdesigner.controller.removeCruftyItext();
                var Itext = formdesigner.model.Itext;
                var languages = Itext.getLanguages();
                var allItems = Itext.getNonEmptyItems();
                var item, forms, form;
                if (languages.length > 0) {
                    xmlWriter.writeStartElement("itext");
                    for (var i = 0; i < languages.length; i++) {
                        lang = languages[i];
                        xmlWriter.writeStartElement("translation");
                        xmlWriter.writeAttributeStringSafe("lang", lang);
                        if (Itext.getDefaultLanguage() === lang) {
                            xmlWriter.writeAttributeStringSafe("default", '');
                        }
                        for (var j = 0; j < allItems.length; j++) {
                            item = allItems[j];
                            xmlWriter.writeStartElement("text");
                            xmlWriter.writeAttributeStringSafe("id", item.id);
                            forms = item.getForms();
                            for (var k = 0; k < forms.length; k++) {
                                form = forms[k];
                                val = form.getValueOrDefault(lang);
                                xmlWriter.writeStartElement("value");
                                if(form.name !== "default") {
                                    xmlWriter.writeAttributeStringSafe('form', form.name);
                                }
                                xmlWriter.writeString(val);
                                xmlWriter.writeEndElement();    
                            }
                            xmlWriter.writeEndElement();
                        }
                        xmlWriter.writeEndElement();
                    }
                    xmlWriter.writeEndElement();
                }

                //done with Itext block generation.
            };

            var createModelHeader = function () {
                var xw = formdesigner.controller.XMLWriter,
                        uuid, uiVersion, version, formName, jrm;
                //assume we're currently pointed at the opening date block tag
                //e.g. <model><instance><data> <--- we're at <data> now.

                jrm = formdesigner.formJRM;
                if(!jrm) {
                    jrm = "http://dev.commcarehq.org/jr/xforms";
                }

                uuid = formdesigner.formUuid; //gets set at parse time/by UI
                if(!uuid) {
                    uuid = "http://openrosa.org/formdesigner/" + formdesigner.util.generate_xmlns_uuid();
                }

                uiVersion = formdesigner.formUIVersion; //gets set at parse time/by UI
                if(!uiVersion) {
                    uiVersion = 1;
                }

                version = formdesigner.formVersion; //gets set at parse time/by UI
                if(!version) {
                    version = 1;
                }

                formName = formdesigner.controller.form.formName; //gets set at parse time/by UI
                if(!formName) {
                    formName = "New Form";
                }

                xw.writeAttributeStringSafe("xmlns:jrm",jrm);
                xw.writeAttributeStringSafe("xmlns", uuid);
                xw.writeAttributeStringSafe("uiVersion", uiVersion);
                xw.writeAttributeStringSafe("version", version);
                xw.writeAttributeStringSafe("name", formName);
            };

            function html_tag_boilerplate () {
                var xw = formdesigner.controller.XMLWriter;
                xw.writeAttributeStringSafe( "xmlns:h", "http://www.w3.org/1999/xhtml" );
                xw.writeAttributeStringSafe( "xmlns:orx", "http://openrosa.org/jr/xforms" );
                xw.writeAttributeStringSafe( "xmlns", "http://www.w3.org/2002/xforms" );
                xw.writeAttributeStringSafe( "xmlns:xsd", "http://www.w3.org/2001/XMLSchema" );
                xw.writeAttributeStringSafe( "xmlns:jr", "http://openrosa.org/javarosa" );
            }

            var _writeInstanceAttributes = function (writer, instanceMetadata) {
                for (var attrId in instanceMetadata.attributes) {
                    if (instanceMetadata.attributes.hasOwnProperty(attrId)) {
                        writer.writeAttributeStringSafe(attrId, instanceMetadata.attributes[attrId]);
                    }
                }
            };
            
            var _writeInstance = function (writer, instanceMetadata) {
                writer.writeStartElement('instance');
                _writeInstanceAttributes(writer, instanceMetadata);
                writer.writeEndElement(); 
            };
            
            var generateForm = function () {
                var docString;
                // first normalize the itext ids so we don't have any
                // duplicates
                formdesigner.model.Itext.deduplicateIds();
                
                formdesigner.controller.initXMLWriter();
                var xw = formdesigner.controller.XMLWriter;

                xw.writeStartDocument();
                //Generate header boilerplate up to instance level
                xw.writeStartElement('h:html');
                html_tag_boilerplate();
                xw.writeStartElement('h:head');
                xw.writeStartElement('h:title');
                xw.writeString(formdesigner.controller.form.formName);
                xw.writeEndElement();       //CLOSE TITLE

                ////////////MODEL///////////////////
                xw.writeStartElement('model');
                xw.writeStartElement('instance');
                _writeInstanceAttributes(xw, formdesigner.controller.form.instanceMetadata[0]);
                
                createDataBlock();
                xw.writeEndElement(); //CLOSE MAIN INSTANCE
                
                // other instances
                for (var i = 1; i < formdesigner.controller.form.instanceMetadata.length; i++) {
                    _writeInstance(xw, formdesigner.controller.form.instanceMetadata[i]);
                }
                
                /////////////////BINDS /////////////////
                createBindList();
                ///////////////////////////////////////
                
                //////////ITEXT //////////////////////
                createITextBlock();
                ////////////////////////////////////
                
                xw.writeEndElement(); //CLOSE MODEL
                ///////////////////////////////////
                xw.writeEndElement(); //CLOSE HEAD

                xw.writeStartElement('h:body');
                /////////////CONTROL BLOCK//////////////
                createControlBlock();
                ////////////////////////////////////////
                xw.writeEndElement(); //CLOSE BODY
                xw.writeEndElement(); //CLOSE HTML

                xw.writeEndDocument(); //CLOSE DOCUMENT
                docString = xw.flush();

                return docString;
            };
            var xformString = generateForm();
            this.fire('xform-created');
            return xformString;
        };
        that.createXForm = createXForm;

        /**
         * Goes through all mugs (in data and control tree and bindList)
         * to determine if all mugs are Valid and ok for form creation.
         */
        var isFormValid = function () {
            var i, bList;
            if (!this.dataTree.isTreeValid()) {
                return false;
            }
            if (!this.controlTree.isTreeValid()) {
                return false;
            }
            bList = this.getBindList();
            for (i in bList) {
                if(bList.hasOwnProperty(i)){
                    if (bList[i].validateMug.status === 'fail') {
                       return false;
                    }
                }
            }

            return true;
        };
        that.isFormValid = isFormValid;

        /**
         * Searches through the dataTree for a mugType
         * that matches the given nodeID (e.g. mugType.mug.properties.dataElement.properties.nodeID)
         *
         * WARNING:
         * Some MugTypes (such as for example 'Items' or 'Triggers' or certain 'Group's may not have
         * any nodeID at all (i.e. no bind element and no data element)
         * in such cases... other methods need to be used as this method will not find a match.
         * @param nodeID
         * @param treeType - either 'data' or 'control
         */
        var getMugTypeByIDFromTree = function (nodeID, treeType) {
            var mapFunc = function (node) {
                if(node.isRootNode){
                    return;
                }
                var mt = node.getValue(),
                    thisDataNodeID, thisBindNodeID;
                if (mt.properties.dataElement && mt.mug.properties.dataElement) {
                    thisDataNodeID = mt.mug.properties.dataElement.properties.nodeID;
                }
                if (mt.properties.bindElement && mt.mug.properties.bindElement){
                    thisBindNodeID = mt.mug.properties.bindElement.properties.nodeID;
                }
                if (!thisDataNodeID && !thisBindNodeID){
                    return; //this MT just has no nodeID :/
                }


                if(thisDataNodeID === nodeID || thisBindNodeID === nodeID){
                    return mt;
                }
            };

            var retVal;
            if (treeType === 'data') {
                retVal = dataTree.treeMap(mapFunc);
            }else if (treeType === 'control') {
                retVal = controlTree.treeMap(mapFunc);
            }else{
                throw 'Invalid TreeType specified! Use either "data" or "control"';
            }

            return retVal;

        };
        that.getMugTypeByIDFromTree = getMugTypeByIDFromTree;

        /**
         * Replace a MugType that already exists in a tree with a new
         * one.  It is up to the caller to ensure that the MT
         * ufids and other properties match up as required.
         * Use with caution.
         * @param oldMT
         * @param newMT
         * @param treeType
         *
         * @return - true if a replacement occurred. False if no match was found for oldMT
         */
        var replaceMugType = function (oldMT, newMT, treeType){
            function treeFunc (node) {
                if(node.getValue() === oldMT){
                    node.setValue(newMT);
                    return true;
                }
            }

            var result, tree;
            if(treeType === 'data'){
                tree = dataTree;
            }else {
                tree = controlTree;
            }
            result = tree.treeMap(treeFunc);
            if(result.length > 0){
                return result[0];
            }else {
                return false;
            }
        };
        that.replaceMugType = replaceMugType;
        
        //make the object event aware
        formdesigner.util.eventuality(that);
        return that;
    };
    that.Form = Form;
    
    // Logic expressions
    that.LogicExpression = function (exprText) {
        var expr = {};
        expr._text = exprText || "";
        
        expr.valid = false;
        if (exprText) {
            try {
                expr.parsed = xpath.parse(exprText);
                expr.valid = true;
            } catch (err) {
                // nothing to do
            }
        } else {
            expr.empty = true;
        }
        
        expr.getPaths = function () {
            var paths = [];
            if (this.parsed) {
                var queue = [this.parsed], 
                    node, i, children;
                while (queue.length > 0) {
                    node = queue.shift();
                    if (node instanceof xpathmodels.XPathPathExpr) {
                        paths.push(node);
                    }
                    children = node.getChildren();
                    for (i = 0; i < children.length; i++) {
                        queue.push(children[i]);
                    }
                }
            }
            return paths;
        };
        
        expr.updatePath = function (from, to) {
            var paths = this.getPaths(),
                path;
            
            var replacePathInfo = function (source, destination) {
                // copies information from source to destination in place,
                // resulting in mutating destination while preserving the 
                // original object reference.
                destination.initial_context = source.initial_context;
                destination.steps = source.steps;
                destination.filter = source.filter;
            };
            
            for (var i = 0; i < paths.length; i++) {
                path = paths[i];
                if (path.toXPath() === from) {
                    replacePathInfo(xpath.parse(to), path);
                }
            }
        };
        
        expr.getText = function () {
            if (this.valid) {
                return this.parsed.toXPath();
            } else {
                return this._text;
            }
        }
        return expr;
    };
    
    that.LogicManager = (function () {
        var logic = {};
        
        logic.all = [];
        
        logic.clearReferences = function (mug, property) {
            this.all = this.all.filter(function (elem) { 
                return elem.mug != mug.ufid || elem.property != property;
            });
        };
        
        logic.addReferences = function (mug, property) {
            var expr = that.LogicExpression(mug.getPropertyValue(property));
            var paths = expr.getPaths().filter(function (p) {
                // currently we don't do anything with relative paths
                return p.initial_context === xpathmodels.XPathInitialContextEnum.ROOT;
            });
            this.all = this.all.concat(paths.map(function (path) {
                var refMug = formdesigner.controller.getMugByPath(path.pathWithoutPredicates());
                var error = that.FormError({
                    level: "parse-warning",
                    key: mug.ufid + "-" + "badpath",
                    message: "The question '" + mug.mug.properties.bindElement.properties.nodeID + 
                        "' references an unknown question " + path.toXPath() + 
                        " in its " + mug.getPropertyDefinition(property).lstring + "."
                                                
                });
                if (!refMug) {
                    // formdesigner.form.errors
                    formdesigner.controller.form.updateError(error, {updateUI: true});
                } else {
                    formdesigner.controller.form.clearError(error, {updateUI: true});
                }
                return {"mug": mug.ufid, "property": property, "path": path.toXPath(), 
                        "ref": refMug ? refMug.ufid : ""};      
            }));
        };
        
        logic.updateReferences = function (mug, property) {
            this.clearReferences(mug, property);
            this.addReferences(mug, property);
        };
        
        logic.updatePath = function (mugId, from, to) {
            var found = this.all.filter(function (elem) {
                return elem.ref === mugId;
            });
            var ref, mug, expr;
            for (var i = 0; i < found.length; i++) {
                ref = found[i];
                mug = formdesigner.controller.getMTFromFormByUFID(ref.mug);
                expr = that.LogicExpression(mug.getPropertyValue(ref.property));
                orig = expr.getText();
                expr.updatePath(from, to);
                if (orig !== expr.getText()) {
                    formdesigner.controller.setMugPropertyValue(mug.mug, ref.property.split("/")[0], 
                                                                ref.property.split("/")[1], expr.getText(), mug);
                } 
            }
            
        };
        
        logic.reset = function () {
            this.all = [];
        };
        
        return logic;
    }());
    
    // IText
    that.ItextForm = function (options) {
        var form = {};
        
        form.data = options.data || {};
        form.name = options.name || "default";
        
        form.getValue = function (lang) {
            return this.data[lang];
        };
        
        form.setValue = function (lang, value) {
            this.data[lang] = value;
        };
        
        form.getValueOrDefault = function (lang) {
            // check the actual language first
            if (this.data[lang]) {
                return this.data[lang];
            }
            var defLang = that.Itext.getDefaultLanguage();
            // check the default, if necesssary
            if (lang !== defLang && this.data[defLang]) {
                return this.data[defLang];
            }
            // check arbitrarily for something
            for (var i in this.data) {
                if (this.data.hasOwnProperty(i)) {
                    return this.data[i];
                }
            }
            // there wasn't anything
            return "";
        };
        
        form.isEmpty = function () {
            for (var lang in this.data) {
                if (this.data.hasOwnProperty(lang) && this.data[lang]) {
                    return false;
                }
            }
            return true;
        };
        
        return form; 
    };

    /*
     * An "item" of itext.
     */
    
    that.ItextItem = function (options) {
        
        var item = {}; 
        
        item.forms = options.forms || [];
        item.id = options.id || "";
        
        item.getForms = function () {
            return this.forms;
        };
        
        item.getFormNames = function () {
            return this.forms.map(function (form) {
                return form.name;
            });
        };
        
        item.hasForm = function (name) {
            return this.getFormNames().indexOf(name) !== -1;
        };
        
        item.getForm = function (name) {
            return formdesigner.util.reduceToOne(this.forms, function (form) {
                return form.name === name;
            }, "form name = " + name);
        };
        
        item.getOrCreateForm = function (name) {
            try {
                return this.getForm(name);
            } catch (err) {
                return this.addForm(name);
            }
        };
        
        item.addForm = function (name) {
            if (!this.hasForm(name)) {
                var newForm = new that.ItextForm({name: name});
                this.forms.push(newForm);
                return newForm;
            }
        };
        
        item.removeForm = function (name) {
            var names = this.getFormNames();
            var index = names.indexOf(name);
            if (index !== -1) {
                this.forms.splice(index, 1);
            }
        };
        
        item.getValue = function(form, language) {
            if (this.hasForm(form)) {
                return this.getForm(form).getValue(language);
            }
        };
        
        item.defaultValue = function() {
            return this.getValue("default", that.Itext.getDefaultLanguage())
        };
        
        item.setDefaultValue = function(val) {
            this.getOrCreateForm("default").setValue(that.Itext.getDefaultLanguage(), val)
        };
        
        item.isEmpty = function () {
            if (this.forms) {
                var nonEmptyItems = formdesigner.util.filterList(this.forms, function (form) {
                    return !form.isEmpty();
                });
                return nonEmptyItems.length === 0;
            }
            return true;
        };
        
        
        item.hasHumanReadableItext = function() {
            return Boolean(this.hasForm('default') || 
                           this.hasForm('long')    || 
                           this.hasForm('short'));
        };
        
        
        return item; 
        
    };

    /**
     * The itext holder object. Access all Itext through this gate.
     *
     * Expected forms of itext:
     * - default (i.e. no special form)
     * - long
     * - short
     * - image
     * - audio
     * - hint
     *
     */
    that.Itext = (function() {
        var itext = {}; 
        
        itext.languages = [];
        
        itext.getLanguages = function () {
            return this.languages;
        };
        
        itext.hasLanguage = function (lang) {
            return this.languages.indexOf(lang) !== -1;
        };
        
        itext.addLanguage = function (lang) {
            if (!this.hasLanguage(lang)) {
                this.languages.push(lang);
            } 
        };
        
        itext.removeLanguage = function (lang) {
            if(this.hasLanguage(lang)) {
                this.languages.splice(this.languages.indexOf(lang), 1);
            }
            // if we removed the default, reset it
            if (this.getDefaultLanguage() === lang) {
                this.setDefaultLanguage(this.languages.length > 0 ? this.languages[0] : "");
            }
        };
        
        itext.setDefaultLanguage = function (lang) {
            this.defaultLanguage = lang;
        };

        itext.getDefaultLanguage = function () {
            if (this.defaultLanguage) {
                return this.defaultLanguage;
            } else {
                // dynamically generate default arbitrarily
                return this.languages.length > 0 ? this.languages[0] : "";
            }
            
            
        };
        
        itext.items = [];
        
        itext.getItems = function () {
            return this.items;
        };
        
        itext.getNonEmptyItems = function () {
            return formdesigner.util.filterList(this.items, function (item) {
                return !item.isEmpty();
            });
        };
        
        itext.getNonEmptyItemIds = function () {
            return this.getNonEmptyItems().map(function (item) {
                return item.id;
            });
        };
        
        itext.deduplicateIds = function () {
            var nonEmpty = this.getNonEmptyItems();
            var found = [];
            var counter, item, origId;
            for (var i = 0; i < nonEmpty.length; i++) {
                item = nonEmpty[i];
                origId = item.id;
                counter = 2;
                while (found.indexOf(item.id) !== -1) {
                    item.id = origId + counter;
                    counter = counter + 1;
                }
                found.push(item.id);
            }
        };
        
        itext.hasItem = function (item) {
            return this.items.indexOf(item) !== -1;
        };
        
        /**
         * Add an itext item to the global Itext object.
         * Item is an ItextItem object.
         * Does nothing if the item was already in the itext object.
         */
        itext.addItem = function (item) {
            if (!this.hasItem(item)) {
                this.items.push(item);
            } 
        };
        
        /*
         * Create a new blacnk item and add it to the list.
         */
        itext.createItem = function (id) {
            var item = new that.ItextItem({
                id: id,
                forms: [new that.ItextForm({
                            name: "default",
                        })]
            });
            this.addItem(item);
            return item;
        };
        
        /**
         * Get the Itext Item by ID.
         */
        itext.getItem = function (iID) {
            // this is O[n] when it could be O[1] with some other
            // data structure. That would require keeping the ids
            // in sync in multiple places though.
            // This could be worked around via careful event handling,
            // but is not implemented until we see slowness.
            return formdesigner.util.reduceToOne(this.items, function (item) {
                return item.id === iID;
            }, "itext id = " + iID);
        };
        
        itext.getOrCreateItem = function (id) {
            try {
                return this.getItem(id);
            } catch (err) {
                return this.createItem(id); 
            }
        };
        
        itext.removeItem = function (item) {
            var index = this.items.indexOf(item);
            if (index !== -1) {
                this.items.splice(index, 1);
            } 
        };
        
        /**
         * Generates a flat list of all unique Itext IDs currently in the
         * Itext object.
         */
        itext.getAllItemIDs = function () {
            return this.items.map(function (item) {
                return item.id;
            });
        };
                
        
        
        /**
         * Goes through the Itext data and verifies that
         * a) a default language is set to something that exists
         * b) That every iID that exists in the DB has a translation in the default language (causes commcare to fail if not the case)
         *
         * if a) fails, will throw an exception
         * if b) fails, will return a dict of all offending iIDs that need a translation in order to pass validation with
         * the KEYs being ItextIDs and the values being descriptive error messages.
         *
         * if everything passes will return true
         */
        itext.validateItext = function () {
            // TODO: fill this back in
            
            var dLang = this.getDefaultLanguage();

            if(!dLang){
                throw 'No Default Language set! Aborting validation. You should set one!';
            }

            if(!this.hasLanguage(dLang)){
                throw 'Default language is set to a language that does not exist in the Itext DB!';
            }

            return true
        };
        
        itext.clear = function () {
            delete this.languages;
            delete this.items;
            this.languages = [];
            this.items = [];
            
        };
        

        /**
         * Blows away all data stored in the Itext object
         * and resets it to pristine condition (i.e. as if the FD was freshly launched)
         */
        itext.resetItext = function (langs) {
            this.clear();
            if (langs && langs.length > 0) {
                for (var i = 0; i < langs.length; i++) {
                    this.addLanguage(langs[i]);
                }
            }
        };

        /**
         * Takes in a list of Itext Items and resets this object to only
         * include those items. 
         *
         * PERMANENTLY DELETES ALL OTHER ITEXT ITEMS FROM THE MODEL
         *
         * For generating a list of useful IDs see:
         * formdesigner.controller.getAllNonEmptyItextItemsFromMugs()
         *
         * @param validIDList
         */
        
        var resetItextList = function (validIDList) {
            this.items = [];
            for (var i = 0; i < validIDList.length; i++) {
                this.items.push(validIDList[i]);
            }
        };
        itext.resetItextList = resetItextList;

        /**
         * Remove all Itext associated with the given mug
         * @param mug
         */
        itext.removeMugItext = function (mugType) {
            // NOTE: this is not currently used. We clear itext
            // at form-generation time. This is because shared 
            // itext makes removal problematic.
            var labelItext, hintItext, constraintItext;
            var mug = mugType.mug;
            if (mug){
	            if (mug.properties.controlElement) {
	                //attempt to remove Itext
	                labelItext = mug.properties.controlElement.properties.labelItextID;
	                hintItext = mug.properties.controlElement.properties.hintItextID;
	                if (labelItext) {
	                    this.removeItem(labelItext);
	                }
	                if (hintItext) {
	                    this.removeItem(hintItext);
	                }
	            } 
	            if (mug.properties.bindElement) {
	                constraintItext = mug.properties.bindElement.properties.constraintMsgItextID;
	                if (constraintItext) {
	                    this.removeItem(constraintItext);
	                }
	            }
	        }
        };


        itext.updateForNewMug = function(mugType) {
            // for new mugs, generate a label
            return this.updateForMug(mugType, mugType.getDefaultLabelValue());
        };
        
        itext.updateForExistingMug = function(mugType) {
            // for existing, just use what's there
            return this.updateForMug(mugType, mugType.getLabelValue());
        };
        
        itext.updateForMug = function (mugType, defaultLabelValue) {
            // set default itext id/values
            if (mugType.hasControlElement()) {
                // set label if not there
                if (!mugType.mug.properties.controlElement.properties.labelItextID) {
		            mugType.mug.properties.controlElement.properties.labelItextID = mugType.getDefaultLabelItext(defaultLabelValue);
		            this.addItem(mugType.mug.properties.controlElement.properties.labelItextID);
	            }
	            // set hint if legal and not there
	            if (mugType.properties.controlElement.hintItextID.presence !== "notallowed" &&
	                !mugType.mug.properties.controlElement.properties.hintItextID) {
	                mugType.mug.properties.controlElement.properties.hintItextID = this.createItem("");
	            }
	        }
	        if (mugType.hasBindElement()) {
	            // set constraint msg if legal and not there
	            if (mugType.properties.bindElement.constraintMsgItextID.presence !== "notallowed" &&
	                !mugType.mug.properties.bindElement.properties.constraintMsgItextID) {
	                mugType.mug.properties.bindElement.properties.constraintMsgItextID = this.createItem("");
	            }
	        }
	    };
        
        //make event aware
        formdesigner.util.eventuality(itext);

        return itext;
    })();

    /**
     * Called during a reset.  Resets the state of all
     * saved objects to represent that of a fresh init.
     */
    that.reset = function () {
        that.form = new Form();
        that.Itext.resetItext(formdesigner.opts.langs);
        that.LogicManager.reset();
        formdesigner.controller.setForm(that.form);
    };

    /**
     * An initialization function that sets up a number of different fields and properties
     */
    var init = function () {
        var form = that.form = new Form();
        //set the form object in the controller so it has access to it as well
        formdesigner.controller.setForm(form);
    };
    that.init = init;




    return that;
}();
