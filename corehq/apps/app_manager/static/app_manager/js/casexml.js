/*globals $, EJS, COMMCAREHQ */

var CaseXML = (function(){
    var action_names = ["open_case", "update_case", "close_case", "open_referral", "update_referral", "close_referral",
        "case_preload", "referral_preload"
    ];
    var CaseXML = function (params) {
        var i;
        this.home = params.home;
        this.actions = params.actions;
        this.questions = params.questions;
        this.edit = params.edit;
        this.save_url = params.save_url;
        this.requires = params.requires;
        this.save_requires_url = params.save_requires_url;
        this.template = new EJS({url:"/static/app_manager/ejs/casexml.ejs", type: "["});
        this.condition_ejs = new EJS({url:"/static/app_manager/ejs/condition.ejs", type: "["});
        this.action_ejs = new EJS({url: "/static/app_manager/ejs/action.ejs", type: "["});
        this.options_ejs = new EJS({url: "/static/app_manager/ejs/options.ejs", type: "["});
        this.propertyList_ejs = new EJS({url: "/static/app_manager/ejs/propertyList.ejs", type: "["});
        this.action_templates = {};
        this.reserved_words = params.reserved_words;
        for(i=0; i<action_names.length; i++) {
            this.action_templates[action_names[i]] = new EJS({url: "/static/app_manager/ejs/actions/" + action_names[i] + ".ejs", type: "["});
        }
        $("#casexml-template").remove();
    };
    CaseXML.prototype = {
        truncateLabel: function (label, suffix) {
            suffix = suffix || "";
            var MAXLEN = 40;
            var maxlen = MAXLEN - suffix.length;
            return ((label.length <= maxlen) ? (label) : (label.slice(0, maxlen) + "...")) + suffix;
        },
        escapeQuotes: function (string){
            return string.replace(/'/g, "&apos;").replace(/"/g, "&quot;");
        },
        action_is_active: function (action) {
            return action && action.condition && (action.condition.type === "if" || action.condition.type === "always");
        }
    };



    CaseXML.prototype.render = function(){
        var casexml = this;

        this.template.update(this.home, this);
        $("#requires_form [name='requires']").addClass('autosave');
        COMMCAREHQ.initBlock("#" + this.home);
        if(this.questions.length && this.edit) {
            $(".casexml").delegate('*', 'change', function(){
                // recompute casexml_json
                casexml.refreshActions();
                $("#casexml_json").text(JSON.stringify(casexml.actions));
                casexml.render();
            }).find('*').first();
        }
    };
    CaseXML.prototype.init = function(){
        this.render();
    };

    CaseXML.prototype.renderCondition = function(condition){
        return this.condition_ejs.render({casexml: this, condition: condition});
    };
    CaseXML.prototype.getQuestions = function(filter, excludeHidden){
        // filter can be "all", or any of "select1", "select", or "input" separated by spaces
        var i;
        excludeHidden = excludeHidden || false;
        filter = filter.split(" ");
        if (!excludeHidden) {
            filter.push('hidden');
        }
        var options = [];
        for(i=0; i < this.questions.length; i++) {
            var q = this.questions[i];
            if(filter[0] === "all" || filter.indexOf(q.tag) !== -1) {
                options.push(q);
            }
        }
        return options;
    };
    CaseXML.prototype.renderOptions = function(options, value, name, allowNull){
        if(allowNull === undefined) {allowNull = true;}
        return this.options_ejs.render({casexml: this, options: options, value: value, name: name, allowNull: allowNull});
    };
    CaseXML.prototype.renderQuestions = function(filter) {
        var options = this.getQuestions(filter);
        var html = "";
        options.forEach(function(o){
            html += "<option value='" + o.value + "' title='" + this.escapeQuotes(o.label) + "'>" + this.truncateLabel(o.label) + "</option>";
        });
        return html;
    };
    CaseXML.prototype.getAnswers = function(condition){
        var i, q, o;
        var value = condition.question;
        var found = false;
        var options = [];
        for(i=0; i < this.questions.length; i++) {
            q = this.questions[i];
            if(q.value === value) {
                found = true;
                break;
            }
        }
        if(found){
            for(i=0; i < q.options.length; i++) {
                o = q.options[i];
                options.push(o);
            }
        }
        return options;
    };
    CaseXML.prototype.renderChecked = function(action){
        if(this.action_is_active(action)) {
            return 'checked="true"';
        }
        else {
            return "";
        }
    };

    CaseXML.prototype.refreshActions = function(){
        var actions = {};
        function lookup(root, key){
            return $(root).find('[name="' + key + '"]').attr('value');
        }
        $(".casexml .action").each(function(){

            var $checkbox = $(this).find('input[type="checkbox"].action-checkbox');
            var id = $checkbox.attr('id').replace('-','_');

            var action = {"condition": {"type": "never"}};

            if(!$checkbox.is(":checked")) {
                actions[id] = action;
                return;
            }


            if(id === "open_case"){
                action.name_path = lookup(this, 'name_path');
                action.external_id = lookup(this, 'external_id');
            } else if(id === "update_case") {
                action.update = {};
                $('.action-update', this).each(function(){
                    var key = lookup(this, "action-update-key");
                    var val = lookup(this, "action-update-value");
                    if(key || val) {
                        action.update[key] = val;
                    }
                });
            } else if(id === "case_preload" || id === "referral_preload") {
                action.preload = {};
                $('.action-update', this).each(function(){
                    var propertyName = lookup(this, "action-update-key");
                    var nodeset = lookup(this, "action-update-value");
                    if(propertyName || nodeset) {
                        action.preload[nodeset] = propertyName;
                    }
                });
            } else if (id==="open_referral") {
                action.name_path = lookup(this, 'name_path');
                action.followup_date = lookup(this, 'followup_date');
            } else if (id==="update_referral") {
                action.followup_date = lookup(this, 'followup_date');
            }
            action.condition = {'type': 'always'}; // default value
            $('.condition', this).each(function(){ // there is only one
                // action.condition = {};
//                if($checkbox.is(":checked")) {
//                    action.condition.type = "never";
//                }
                if($('input[name="if"]', this).is(':checked')) {
                    action.condition.type = "if";
                }
                else {
                    action.condition.type = 'always';
                }
                if(action.condition.type === 'if') {
                    action.condition.question = lookup(this, 'condition-question');
                    action.condition.answer = lookup(this, 'condition-answer');
                }
            });
            actions[id] = action;

        });
        this.actions = actions;
    };

    CaseXML.prototype.renderAction = function (action_type, label){
        var html =  this.action_ejs.render({
            casexml: this,
            id: action_type.replace("_", "-"),
            action_type: action_type,
            label: label,
            action_body: this.action_templates[action_type].render(this)
        });
        return html;
    };
    CaseXML.prototype.hasActions = function (){
        var a;
        for(a in this.actions) {
            if(this.actions.hasOwnProperty(a)) {
                if(this.action_is_active(this.actions[a])) {
                    return true;
                }
            }
        }
    };

    CaseXML.prototype.renderPropertyList = function (map, keyType) {
        return this.propertyList_ejs.render({map: map, keyType: keyType, casexml: this});
    };

    return CaseXML;
}());