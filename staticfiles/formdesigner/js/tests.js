
var JRVALIDATE_MODE = true;

var validateCallbackFunc = function (testDescription) {
    var thisDesc = testDescription;
    var func = function(data, textStatus, jqXHR) {
        if(!data.success) {
            console.group('JR Validation Error');
            console.log(data);
            console.groupEnd();
        }
        ok(data.success, 'Form Validates with JR validator:'+thisDesc);
        start();
    };
    return func;
};

$(document).ready(function(){
    formdesigner.launch({});
    var testXformBuffer = {};
    var testFormNames = [
//        "Follow-up a Household Referral.xml",
//        "Follow-up at household.xml",
//        "Pos Parto.xml",
//        "Registo.xml",
//        "Follow-up a pregnancy referral.xml",
//        "Gravidez.xml",
//        "Register a household.xml",
        "Close a pregnancy.xml",
//        "Follow-up a pregnancy.xml",
//        "NutritionAndHealth.xml",
//        "Register a pregnancy.xml"
    ];

    var get_cchq_forms = function (name) {
        getFormFromServerAndPlaceInBuffer('fromcchq/' + name);
    };

    var make_control_bind_data_mug = function(){
        var myMug;

        //Control Element
        var typeName = "input";
        var myControl = new formdesigner.model.ControlElement(
                {
                    name:"Text",
                    tagName: "input",
                    label:"What is your name?",
                    hintLabel:"Enter the client's name",
                    labelItextID:"Q1EN",
                    hintItextID:"Q1ENH"
                }
        );

        //Data Element
        var name = "question1";
        var initialData = "foo";
        var spec = {
            dataValue: initialData,
            nodeID: "data_for_question1"
        };
        var myData = formdesigner.model.DataElement(spec);

        //Bind Element
        var attributes = {
            dataType: "xsd:text",
            constraintAttr: "length(.) > 5",
            constraintMsgAttr: "Town Name must be longer than 5!",
            nodeID: "question1"
        };
        spec =  attributes;
        var myBind = new formdesigner.model.BindElement(spec);

        var mugSpec = {
            dataElement: myData,
            bindElement: myBind,
            controlElement: myControl
        };
        myMug = new formdesigner.model.Mug(mugSpec);

        return {
            control: myControl,
            data: myData,
            bind: myBind,
            mug: myMug
        };
    };

    var getFormFromServerAndPlaceInBuffer = function (formName) {
        $.ajax({
            url: 'testing/xforms/' + formName,
            async: false,
            cache: false,
            dataType: 'text',
            success: function(xform){
                testXformBuffer[formName] = xform;
            }
        });
    };

    var giveMugFakeValues = function (mug, mugType) {
        function randomString() {
            var chars = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXTZabcdefghiklmnopqrstuvwxyz";
            var string_length = 8;
            var randomstring = '';
            for (var i=0; i<string_length; i++) {
                var rnum = Math.floor(Math.random() * chars.length);
                randomstring += chars.substring(rnum,rnum+1);
            }
            return randomstring;
        }
        for (var i in mug.properties) {
            if(mug.properties.hasOwnProperty(i)) {
                for (var j in mug.properties[i].properties) {
                    if(mug.properties[i].properties.hasOwnProperty(j)){
                        if(!mug.properties[i].properties[j]){ //if value is empty/blank
                            if(i === 'dataElement' && j === 'nodeID'){
                                mug.properties[i].properties[j] = formdesigner.util.generate_question_id();
                                if(mug.properties.bindElement){ //set bindElement.nodeID to same as dataElement.nodeID
                                    mug.properties.bindElement.properties.nodeID = mug.properties[i].properties[j];
                                }
                            } else {
                                // hack for itext to properly be set
                                if (j.indexOf("ItextID") !== -1) {
                                    mug.properties[i].properties[j] = formdesigner.model.ItextItem({
                                        id: formdesigner.util.generate_item_label()
                                    });
                                    mug.properties[i].properties[j].setDefaultValue(randomString());
                                } else {
                                    mug.properties[i].properties[j] = randomString();
                                }
                            }
                        }

                    }
                }
            }
        }
        if (mugType.properties.bindElement) {
            if (mug.properties.bindElement.properties.constraintMsgAttr && mug.properties.bindElement.properties.constraintMsgItextID) {
                // hack, these are mutually exclusive so remove one to make the validator happy
                delete mug.properties.bindElement.properties["constraintMsgAttr"];
            }         
        }
    };

    var addQuestionThroughUI = function (type) {
        var addbut, sel;
        addbut = $('#fd-add-but');
        sel = $('#fd-question-select');

        sel.val(type); //set the dropdown to the correct val
        addbut.click(); //click the add question button.

    };

    var listsHaveSameContents = function (expect, actual) {
        equal(expect.length, actual.length, "Lists are the same length");
        for (var i = 0; i < expect.length; i++) {
            ok(actual.indexOf(expect[i]) !== -1, "Item " + expect[i] + " found in actual.");
            ok(expect.indexOf(actual[i]) !== -1, "Item " + actual[i] + " found in expected.");
        }
    };

    module("LiveText Unit Tests");
    asyncTest("Create and Verify LiveText", function(){
        expect(4);

        ////////
        var liveText = new formdesigner.model.LiveText();
        ok(typeof liveText === 'object',"LiveText object should be an Object");

        ////////
        liveText.addToken("Test String");
        equal(liveText.renderString(),"Test String", "Check for correct rendering of added string 'Test String'");

        ////////
        var testObj = (function (){
            var that = {};
            var text = "Some Text";
            var cbFunc = function(){
                return this.text;
            };
            that.text = text;
            that.cbFunc = cbFunc;
            return that;
        })();
        liveText.addToken(testObj,testObj.cbFunc);
        equal(liveText.renderString(),"Test StringSome Text","correct rendering of obj token with callback");

        ////////
        var otherObj = {text: " Meow Mix times: "};
        otherObj.cbFunc = function(n){
            return this.text + n;
        };
        liveText.addToken(otherObj,otherObj.cbFunc,[5]);
        equal(liveText.renderString(),"Test StringSome Text Meow Mix times: 5", "rendering with callback + params");
        start();
    });
    asyncTest("Test additional LiveText object", function(){
        expect(2);

        ///////
        var otherLiveText = new formdesigner.model.LiveText;
        equal(otherLiveText.renderString(),"", 'test render empty liveText');

        ///////
        otherLiveText.addToken("foo ");
        otherLiveText.addToken("bar");
        equal(otherLiveText.renderString(),"foo bar", "check creation of additional LiveText and that it produces correct results");
start();
    });

    module("Bind Element");
    asyncTest("Create a bind with and without arguments", function(){
       expect(8);
       var myBind = new formdesigner.model.BindElement();
       ok(typeof myBind === 'object', "Is it an object?");

       //make the spec object for the bind constructor
        var spec = {
            dataRef: "question1",
            dataType: "text",
            constraint: "length(.) > 5",
            constraintMsg: "Town Name must be longer than 5!",
            id: "someUniqueBindID"
        };


        var myOtherBind = new formdesigner.model.BindElement(spec);

        //check if the bind was created properly
        equal(myOtherBind.properties.dataRef, spec.dataRef, "Shortcut to dataRef correctly set");
        equal(myOtherBind.properties.dataType, spec.dataType, "Shortcut to dataRef correctly set");
        equal(myOtherBind.properties.constraint, spec.constraint, "Shortcut to dataRef correctly set");
        equal(myOtherBind.properties.constraintMsg, spec.constraintMsg, "Shortcut to dataRef correctly set");
        equal(myOtherBind.properties.id, spec.id, "Shortcut to id correctly set");

        //test that a unique formdesigner id was generated for this object (well, kind of)
        equal(typeof myOtherBind.ufid, 'string', "Is the ufid a string?");

        notEqual(myBind.ufid,myOtherBind.ufid, "Make sure that the ufids are unique");
//        ok(typeof myOtherBind.ufid === 'string', "Is the ufid a string?");
        start();
    });

    module("Data Element");
    asyncTest("Create a data Element with and without", function(){
        expect(6);
        var myData = new formdesigner.model.DataElement();
        ok(typeof myData === 'object', "Is it an object?");

        var name = "question1";
        var initialData = "foo";
        var spec = {
            name: name,
            defaultData: initialData
        };

        var otherData = formdesigner.model.DataElement(spec);
        ok(typeof otherData === 'object', "Is it an object? (with args)");
        equal(otherData.properties.name,name,"Was the name attribute set correctly?");
        equal(otherData.properties.defaultData,initialData,"Is initialData correct?");
        equal(typeof otherData.ufid, 'string', "Is ufid a string and exists?");
        notEqual(otherData,myData,"Test that data elements are unique");
        start();
    });

    module("Control Element");
    asyncTest("Control Element Default", function(){
        expect(2);
        var emptyControl = new formdesigner.model.ControlElement();
        ok(typeof emptyControl === 'object', "Is emptyControl an object?");

        var typeName = "input";
        var fullControl = new formdesigner.model.ControlElement(
                {
                    typeName:typeName
                }
        );

        notEqual(emptyControl.ufid,fullControl.ufid,"Check that ufids are not equal for ControlElements");
start();
    });
    asyncTest("Control Element with additional init value", function(){
        expect(2);
               //Control Element
        var typeName = "input";
        var myControl = new formdesigner.model.ControlElement(
                {
                    typeName:typeName,
                    label:"What is your name?",
                    hintLabel:"Enter the client's name",
                    labelItext:"Q1EN",
                    hintItext:"Q1ENH"
                }
        );

        equal(myControl.properties.typeName,typeName, "Was type name set?");
        equal(typeof myControl.ufid,'string', "Does ufid exist?");
        start();
    });

    module("Mug Unit Tests");
    asyncTest("Create and Verify Mug with null constructor", function(){
        expect(4);
        var myMug = new formdesigner.model.Mug();
        ok(typeof myMug === 'object',"Test that the object is an object");

        ok(typeof myMug.properties.bindElement === 'undefined', "BindElement should not exist in object constructed with no params");
        ok(typeof myMug.properties.controlElement === 'undefined', "ControlElement should not exist in object constructed with no params");
        ok(typeof myMug.properties.dataElement === 'undefined', "DataElement should not exist in object constructed with no params");
        start();

    });
    asyncTest("Create and Verify Mug with fake Bind,Control and Data element specified in Constructor", function(){
        expect(4);
        var specObj = {
           bindElement: {},
           controlElement: {},
           dataElement: {}
        }
        var myMug = new formdesigner.model.Mug(specObj);
        ok(typeof myMug === 'object',"Test that the object is an object");

        ok(typeof myMug.properties.bindElement === 'object', "BindElement should exist in object constructed with params");
        ok(typeof myMug.properties.controlElement === 'object', "ControlElement should exist in object constructed with params");
        ok(typeof myMug.properties.dataElement === 'object', "DataElement should exist in object constructed with params");
        start();
    });
    asyncTest("Create populated Mug", function(){
       expect(5);
        var testData = make_control_bind_data_mug();
        var myMug = testData.mug;
        var myControl = testData.control;
        var myBind = testData.bind;
        var myData = testData.data;
        ok(typeof myMug === 'object',"Is this populated mug an object?");
        equal(typeof myMug.definition,'undefined', "Is the definition undefined?");
        deepEqual(myMug.properties.controlElement,myControl,"Control Element check");
        deepEqual(myMug.properties.bindElement,myBind, "Bind Element check");
        deepEqual(myMug.properties.dataElement,myData, "Data Element check");

start();




    });
    module("MugType tests");
    asyncTest("Validate example mug against definition", function(){
        expect(3);
        var myMug;
        var MugType = formdesigner.model.mugTypeMaker.stdTextQuestion(); //simulates a 'standard' text question
        myMug = MugType.mug;
        giveMugFakeValues(myMug,MugType);
        var validationObject = MugType.validateMug(myMug);
        equal(MugType.typeName, "Text Question");
        equal(validationObject.status, "pass", 'Does the mug validate against the MugType?');

        var otherType = formdesigner.model.mugTypeMaker["stdTextQuestion"]();
        otherType.properties.bindElement['someProperty'] = 'foo';
        var vObj = otherType.validateMug(myMug);
        equal(vObj.status,'fail', "This should fail because the mug does not contain the required property");
    
        start();
    });

    asyncTest("Validate mug itext properties", function(){
        resetVellumForUnitTests();
        expect(7);
        var MugType = formdesigner.model.mugTypeMaker.stdTextQuestion(); //simulates a 'standard' text question
        var myMug = MugType.mug;
        giveMugFakeValues(myMug,MugType);
        
        equal(MugType.validateMug(myMug).status, "pass", 'Initial mug validates fine.');
        
        var validateItext = function (node, slug) {
            node.id = "some-" + slug + "-id";
            node.setDefaultValue("");
	        equal(MugType.validateMug(myMug).status, "fail", "Mug with a " + slug + " id but no text fails.");
	        node.setDefaultValue("en", slug + " value");
	        equal(MugType.validateMug(myMug).status, "pass", "Mug with a " + slug + " id and text passes.");
            node.id = "";
	        equal(MugType.validateMug(myMug).status, "fail", "Mug with a " + slug + " text but no id fails.");
            // clear to leave things as they are
            node.getForm("default").setValue("en", "");
        };
        validateItext(myMug.properties.controlElement.properties.hintItextID, "hint");
        validateItext(myMug.properties.bindElement.properties.constraintMsgItextID, "constraintMsg");
        
        
        start();
    });

    asyncTest("Test custom validation function in bind block definition", function(){
        expect(2);
        var myMug;
        var MugType = formdesigner.model.mugTypeMaker.stdTextQuestion(); //simulates a 'standard' text question
        myMug = MugType.mug;
        giveMugFakeValues(myMug,MugType);
        myMug.properties.bindElement.properties.constraintAttr = "foo";
        myMug.properties.bindElement.properties.constraintMsgAttr = null;
        var validationObject = MugType.validateMug(myMug);
        equal(validationObject.status,'pass', "Mug has a constraint but no constraint message which is OK");

        //now remove constraint but add a constraint message
        myMug.properties.bindElement.properties.constraintAttr = undefined;
        myMug.properties.bindElement.properties.constraintMsgAttr = "foo";
        validationObject = MugType.validateMug(myMug);
        equal(validationObject.status,'fail', "Special validation function has detected a constraintMsg but no constraint attribute in the bindElement");
        start();
    });

    asyncTest("MugType creation tools", function(){
        expect(2);
        var testData = make_control_bind_data_mug();
        var myMug = testData.mug;
        myMug.properties.bindElement.constraintAttr = "foo";
        myMug.properties.bindElement.constraintMsgAttr = undefined;
        var MugType = formdesigner.model.RootMugType; //simulates a 'standard' text question

        var OtherMugType = formdesigner.util.getNewMugType(MugType);
        notDeepEqual(MugType,OtherMugType);

        OtherMugType.typeName = "This is a different Mug";
        notEqual(MugType.typeName,OtherMugType.typeName);
start();
    });

    module("Automatic Mug Creation from MugType");
    asyncTest("Create mug from MugType", function(){
        expect(2);
        var mugType = formdesigner.model.mugTypeMaker.stdTextQuestion();
        var mug = mugType.mug;
        giveMugFakeValues(mug,mugType);
        ok(typeof mug === 'object', "Mug is an Object");
        equal(mugType.validateMug(mug).status,'pass', "Mug passes validation");
        start();
    });
    asyncTest("Test sub MugType and Mug creation",function(){
        expect(23);
        //capital A for 'Abstract'
        var AdbType  = formdesigner.model.mugTypes.dataBind,
            AdbcType = formdesigner.model.mugTypes.dataBindControlQuestion,
            AdcType  = formdesigner.model.mugTypes.dataControlQuestion,
            AdType   = formdesigner.model.mugTypes.dataOnly,
        tMug,Mug;

        tMug = formdesigner.util.getNewMugType(AdbType);
        Mug = formdesigner.model.createMugFromMugType(tMug);
        giveMugFakeValues(Mug,tMug);
        ok(typeof tMug === 'object', "MugType creation successful for '"+tMug.typeName+"' MugType");
        ok(tMug.validateMug(Mug).status === 'pass', "Mug created from '"+tMug.typeName+"' MugType passes validation");
        ok(typeof Mug.properties.controlElement === 'undefined', "Mug's ControlElement is undefined");
        ok(typeof Mug.properties.bindElement === 'object', "Mug's bindElement exists");
        ok(typeof Mug.properties.dataElement === 'object', "Mug's dataElement exists");
        equal(Mug.properties.dataElement.properties.nodeID,Mug.properties.bindElement.properties.nodeID);

        tMug = formdesigner.util.getNewMugType(AdbcType);
        Mug = formdesigner.model.createMugFromMugType(tMug);
        giveMugFakeValues(Mug,tMug);
        ok(typeof tMug === 'object', "MugType creation successful for '"+tMug.typeName+"' MugType");
        ok(tMug.validateMug(Mug).status === 'pass', "Mug created from '"+tMug.typeName+"' MugType passes validation");
        ok(typeof Mug.properties.controlElement === 'object', "Mug's ControlElement exists");
        ok(typeof Mug.properties.bindElement === 'object', "Mug's bindElement exists");
        ok(typeof Mug.properties.dataElement === 'object', "Mug's dataElement exists");
        equal(Mug.properties.dataElement.properties.nodeID,Mug.properties.bindElement.properties.nodeID);

        tMug = formdesigner.util.getNewMugType(AdcType);
        Mug = formdesigner.model.createMugFromMugType(tMug);
        giveMugFakeValues(Mug,tMug);
        ok(typeof tMug === 'object', "MugType creation successful for '"+tMug.typeName+"' MugType");
        ok(tMug.validateMug(Mug).status === 'pass', "Mug created from '"+tMug.typeName+"' MugType passes validation");
        ok(typeof Mug.properties.controlElement === 'object', "Mug's ControlElement exists");
        ok(typeof Mug.properties.bindElement === 'undefined', "Mug's bindElement is undefined");
        ok(typeof Mug.properties.dataElement === 'object', "Mug's dataElement exists");

        tMug = formdesigner.util.getNewMugType(AdType);
        Mug = formdesigner.model.createMugFromMugType(tMug);
        giveMugFakeValues(Mug,tMug);
        ok(typeof tMug === 'object', "MugType creation successful for '"+tMug.typeName+"' MugType");
        ok(tMug.validateMug(Mug).status === 'pass', "Mug created from '"+tMug.typeName+"' MugType passes validation");
        ok(typeof Mug.properties.controlElement === 'undefined', "Mug's ControlElement is undefined");
        ok(typeof Mug.properties.bindElement === 'undefined', "Mug's bindElement is undefined");
        ok(typeof Mug.properties.dataElement === 'object', "Mug's dataElement exists");
        ok(Mug.properties.dataElement.properties.nodeID.toLocaleLowerCase().indexOf('question') != -1);
        start();
    });

    asyncTest("More MugType validation testing", function(){
        var AdbType  = formdesigner.model.mugTypes.dataBind,
            AdbcType = formdesigner.model.mugTypes.dataBindControlQuestion,
            AdcType  = formdesigner.model.mugTypes.dataControlQuestion,
            AdType   = formdesigner.model.mugTypes.dataOnly,
        tMug,Mug;

        tMug = formdesigner.util.getNewMugType(AdbType);
        Mug = formdesigner.model.createMugFromMugType(tMug);
        tMug.type="dbc";


        var validationResult = tMug.validateMug(Mug);
        notEqual(validationResult.status,'pass',"MugType is wrong Type ('dbc' instead of 'db')");
        tMug.type = "";
        validationResult = tMug.validateMug(Mug);
        notEqual(validationResult.status,'pass',"MugType is wrong Type ('' instead of 'db')");
        start();
    });

    asyncTest("Check MugType properties alterations",function(){
        var mugTA = formdesigner.model.mugTypeMaker.stdTextQuestion(),
            mugTB = formdesigner.model.mugTypeMaker.stdTrigger(),
            mugTC = formdesigner.model.mugTypeMaker.stdMSelect(),
            mugA = mugTA.mug,
            mugB = mugTB.mug,
            mugC = mugTC.mug;

        notEqual(mugTB.ufid,mugTC.ufid);
        notEqual(mugTB.properties, mugTC.properties);
        equal(mugTC.properties.bindElement.nodeID.visibility,'advanced');
start();
    })

    module("Tree Data Structure Tests");
    asyncTest("Trees", function(){
//        expect(16);

        ///////////BEGIN SETUP///////
        var mugTA = formdesigner.model.mugTypeMaker.stdGroup(),
            mugTB = formdesigner.model.mugTypeMaker.stdGroup(),
            mugTC = formdesigner.model.mugTypeMaker.stdGroup(),
            mugA = mugTA.mug,
            mugB = mugTB.mug,
            mugC = mugTC.mug,
            tree = new formdesigner.model.Tree('data');
        var GNMT = formdesigner.util.getNewMugType;
        var createMugFromMugType = formdesigner.model.createMugFromMugType;
        var DBCQuestion = formdesigner.model.mugTypeMaker.stdTextQuestion();

        giveMugFakeValues(mugA,mugTA);
        giveMugFakeValues(mugB,mugTB);
        giveMugFakeValues(mugC,mugTC);

        var vTA = mugTA.validateMug(),
                vTB = mugTB.validateMug(),
                vTC = mugTC.validateMug();
        if(!((vTA.status === 'pass') && (vTB.status === 'pass') && (vTC.status === 'pass'))){
            console.group("VALIDATION FAILURE BLOCK");
            console.log("validation obj A",vTA);
            console.log("validation obj B",vTB);
            console.log("validation obj C",vTC);
            console.groupEnd()
            ok(false);
            throw 'AUTO MUG CREATION FROM MUG DID NOT PASS VALIDATION SEE CONSOLE'
        }

        tree.insertMugType(mugTA, 'into', null); //add mugA as a child of the rootNode
        tree.insertMugType(mugTB, 'into',mugTA ); //add mugB as a child of mugA...
        tree.insertMugType(mugTC, 'into', mugTB); //...
        //////////END SETUP//////////

        var actualPath = tree.getAbsolutePath(mugTC);
        var expectedPath =  '/'+formdesigner.controller.form.formID+
                            '/'+mugTA.mug.properties.dataElement.properties.nodeID+
                            '/'+mugTB.mug.properties.dataElement.properties.nodeID+
                            '/'+mugTC.mug.properties.dataElement.properties.nodeID;
        equal(actualPath, expectedPath, 'Is the generated DataElement path for the mug correct?');

        var treePrettyPrintExpected = ''+tree._getRootNodeID()+'['+
                tree._getMugTypeNodeID(mugTA)+'['+
                tree._getMugTypeNodeID(mugTB)+'['+
                tree._getMugTypeNodeID(mugTC)+']]]';
        equal(treePrettyPrintExpected,tree.printTree(), 'Check the tree structure is correct1');

        actualPath = tree.getAbsolutePath(mugTC);
        tree.removeMugType(mugTC);
        tree.insertMugType(mugTC,'into',mugTB);
        equal(actualPath,expectedPath, 'Is the path still correct after removal and insertion (into the same place');

        treePrettyPrintExpected = ''+tree._getRootNodeID()+'['+
                tree._getMugTypeNodeID(mugTA)+'['+
                tree._getMugTypeNodeID(mugTB)+'['+
                tree._getMugTypeNodeID(mugTC)+']]]';
        equal(treePrettyPrintExpected,tree.printTree(), 'Check the tree structure is correct2');
        
        tree.insertMugType(mugTC, 'into', mugTA);
        actualPath = tree.getAbsolutePath(mugTC);
        expectedPath =  '/'+formdesigner.controller.form.formID+
                        '/'+mugTA.mug.properties.dataElement.properties.nodeID+
                        '/'+mugTC.mug.properties.dataElement.properties.nodeID;
        equal(actualPath, expectedPath, 'After move is the calculated path still correct?');

        treePrettyPrintExpected = ''+tree._getRootNodeID()+'['+
                tree._getMugTypeNodeID(mugTA)+'['+
                tree._getMugTypeNodeID(mugTB)+','+
                tree._getMugTypeNodeID(mugTC)+']]';
        equal(treePrettyPrintExpected,tree.printTree(), 'Check the tree structure is correct3');

        tree.removeMugType(mugTB);
        ok(tree.getAbsolutePath(mugTB) === null, "Cant find path of MugType that is not present in the Tree!");

        tree.insertMugType(mugTB,'before',mugTC);
        treePrettyPrintExpected = ''+tree._getRootNodeID()+'['+
            tree._getMugTypeNodeID(mugTA)+'['+
            tree._getMugTypeNodeID(mugTB)+','+
            tree._getMugTypeNodeID(mugTC)+']]';
        equal(treePrettyPrintExpected,tree.printTree(), 'Check the tree structure is correct4');

        tree.removeMugType(mugTB);
        ok(tree.getAbsolutePath(mugTB) === null, "Cant find path of MugType that is not present in the Tree!");

        tree.insertMugType(mugTB,'before',mugTC);
        treePrettyPrintExpected = ''+tree._getRootNodeID()+'['+
            tree._getMugTypeNodeID(mugTA)+'['+
            tree._getMugTypeNodeID(mugTB)+','+
            tree._getMugTypeNodeID(mugTC)+']]';
        equal(treePrettyPrintExpected,tree.printTree(), 'Check the tree structure is correct5');

        var mugTD = GNMT(DBCQuestion);
        var mugD = createMugFromMugType(mugTD);
        tree.insertMugType(mugTD, 'before', mugTA);
        equal('/' + formdesigner.controller.form.formID + '/' + mugTD.mug.properties.dataElement.properties.nodeID, tree.getAbsolutePath(mugTD),
             "Check that the newly inserted Mug's generated path is correct");
        treePrettyPrintExpected = ''+tree._getRootNodeID()+'['+
            tree._getMugTypeNodeID(mugTD)+','+
            tree._getMugTypeNodeID(mugTA)+'['+
            tree._getMugTypeNodeID(mugTB)+','+
            tree._getMugTypeNodeID(mugTC)+']]';
        equal(tree.printTree(),treePrettyPrintExpected, 'Check the tree structure is correct6');

        tree.insertMugType(mugTD,'after',mugTB);
        treePrettyPrintExpected = ''+tree._getRootNodeID()+'['+
            tree._getMugTypeNodeID(mugTA)+'['+
            tree._getMugTypeNodeID(mugTB)+','+
            tree._getMugTypeNodeID(mugTD)+','+
            tree._getMugTypeNodeID(mugTC)+']]';
        equal(treePrettyPrintExpected,tree.printTree(), 'Check the tree structure is correct7');

        tree.insertMugType(mugTD,'after',mugTC);
        treePrettyPrintExpected = ''+tree._getRootNodeID()+'['+
            tree._getMugTypeNodeID(mugTA)+'['+
            tree._getMugTypeNodeID(mugTB)+','+
            tree._getMugTypeNodeID(mugTC)+','+
            tree._getMugTypeNodeID(mugTD)+']]';
        equal(treePrettyPrintExpected,tree.printTree(), 'Check the tree structure is correct8');

        var tempMT = tree.getMugTypeFromUFID(mugTA.ufid);
        deepEqual(mugTA, tempMT, "Check getMugTypeFromUFID() method works correctly");

        tempMT = tree.getMugTypeFromUFID("foobar");
        equal(tempMT, null, "Check getMugTypeFromUFID('notAUFID') returns null");

        tempMT = tree.getMugTypeFromUFID(mugTD.ufid);
        deepEqual(mugTD,tempMT);
start();

    });
    module("UITree");
    asyncTest("Children moving/relative location tests", function(){
            var mugTA = formdesigner.model.mugTypeMaker.stdGroup(),
            mugTB = formdesigner.model.mugTypeMaker.stdTextQuestion(),
            mugTC = formdesigner.model.mugTypeMaker.stdTextQuestion(),
            mugA = mugTA.mug,
            mugB = mugTB.mug,
            mugC = mugTC.mug;
        ok(formdesigner.util.canMugTypeHaveChildren(mugTA,mugTB), "Can a 'Group' MugType have children of type 'Text'?");
        ok(!formdesigner.util.canMugTypeHaveChildren(mugTB,mugTA), "'Text' mugType can NOT have children (of type 'group')");
        ok(!formdesigner.util.canMugTypeHaveChildren(mugTB,mugTC), "'Text' can't have children of /any/ type");

        var relPos = formdesigner.util.getRelativeInsertPosition,
        pos = relPos(mugTA,mugTB);
        equal(pos,'into', "Insert a 'Text' MT into a 'Group' MT");
        pos = relPos(mugTB,mugTC);
        equal(pos,'after', "Insert 'Text' after other 'Text'");
start();

    });

    asyncTest("Tree insertion tests", function(){
        expect(4);
        resetVellumForUnitTests();
        var mugTA = formdesigner.model.mugTypeMaker.stdGroup(),
            mugTB = formdesigner.model.mugTypeMaker.stdTextQuestion(),
            mugTC = formdesigner.model.mugTypeMaker.stdTextQuestion(),
            mugA = mugTA.mug,
            mugB = mugTB.mug,
            mugC = mugTC.mug;


        var mugs = [mugTA, mugTB, mugTC];
        for (var i = 0; i < mugs.length; i++) {
            giveMugFakeValues(mugs[i].mug, mugs[i]);
            
        }
        mugA.properties.controlElement.properties.labelItextID.setDefaultValue('group1 itext');
        mugB.properties.controlElement.properties.labelItextID.setDefaultValue('question1 itext');
        mugC.properties.controlElement.properties.labelItextID.setDefaultValue('question2 itext');

        var c = formdesigner.controller, disp = formdesigner.util.getMugDisplayName;
        c.insertMugTypeIntoForm(null,mugTA);
        var tree = c.form.dataTree;
        var treePrettyPrintExpected = ''+tree._getRootNodeID()+'['+
                                        tree._getMugTypeNodeID(mugTA)+']';

        equal(c.form.dataTree.printTree(),treePrettyPrintExpected, "Tree structure is correct after inserting a 'Group' MT under root DATA TREE");

        treePrettyPrintExpected = ''+tree._getRootNodeID()+'['+
                                        disp(mugTA)+']';
        equal(c.form.controlTree.printTree(),treePrettyPrintExpected, "Tree structure is correct after inserting a 'Group' MT under root CONTROL TREE");

        c.insertMugTypeIntoForm(mugTA,mugTB);
        treePrettyPrintExpected = ''+tree._getRootNodeID()+'['+
                                        tree._getMugTypeNodeID(mugTA)+'['+
                                        tree._getMugTypeNodeID(mugTB)+']]';
        equal(c.form.dataTree.printTree(),treePrettyPrintExpected, "Tree structure is correct after inserting a 'Text' MT under 'Group' DATA TREE");

        treePrettyPrintExpected = ''+tree._getRootNodeID()+'['+
                                        disp(mugTA)+'['+
                                        disp(mugTB)+']]';
        equal(c.form.controlTree.printTree(),treePrettyPrintExpected, "Tree structure is correct after inserting a 'Text' MT under 'Group' CONTROL TREE");
        start();
    });

    asyncTest("Does check_move() work correctly?", function(){
        var mugTA = formdesigner.model.mugTypeMaker.stdTextQuestion(),
            mugTB = formdesigner.model.mugTypeMaker.stdTrigger(),
            mugTC = formdesigner.model.mugTypeMaker.stdItem(),
            mugA = mugTA.mug,
            mugB = mugTB.mug,
            mugC = mugTC.mug;
            resetVellumForUnitTests();
        var c = formdesigner.controller,
        m = formdesigner.model;

        var tree = c.form.controlTree;
        ok(c.checkMoveOp(mugTA,'before',mugTB));
        ok(!c.checkMoveOp(mugTA,'into',mugTB));

        var mugTGroupA = formdesigner.model.mugTypeMaker.stdGroup(),
            mugTGroupB = formdesigner.model.mugTypeMaker.stdGroup(),
            mugTGroupC = formdesigner.model.mugTypeMaker.stdGroup(),
            mugGA = mugTGroupA.mug,
            mugGB = mugTGroupB.mug,
            mugGC = mugTGroupC.mug;
        ok(c.checkMoveOp(mugTA,'into',mugTGroupA));
        ok(c.checkMoveOp(mugTB,'into',mugTGroupA));
        ok(!c.checkMoveOp(mugTC,'into',mugTGroupA));

        var mugTD = formdesigner.model.mugTypeMaker.stdMSelect(),
            mugD = mugTD.mug;

        ok(c.checkMoveOp(mugTD,'into',mugTGroupA));
        ok(c.checkMoveOp(mugTC,'into',mugTD));
        ok(!c.checkMoveOp(mugTA,'into',mugTD));
        ok(!c.checkMoveOp(mugTGroupA,'into',mugTD));

start();

    });

    module("UI Create Questions Tests");
    asyncTest("Add A text question", function(){

        resetVellumForUnitTests();

        var c,ui, jstree, curMugType, addqbut;


        c = formdesigner.controller
        ui = formdesigner.ui;
        jstree = $("#fd-question-tree");

        equal(c.form.controlTree.printTree(false), formdesigner.controller.form.formID, "Ensure the controlTree is empty after a call to resetFormDesigner");
        equal(c.form.dataTree.printTree(false), formdesigner.controller.form.formID, "Ensure the dataTree is empty after a call to resetFormDesigner");

        //add a listener for question creation events
        c.on("question-creation", function(e){
            curMugType = e.mugType;
        });

        addqbut = $('#fd-add-but');
        addqbut.click();
        addqbut.click();
        addqbut.click();
        jstree.jstree("select_node",$('#'+curMugType.ufid));

        var curSelNode = jstree.jstree("get_selected");
        var curSelMT = c.getMTFromFormByUFID(curSelNode.attr('id'));
        ok(typeof jstree.jstree("get_selected") !== 'undefined');


        equal(jstree.jstree("get_selected").attr('id'), curMugType.ufid, "Mug that was just created is the same as the one that is currently selected");
start();
    });

    module("Itext functionality testing");
    asyncTest("Itext Language Operations", function(){
        resetVellumForUnitTests();
        var IT = formdesigner.model.Itext;
        var otherLanguageName = "sw";
        ok(IT.getLanguages().length === 1, "Test that there is only one language at start");
        ok(IT.getLanguages()[0] === "en", "Test that english loads as the only language.");
        ok(IT.getDefaultLanguage() === "en", "Test that english loads as the default.");
        IT.addLanguage(otherLanguageName);
        
        var updatedLangs = IT.getLanguages();
        ok(updatedLangs.length === 2, "Test adding language updates model");
        ok(updatedLangs.indexOf("en") !== -1, "Test that default language still present.");
        ok(IT.getDefaultLanguage() === "en", "Test that default language still the default.");
        ok(updatedLangs.indexOf("sw") !== -1, "Test that new language properly added.");
        
        IT.setDefaultLanguage(otherLanguageName);
        equal(IT.getDefaultLanguage(), otherLanguageName, "Test that default language updates default");

        IT.removeLanguage("sw");
        updatedLangs = IT.getLanguages();
        ok(updatedLangs.length === 1, "Test removing language updates model");
        ok(updatedLangs.indexOf("sw") === -1, "Test that new language properly removed.");
        ok(updatedLangs.indexOf("en") !== -1, "Test that other language still present after removal.");
        ok(IT.getDefaultLanguage() === "en", "Test that default language switches after deleting the default.");
        
        start();
    });

        asyncTest("Crufty Itext Removal Controller Wrapper Func", function () {
                        resetVellumForUnitTests();
            var cleanForm = 'form0.xml';
            var cruftyForm = 'form_with_crufty_itext1.xml';

            var Itext = formdesigner.model.Itext;
            var c = formdesigner.controller;
            getFormFromServerAndPlaceInBuffer(cleanForm);
            cleanForm = testXformBuffer[cleanForm];
            getFormFromServerAndPlaceInBuffer(cruftyForm);
            cruftyForm = testXformBuffer[cruftyForm];

            var cleanIDs = ["question1", "question2", "question3", "question4", "question5"];
            
            var crufyIDs = ["question1", "question2", "question3", "question4", "question5",
                            "cough", "TB_positive", "fever", "skin_infection", "wound_infection", "hiv_positive", "BP", 
                            "diabetes", "danger_sign_preg_mother", "preg_mother-TT", "preg_mother-ante_natal", "birth_registration"];

            //Test the clean form

            c.loadXForm(cruftyForm);
            window.setTimeout(function () {
                start();
                c.removeCruftyItext();
                same(Itext.getNonEmptyItemIds(), cleanIDs, "Controller function for UI for cleaning out Crufty Itext produces correct results");

            },700);

        });



        asyncTest("Test default language setting", function () {
            var form = 'form_with_3_languages.xml';
            resetVellumForUnitTests();
            var Itext = formdesigner.model.Itext;
            var c = formdesigner.controller;
            getFormFromServerAndPlaceInBuffer(form);
            form = testXformBuffer[form];

            //Test the clean form
            c.loadXForm(form);

            window.setTimeout(function () {
                start();
                equal(Itext.getDefaultLanguage(), 'th', "Default Language was correctly set to 'th'");
                Itext.setDefaultLanguage('sw');
                equal(Itext.getDefaultLanguage(), 'sw', "Default Language was correctly set to 'sw'");
            },777);
            
            
        });

        asyncTest("Test default language by using external language list init option", function () {

            var form = 'form_with_3_languages.xml';
            var Itext = formdesigner.model.Itext;
            var c = formdesigner.controller;
            var xmlString, opts = {};
            getFormFromServerAndPlaceInBuffer(form);
            form = testXformBuffer[form];
            //fake the mechanism by which options are usually passed in by the launcher see formdesigner.launch() in ui.js
            opts.langs = ["sw", "th", "en"];
            formdesigner.opts = opts;
            resetVellumForUnitTests(opts);
            c.loadXForm(form);

            window.setTimeout(function () {

                equal(Itext.getDefaultLanguage(), 'sw', "Default Language was correctly set to 'sw' at parse time");
                equal(formdesigner.currentItextDisplayLanguage, 'sw', "Is the display language set to 'sw'?");

                xmlString = c.form.createXForm();
                validateFormWithJR(xmlString, validateCallbackFunc('Default Language Init w sw'));
                
                var grepVal = grep(xmlString,"default=").trim();
                equal(grepVal, '<translation lang="sw" default="">', "default attr was correctly set");


                start();

            },777);
        });






    module("Create XForm XML");
    asyncTest("Create simple flat Xform", function () {
        stop()
        var c = formdesigner.controller,
                ui = formdesigner.ui,
                jstree = $("#fd-question-tree"),
                curMugType,
                addQbut;
        resetVellumForUnitTests();
        start()
        addQbut = $('#fd-add-but');
        addQbut.click();
        addQbut.click();
        addQbut.click();
        addQbut.click();
        addQbut.click();
        formdesigner.formUuid = 'http://openrosa.org/formdesigner/1B27BC6C-D6B2-43E2-A36A-050DBCAF4763';
        var actual = beautifyXml(c.form.createXForm());
        getFormFromServerAndPlaceInBuffer('form0.xml');

        var expected = beautifyXml(testXformBuffer['form0.xml']);
        equal(expected,actual);
        start();
    });

    asyncTest("Create simple nested Xform", function () {
        var c = formdesigner.controller,
            ui = formdesigner.ui,
            jstree = $("#fd-question-tree"),
            curMugType, Itext,
            addQbut, lastCreatedNode, addGroupBut, qTypeSel;
        resetVellumForUnitTests();

        Itext = formdesigner.model.Itext;

        jstree.bind('create_node.jstree',function(e,data){
            lastCreatedNode = data.rslt.obj;
        })
        addQuestionThroughUI("Text Question");
        jstree.jstree('select_node',lastCreatedNode);
        curMugType = formdesigner.controller.form.controlTree.getMugTypeFromUFID(lastCreatedNode.attr('id'));
        $('#dataElement-nodeID').val('question1').keyup();
        $('#controlElement-labelItextID').val('question1').keyup();
        curMugType.mug.properties.controlElement.properties.labelItextID.setDefaultValue('question1 label');

        addQuestionThroughUI("Group");
        jstree.jstree('select_node',lastCreatedNode,true);

        // change node id and itext id
        $('#dataElement-nodeID').val('group1').keyup();
        $('#controlElement-labelItextID').val('group1').keyup();
        
        curMugType = formdesigner.controller.form.controlTree.getMugTypeFromUFID(lastCreatedNode.attr('id'));
        curMugType.mug.properties.controlElement.properties.labelItextID.setDefaultValue('group label');
        addQuestionThroughUI("Text Question");
        jstree.jstree('select_node',lastCreatedNode,true);
        // change node id and itext id
        $('#dataElement-nodeID').val('question2').keyup();
        $('#controlElement-labelItextID').val('question2').keyup();
        curMugType = formdesigner.controller.form.controlTree.getMugTypeFromUFID(lastCreatedNode.attr('id'));
        curMugType.mug.properties.controlElement.properties.labelItextID.setDefaultValue('question2 label');
        formdesigner.formUuid = "http://openrosa.org/formdesigner/5EACC430-F892-4AA7-B4AA-999AD0805A97";    
        var actual = beautifyXml(c.form.createXForm());
        validateFormWithJR(actual, validateCallbackFunc('Simple Nested Form Actual 1'));

        getFormFromServerAndPlaceInBuffer('form1.xml');
        var expected = beautifyXml(testXformBuffer['form1.xml']);
        validateFormWithJR(expected, validateCallbackFunc('form1.xml'));
        validateFormWithJR(actual, validateCallbackFunc('Simple Nested Form Actual 2'));
        equal(expected,actual);

        //test if form is valid
        ok(formdesigner.controller.form.isFormValid(), 'Form Should pass all Validation Tests');
        start();
                

    });

    asyncTest("Test Form Validation function", function () {
        var c = formdesigner.controller,
            ui = formdesigner.ui,
            jstree = $("#fd-question-tree"),
            curMugType,
            lastCreatedNode;
        resetVellumForUnitTests();

        jstree.bind('create_node.jstree',function(e,data){
            lastCreatedNode = data.rslt.obj;
        })
        addQuestionThroughUI("Text Question");
        addQuestionThroughUI("Text Question");
        addQuestionThroughUI("Group");
        jstree.jstree('select_node',lastCreatedNode,true);
        addQuestionThroughUI("Text Question");

        equal(formdesigner.controller.form.isFormValid(), true, 'Form should be valid.');
        start();

    });

    asyncTest("Test getMTbyDataNodeID function", function ()  {
        var c = formdesigner.controller,
            ui = formdesigner.ui,
            jstree = $("#fd-question-tree"),
            mugType,
            ufid1,ufid2,
            lastCreatedNode;
        resetVellumForUnitTests();
        jstree.bind('create_node.jstree',function(e,data){
            lastCreatedNode = data.rslt.obj;
        })
        addQuestionThroughUI("Text Question");
        ufid1 = $(lastCreatedNode).attr('id');
        addQuestionThroughUI("Text Question");
        ufid2 = $(lastCreatedNode).attr('id');

        mugType = c.getMTFromFormByUFID(ufid2);
        deepEqual([mugType], c.form.getMugTypeByIDFromTree(mugType.mug.properties.dataElement.properties.nodeID, 'data'), 'MugTypes should be the same')
        equal(0, c.form.getMugTypeByIDFromTree('foo', 'data').length, 'Given a bogus ID should return an empty list');
        start();
    });

    module("Parsing tests");
    asyncTest("Replacing MugTypes in a tree", function () {
        getFormFromServerAndPlaceInBuffer('form1.xml');
        var xmlDoc = $.parseXML(testXformBuffer['form1.xml']),
            xml = $(xmlDoc),
            binds = xml.find('bind'),
            data = xml.find('instance').children(),
            formID, formName, lastCreatedNode,
            c ,replaceSuccess,
            jstree = $("#fd-question-tree");
        resetVellumForUnitTests();
        c = formdesigner.controller;
        var mType = formdesigner.util.getNewMugType(formdesigner.model.mugTypes.dataBind),
        mug = formdesigner.model.createMugFromMugType(mType),
        oldMT;

        jstree.bind('create_node.jstree',function(e,data){
            lastCreatedNode = data.rslt.obj;
        });

        addQuestionThroughUI("Text Question");
        oldMT = formdesigner.controller.form.getMugTypeByIDFromTree('question2', 'data')[0];
        replaceSuccess = c.form.replaceMugType(oldMT,mType,'data');
        mType.mug = mug;
        mType.mug.properties.dataElement.properties.nodeID = 'HYAAA';
        mType.ufid = oldMT.ufid;


        ok(replaceSuccess, "Replace Operation was succesful");
        equal(formdesigner.controller.form.getMugTypeByIDFromTree('HYAAA', 'data')[0], mType, "mug replacement worked");

        start();
    });

    function getMTFromControlTree(el) {
        return formdesigner.controller.form.controlTree.getMugTypeFromUFID(el.attr('id'));
    }

    function getMTFromDataTree(el) {
        return formdesigner.controller.form.dataTree.getMugTypeFromUFID(el.attr('id'));
    }

    module("UI Tests");
    test ("'Remove Selected' button", function () {
        var c = formdesigner.controller,
            ui = formdesigner.ui,
            jstree = $("#fd-question-tree"),
            curMugType,
            addQbut, lastCreatedNode, addGroupBut, qTypeSel, iiD, groupMT, Itext,mugProps,cEl,iID;
        resetVellumForUnitTests();
        jstree.bind('create_node.jstree',function(e,data){
            lastCreatedNode = data.rslt.obj;
        })

        //build form
        addQuestionThroughUI("Text Question");
        jstree.jstree('select_node',lastCreatedNode);
        curMugType = getMTFromControlTree(lastCreatedNode);
        mugProps = curMugType.mug.properties;
        cEl = mugProps.controlElement.properties;
        iID = cEl.labelItextID;
        iID.id = "question1";
        iID.setDefaultValue('question1 label');
        //add group
        addQuestionThroughUI("Group");
        jstree.jstree('select_node',lastCreatedNode,true);
        curMugType = getMTFromControlTree(lastCreatedNode);
        groupMT = curMugType;
        mugProps = curMugType.mug.properties;
        cEl = mugProps.controlElement.properties;
        iID = cEl.labelItextID;
        //set itext value for group
        iID.setDefaultValue('group1 label'); 
        //change the group's nodeIDs to something more reasonable
        $('#dataElement-nodeID').val('group1').keyup(); 
        
        
        //add another text question
        addQuestionThroughUI("Text Question");
        jstree.jstree('select_node',lastCreatedNode,true);
        curMugType = getMTFromControlTree(lastCreatedNode);
        mugProps = curMugType.mug.properties;
        cEl = mugProps.controlElement.properties;
        iID = cEl.labelItextID;
        iID.setDefaultValue('question2 label');

        //select the group node
        jstree.jstree('select_node',$('#'+ groupMT.ufid),true);

        //remove it
        $('#fd-remove-button').click();

        //test if form is valid
        ok(formdesigner.controller.form.isFormValid(), 'Form Should pass all Validation Tests');

        //compare with form we have in the testing cache.
        formdesigner.formUuid = "http://openrosa.org/formdesigner/E9BE7934-687F-4C19-BDB7-9509005460B6";
        var actual = c.form.createXForm();
        validateFormWithJR(actual, validateCallbackFunc('Remove Selected 1'));
        actual = beautifyXml(actual);
        getFormFromServerAndPlaceInBuffer('form8.xml');
        var expected = beautifyXml(testXformBuffer['form8.xml']);
        equal(actual,expected);
        start();

    })

    asyncTest("Input fields", function() {
        var c = formdesigner.controller,
                    ui = formdesigner.ui,
                    jstree = $("#fd-question-tree"),
                    curMugType,
                    addQbut, lastCreatedNode, addGroupBut, qTypeSel, iiD, groupMT, Itext,mugProps,cEl,iID,
                    workingField;
        resetVellumForUnitTests();

//        start();
        Itext = formdesigner.model.Itext;

        jstree.bind('create_node.jstree',function(e,data){
            lastCreatedNode = data.rslt.obj;
        })


        var xmlString;
        //build form
        addQuestionThroughUI("Text Question");

        //change form name and test results
        workingField = $("#fd-form-prop-formName-input");
        workingField.val("My Test Form");
        triggerKeyEvents(workingField,32,false,false);
        triggerKeyEvents(workingField,8,false,false);
        xmlString = c.form.createXForm();
        validateFormWithJR(xmlString, validateCallbackFunc('Input Selector 1'));
        var xml = parseXMLAndGetSelector(xmlString);
        var title = xml.find("h\\:title");
        if(title.length === 0) {
            title = xml.find("title");
        }
        equal(title.length, 1, "Should have found the title node in generated source");
        equal(title.text(), "My Test Form", "Form title has been set correctly");

        //change form data node name and test results
        workingField = $('#fd-form-prop-formID-input');
        workingField.val('mydatanode');
        triggerKeyEvents(workingField,32,false,false);
        triggerKeyEvents(workingField,8,false,false);
        xmlString = c.form.createXForm();
        xml = parseXMLAndGetSelector(xmlString);
        validateFormWithJR(xmlString, validateCallbackFunc('Input Selector 2'));

        var dataNode = $(xml.find('instance').children()[0]);
        equal(dataNode.length, 1, 'found data node in xml source');
        equal(dataNode[0].tagName, "mydatanode", "Data node is named correctly");
        workingField.val("My Data Node");
        triggerKeyEvents(workingField,32,false,false);
        triggerKeyEvents(workingField,8,false,false); //test auto replace of ' ' with '_'
        xmlString = c.form.createXForm();
        xml = parseXMLAndGetSelector(xmlString);
        validateFormWithJR(xmlString, validateCallbackFunc('Input Selector 3'));
        formdesigner.temp = xml;
        equal(workingField.val(), "My_Data_Node", "field value correctly swapped ' ' for '_'");
        var dataNode = $(xml.find('instance').children()[0]);
        equal(dataNode.length, 1, 'found data node in xml source');
        equal(dataNode[0].tagName, "My_Data_Node", "Data node with spaces is named correctly");
        


        curMugType = getMTFromControlTree($(lastCreatedNode));
        ui.selectMugTypeInUI(curMugType);
        equal(curMugType.typeName, "Text Question", "Is Question created through UI a text type question?");
        workingField = $('#dataElement-nodeID');
        workingField.val("textQuestion1").keyup();
        triggerKeyEvents(workingField,32,false,false);
        triggerKeyEvents(workingField,8,false,false);
        xmlString = c.form.createXForm();
        validateFormWithJR(xmlString, validateCallbackFunc('Input Selector 4'));
        equal(curMugType.mug.properties.dataElement.properties.nodeID, "textQuestion1", "dataElement nodeID set correctly");
        equal(curMugType.mug.properties.bindElement.properties.nodeID, "textQuestion1", "bindElement nodeID set correctly");
        xml = parseXMLAndGetSelector(xmlString);
        validateFormWithJR(xmlString, validateCallbackFunc('Input Selector 5'));

        //set Default Value
        workingField = $('#dataElement-dataValue');
        workingField.val('Some Data Value String');
        triggerKeyEvents(workingField,32,false,false);
        triggerKeyEvents(workingField,8,false,false);
        xmlString = c.form.createXForm();
        validateFormWithJR(xmlString, validateCallbackFunc('Input Selector 5'));
        xml = parseXMLAndGetSelector(xmlString);
        var defaultValueXML = xml.find('My_Data_Node').children('textQuestion1').text();
        equal(defaultValueXML, "Some Data Value String", "default value set in UI corresponds to that generated in XML");

        workingField = $('#bindElement-relevantAttr');
        workingField.val("/data/bleeding_sign = 'N'").keyup();
        xmlString = c.form.createXForm();
        validateFormWithJR(xmlString, validateCallbackFunc('Input Selector 6'));
        xml = parseXMLAndGetSelector(xmlString);
        var bindRelVal = $(xml.find('bind')[0]).attr('relevant');
        equal(bindRelVal, "/data/bleeding_sign = 'N'", 'Was relevancy condition set correctly in the UI?');

        workingField.val("/data/bleeding_sign >= 5 or /data/bleeding_sing < 21").keyup();
        xmlString = c.form.createXForm();
        validateFormWithJR(xmlString, validateCallbackFunc('Input Selector 7'));
        xml = parseXMLAndGetSelector(xmlString);
        var bindVal = grep(xmlString,"<bind").trim();
        var expected = '<bind nodeset="/My_Data_Node/textQuestion1" type="xsd:string" relevant="/data/bleeding_sign &gt;= 5 or /data/bleeding_sing &lt; 21" />'
        equal(bindVal, expected, 'Was relevancy condition with < or > signs rendered correctly in the UI?');

        workingField = $('#bindElement-calculateAttr');
        workingField.val("/data/bleeding_sign >= 5 or /data/bleeding_sing < 21");
        triggerKeyEvents(workingField,32,false,false);
        triggerKeyEvents(workingField,8,false,false);
        xmlString = c.form.createXForm();
        validateFormWithJR(xmlString, validateCallbackFunc('Input Selector 8'));
        xml = parseXMLAndGetSelector(xmlString);
        bindVal = grep(xmlString,"<bind").trim();
        expected = '<bind nodeset="/My_Data_Node/textQuestion1" type="xsd:string" relevant="/data/bleeding_sign &gt;= 5 or /data/bleeding_sing &lt; 21" calculate="/data/bleeding_sign &gt;= 5 or /data/bleeding_sing &lt; 21" />'
        equal(bindVal, expected, 'Was calculate condition with < or > signs rendered correctly in the UI?');

        workingField = $('#bindElement-constraintAttr');
        workingField.val("/data/bleeding_sign >= 5 or /data/bleeding_sing < 21");
        triggerKeyEvents(workingField,32,false,false);
		triggerKeyEvents(workingField,8,false,false);
        xmlString = c.form.createXForm();
        validateFormWithJR(xmlString, validateCallbackFunc('Input Selector 9'));
        xml = parseXMLAndGetSelector(xmlString);
        bindVal = grep(xmlString,"<bind").trim();
        expected = '<bind nodeset="/My_Data_Node/textQuestion1" type="xsd:string" constraint="/data/bleeding_sign &gt;= 5 or /data/bleeding_sing &lt; 21" relevant="/data/bleeding_sign &gt;= 5 or /data/bleeding_sing &lt; 21" calculate="/data/bleeding_sign &gt;= 5 or /data/bleeding_sing &lt; 21" />'
        equal(bindVal, expected, 'Was validation condition with < or > signs rendered correctly in the UI?');
        workingField.val('');
		triggerKeyEvents(workingField,32,false,false);
		triggerKeyEvents(workingField,8,false,false);
        workingField = $('#bindElement-calculateAttr');
        workingField.val('');
		triggerKeyEvents(workingField,32,false,false);
		triggerKeyEvents(workingField,8,false,false);
        workingField = $('#bindElement-relevantAttr');
        workingField.val('');
		triggerKeyEvents(workingField,32,false,false);
		triggerKeyEvents(workingField,8,false,false);

        workingField = $('#bindElement-requiredAttr');
        workingField.click(); //check the 'required' checkbox;
        xmlString = c.form.createXForm();
        validateFormWithJR(xmlString, validateCallbackFunc('Input Selector 10'));
        xml = parseXMLAndGetSelector(xmlString);
        var requireAttr = xml.find('bind').attr('required');
        expected = "true()";
        equal(requireAttr,expected,"Is the required attribute value === 'true()' in the bind?");

        workingField = $('#itext-en-text-default');
        workingField.val("Question 1 Itext yay").keyup();
		xmlString = c.form.createXForm();
        validateFormWithJR(xmlString, validateCallbackFunc('Input Selector 11'));
        xml = parseXMLAndGetSelector(xmlString);
        var itextVal = xml.find('translation #'+ $('#controlElement-labelItextID').val()).children('value').text();
        expected = "Question 1 Itext yay";
        equal(itextVal,expected,"Has default Itext been set correctly through UI?");

        workingField = $('#bindElement-constraintMsgAttr');
        workingField.val("Some default jr:constraintMsg value");
		triggerKeyEvents(workingField,32,false,false);
		triggerKeyEvents(workingField,8,false,false);
        xmlString = c.form.createXForm();
        validateFormWithJR(xmlString, validateCallbackFunc('Input Selector 16'));
        xml = parseXMLAndGetSelector(xmlString);
        bindVal = grep(xmlString,"<bind").trim();
        expected = '<bind nodeset="/My_Data_Node/textQuestion1" type="xsd:string" jr:constraintMsg="Some default jr:constraintMsg value" required="true()" />';
        equal(bindVal, expected, 'Was constraint Message correctly set?');


        workingField = $('#controlElement-hintLabel');
        workingField.val("Default Hint Label Value");
		triggerKeyEvents(workingField,32,false,false);
		triggerKeyEvents(workingField,8,false,false);
        xmlString = c.form.createXForm();
        validateFormWithJR(xmlString, validateCallbackFunc('Input Selector 17'));
        xml = parseXMLAndGetSelector(xmlString);
        window.xmlString = xml;
        var someval = xml.find('input').children('hint').text()
        expected = "Default Hint Label Value";
        equal(someval,expected,"Has default hint label been set correctly through UI?");

        workingField = $('#controlElement-hintItextID');
        workingField.val("question1_hint").keyup();
		xmlString = c.form.createXForm();
        xml = parseXMLAndGetSelector(xmlString);
        window.xmlString = xml;
        someval = xml.find('input').children('hint').attr('ref');
        expected = "jr:itext('question1_hint')";
        equal(someval,expected,"Has hint Itext ID been set correctly through UI?");

        // TODO: still broken, determine expected behavior
        workingField = $('#itext-en-hint-default');
        workingField.val("Question 1 Itext hint").keyup();
		xmlString = c.form.createXForm();
        validateFormWithJR(xmlString, validateCallbackFunc('Input Selector 18'));
        xml = parseXMLAndGetSelector(xmlString);
        var findstring = '';
        if($('#controlElement-hintItextID').val()) {
            findstring = '[id='+$('#controlElement-hintItextID').val()+']';
        }
        itextVal = xml.find('translation').find(findstring).children('value').text()
        expected = "Question 1 Itext hint";
        equal(itextVal,expected,"Has hint Itext been set correctly through UI?");
        start();

    });

    asyncTest("DataType selector functionality", function() {
        var c = formdesigner.controller,
                    ui = formdesigner.ui,
                    jstree = $("#fd-question-tree"),
                    curMugType,
                    addQbut, lastCreatedNode, addGroupBut, qTypeSel, iiD, groupMT, Itext,mugProps,cEl,iID,
                    workingField;
        resetVellumForUnitTests();


        Itext = formdesigner.model.Itext;

        jstree.bind('create_node.jstree',function(e,data){
            lastCreatedNode = data.rslt.obj;
        });

        var xmlString, xml;
        //build form
        addQuestionThroughUI("Text Question");
        addQuestionThroughUI("Group");
        curMugType = getMTFromControlTree($(lastCreatedNode));
        ui.selectMugTypeInUI(curMugType);
        addQuestionThroughUI("Integer Number");
        curMugType = getMTFromControlTree($(lastCreatedNode));
        ui.selectMugTypeInUI(curMugType);
        equal($('#bindElement-dataType').val(), 'xsd:int');
        equal(curMugType.mug.properties.bindElement.properties.dataType, 'xsd:int');

        xmlString = c.form.createXForm();
        validateFormWithJR(xmlString, validateCallbackFunc('DataType Selector 1'));
        xml = parseXMLAndGetSelector(xmlString);
        window.xmlSring = xml;
        var el = xml.find('[nodeset*='+curMugType.mug.properties.bindElement.properties.nodeID+']')
        equal($(el).attr('type'), 'xsd:int');


        addQuestionThroughUI("Double Number");
        curMugType = getMTFromControlTree($(lastCreatedNode));
        ui.selectMugTypeInUI(curMugType);
        equal($('#bindElement-dataType').val(), 'xsd:double');
        equal(curMugType.mug.properties.bindElement.properties.dataType, 'xsd:double');
        xmlString = c.form.createXForm();
        validateFormWithJR(xmlString, validateCallbackFunc('DataType Selector 2'));
        xml = parseXMLAndGetSelector(xmlString);
        window.xmlSring = xml;
        el = xml.find('[nodeset*='+curMugType.mug.properties.bindElement.properties.nodeID+']')
        equal($(el).attr('type'), 'xsd:double');
        equal(curMugType.mug.properties.bindElement.properties.dataType, 'xsd:double');

        addQuestionThroughUI("Long Number");
        curMugType = getMTFromControlTree($(lastCreatedNode));
        ui.selectMugTypeInUI(curMugType);
        equal($('#bindElement-dataType').val(), 'xsd:long');
        equal(curMugType.mug.properties.bindElement.properties.dataType, 'xsd:long');

        xmlString = c.form.createXForm();
        validateFormWithJR(xmlString, validateCallbackFunc('DataType Selector 3'));
        xml = parseXMLAndGetSelector(xmlString);
        window.xmlSring = xml;
        el = xml.find('[nodeset*='+curMugType.mug.properties.bindElement.properties.nodeID+']')
        equal($(el).attr('type'), 'xsd:long');

        addQuestionThroughUI("Password Question");
        curMugType = getMTFromControlTree($(lastCreatedNode));
        ui.selectMugTypeInUI(curMugType);
        equal($('#bindElement-dataType').val(), 'xsd:string');
        equal(curMugType.mug.properties.bindElement.properties.dataType, 'xsd:string');
        equal(curMugType.typeName, "Password Question");
        equal(curMugType.mug.properties.controlElement.properties.name, "Secret");
        xmlString = c.form.createXForm();
        validateFormWithJR(xmlString, validateCallbackFunc('DataType Selector 4'));
        xml = parseXMLAndGetSelector(xmlString);
        window.xmlSring = xml;
        el = xml.find('secret');
        equal($(el).length,1);
        equal($(el).tagName);
        el = xml.find('[nodeset*='+curMugType.mug.properties.bindElement.properties.nodeID+']');
        equal($(el).attr('type'), 'xsd:string');
        start();


    });

    module("Parsing Tests Part II");
    asyncTest("Parse Error Messages Functionality", function () {
        var c = formdesigner.controller,
            ui = formdesigner.ui,
            jstree = $("#fd-question-tree"),
            curMugType,
            addQbut, lastCreatedNode, addGroupBut, qTypeSel, iiD, groupMT, Itext,mugProps,cEl,iID,
                sourceDrop, parseButton, pErrors, expectedErrors, myxml;
        resetVellumForUnitTests();


        getFormFromServerAndPlaceInBuffer('form_with_no_data_attrs.xml');
        myxml = testXformBuffer["form_with_no_data_attrs.xml"];
        c.loadXForm(myxml); //load the xform using the standard pathway in the FD for parsing forms
        window.setTimeout(function () {
            expectedErrors = [
                "Form does not have a unique xform XMLNS (in data block). Will be added automatically",
                "Form JRM namespace attribute was not found in data block. One will be added automatically",
                "Form does not have a UIVersion attribute, one will be generated automatically",
                "Form does not have a Version attribute (in the data block), one will be added automatically",
                "Form does not have a Name! The default form name will be used"
            ];
            start();
            deepEqual(c.parseWarningMsgs, expectedErrors, "Do the correct warnings get generated for a form with no data block attributes?");
        }, 1000);

    });

    module("Utilities tests");
    test("Check XML Element Validation Function", function () {
        var fdutil = formdesigner.util;
        
        var goodNames = ["textOnly", "textWithSomeNumbers123", "hyphenated-string",
                         "underscored_string", "CapsFirst", "XMok", "xmok", 
                         "a_bit-ofEv3ryth1ng"];
        var badNames = ["1startswithnumber", "has spaces", "illegalChar$",
                        "illegalChar.", "illegalChar!", "illegalChar'",
                        'illegalChar"', "illegalChar?", "illegalChar*",
                        "XMLisAnIllegalStartString", "-startsWithHyphen",
                        "_startsWithUnderscore"];
        var i;
        for (i = 0; i < goodNames.length; i++) {
            ok(fdutil.isValidElementName(goodNames[i]), goodNames[i] + " is considered a valid xml element");
        }
        for (i = 0; i < badNames.length; i++) {
            ok(!fdutil.isValidElementName(badNames[i]), badNames[i] + " is considered an invalid xml element");
        }
        
    });

    test("Check XML String Quoting Function", function () {
        var fdutil = formdesigner.util;
        equal(fdutil.escapeQuotedXML("foo < bar"), "foo &lt; bar", "Less than signs escape.");
        equal(fdutil.escapeQuotedXML("foo > bar"), "foo &gt; bar", "Greater than signs escape.");
        equal(fdutil.escapeQuotedXML('foo " bar'), "foo &quot; bar", "Quotes escape.");
        equal(fdutil.escapeQuotedXML('foo " bar', {escapeQuotes: false}), 'foo " bar', 
              "Options can override escape quote behavior.");
        equal(fdutil.escapeQuotedXML('foo & bar'), "foo & bar", "Ampersands don't escape.");
        equal(fdutil.escapeQuotedXML('foo & bar', {escapeAmpersands: true}), "foo &amp; bar", 
              "Options can override escape ampersand behavior.");
        equal(fdutil.escapeQuotedXML("foo ' bar"), "foo ' bar", "Apostrophes don't escape.");
        equal(fdutil.escapeQuotedXML("foo ' bar", {escapeApostrophes: true}), "foo &apos; bar", 
              "Options can override escape apostrophe behavior.");
        equal(fdutil.escapeQuotedXML("foo & bar < baz", {escapeAmpersands: true}), "foo &amp; bar &lt; baz", 
              "Order of operations doesn't break apostrophes.");
        
    });


    module("Tests created upon bug submission");
    test("Create a data node", function () {
        var c = formdesigner.controller,
        ui = formdesigner.ui,curMugType,
                addQbut, lastCreatedNode, addGroupBut, qTypeSel, iiD, groupMT, Itext,mugProps,cEl,iID,
                workingField, jstree;

        resetVellumForUnitTests();


        Itext = formdesigner.model.Itext;

        jstree = $("#fd-question-tree");

        jstree.bind('create_node.jstree',function(e,data){
            lastCreatedNode = data.rslt.obj;
        });

        addQuestionThroughUI("Data Node");
        curMugType = getMTFromDataTree($(lastCreatedNode));
        ui.selectMugTypeInUI(curMugType);
        ok(curMugType,'Data Node Exists');
    });





    

    //Disabling these tests until I can figure out what the hell is wrong with them.
//    module("In Out In XForm Tests");
//
//         var c = formdesigner.controller,
//            ui = formdesigner.ui,
//            jstree = $("#fd-question-tree"),
//            output, myxml = {}, i=0, k=0, prettyTreeBefore = [], prettyTreeAfter = [],
//            PARSE_SUCCESS = true;
//
//        formdesigner.controller.on('parse-error', function (d) {
//            PARSE_SUCCESS = false;
//            console.error(d.exceptionData);
//            throw 'Parse Error! :' + d.exceptionData;
//
//        });
//
//        for (k in testFormNames) {
//            asyncTest("Test form: " + testFormNames[k], (function(i) {
//                return function () {
//
//                    var myform;
//                    get_cchq_forms(testFormNames[i]);
//                    myform = testXformBuffer['fromcchq/' + testFormNames[i]];
//                    resetVellumForUnitTests();
//                    c.loadXForm(myform);             //parse
//                    prettyTreeBefore[0] = formdesigner.controller.form.controlTree.printTree();
//                    prettyTreeBefore[1] = formdesigner.controller.form.dataTree.printTree();
//                    output = c.form.createXForm();  //generate form with FD
//                    validateFormWithJR(output, validateCallbackFunc('Iteration:' + i));     //validate
//
//                    c.loadXForm(output);            //parse the newly generated form
//                    prettyTreeAfter[0] = formdesigner.controller.form.controlTree.printTree();
//                    prettyTreeAfter[1] = formdesigner.controller.form.dataTree.printTree();
//                    output = c.form.createXForm();  //generate resulting XForm again
//                    validateFormWithJR(output, validateCallbackFunc('Iteration 2nd:' + i));     //Validate again
//
//                    equal(prettyTreeBefore[0], prettyTreeAfter[0], "Internal controlTree should be the same at all times");
//                    equal(prettyTreeBefore[1], prettyTreeAfter[1], "Internal dataTree should be the same at all times");
//                    ok(PARSE_SUCCESS, "PARSING PROBLEM");
//                    start();
//                }
//            }(k)));
//
//        }




});



var asyncRes = [], testData = [], len = -1;
formdesigner.asyncRes = asyncRes;
formdesigner.testData = testData;
/**
 * Actual is the xml form string
 * @param actual
 */
function validateFormWithJR(actual, successFunc, name) {
    if(typeof name === undefined){
        name = '';
    }
    if(!JRVALIDATE_MODE){
        return true;
    }

    if (!successFunc) {
        successFunc = validateCallbackFunc(name);
    }
    stop();

//        $.ajaxSetup({"async": false});
    $.post('/formtranslate/validate/',{xform: actual},successFunc);
}

function resetVellumForUnitTests(opts) {
    if (opts) {
        formdesigner.opts = opts;
    } else {
        formdesigner.opts = {};
    }
    formdesigner.controller.resetFormDesigner();
    if (!formdesigner.opts.langs) {
        formdesigner.opts.allowLanguageEdits = true;
        formdesigner.model.Itext.addLanguage("en"); //add a starting language
        formdesigner.model.Itext.setDefaultLanguage("en");
    }
}

function parseXMLAndGetSelector(xmlString) {

    var xmlDoc = $.parseXML(xmlString),
                xml = $(xmlDoc);
    return xml;
}

function divide(a,b){
    return a/b;
}

function grep(xmlString, matchStr) {
    var lines,i;
    lines = xmlString.split(/\n/g);
    for (i in lines) {
        if(lines[i].match(matchStr)) {
            return lines[i];
        }
    }
    return null;
}