function truncateLabel(label) {
    var MAXLEN = 40;
    return (label.length <= MAXLEN) ? (label) : (label.slice(0, MAXLEN) + "...");
}

function escapeQuotes(string){
    return string.replace("'", "&apos;").replace("\"", "&quot;");
}

function action_is_active(action) {
    return action && action.condition && action.condition.type in {'if': true, 'always': true};
}

CaseXML = (function(){
    function CaseXML(params) {
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
        this.action_templates = {};
        for(var a in this.actions) {
            if(a == "doc_type") continue;
            this.action_templates[a] = new EJS({url: "/static/app_manager/ejs/actions/" + a + ".ejs", type: "["});
        }
        $("#casexml-template").remove();
    }
    //CaseXML.action_types = ["open_case", "update_case", "close_case", "open_referral", "update_referral", "close_referral"];
    CaseXML.prototype.render = (function(){
        var casexml = this;
        this.template.update(this.home, this);
        $("#requires_form [name='requires']").addClass('autosave');
        initBlock("#" + this.home);
        if(this.questions.length && this.edit) {
            $(".casexml").delegate('*', 'change', function(){
                // recompute casexml_json
                casexml.refreshActions();
                $("#casexml_json").text(JSON.stringify(casexml.actions));
                casexml.render();
            }).find('*').first();
        }
    });
    CaseXML.prototype.init = (function(){
        $("#casexml_json").hide();
        this.render();
    });

    CaseXML.prototype.renderCondition = (function(condition){
        return this.condition_ejs.render({casexml: this, condition: condition});;
    });
    CaseXML.prototype.getQuestions = (function(filter){
        // filter can be "all", or any of "select1", "select", or "input" separated by spaces
        filter = filter.split(" ");
        var options = [];
        for(var i in this.questions) {
            var q = this.questions[i];
            if(filter[0] == "all" || filter.indexOf(q.tag) != -1) {
                options.push(q);
            }
        }
        return options;
    });
    CaseXML.prototype.renderOptions = (function(options, value, name){
        return this.options_ejs.render({casexml: this, options: options, value: value, name: name});
    });
    CaseXML.prototype.renderQuestions = (function(filter) {
        var options = this.getQuestions(filter);
        var html = "";
        options.forEach(function(o){
            html += "<option value='" + o.value + "' title='" + escapeQuotes(o.label) + "'>" + truncateLabel(o.label) + "</option>";
        });
        return html;
    });
    CaseXML.prototype.getAnswers = (function(condition){
        var value = condition.question;
        var found = false;
        var options = [];
        for(var i in this.questions) {
            q = this.questions[i];
            if(q.value == value) {
                found = true;
                break;
            }
        }
        if(found){
            for(i in q.options) {
                o = q.options[i];
                options.push(o);
            }
        }
        return options;
    });
    CaseXML.prototype.renderChecked = (function(action){
        if(action_is_active(action)) {
            return 'checked="true"';
        }
        else {
            return "";
        }
    });

    CaseXML.prototype.refreshActions = (function(){
        var actions = {};
        function lookup(root, key){
            return $(root).find('[name="' + key + '"]').attr('value');
        }
        $(".casexml .action").each(function(){

            var $checkbox = $(this).find('input[type="checkbox"]');
            var id = $checkbox.attr('id').replace('-','_');

            if(!$checkbox.is(":checked")) {
                actions[id] = {};
                return;
            }

            var action = {};
            
            if(id=="update_case") {
                action.update = {};
                $('.action-update', this).each(function(){
                    var key = lookup(this, "action-update-key");
                    var val = lookup(this, "action-update-value");
                    if(key || val) {
                        action.update[key] = val;
                    }
                });
            }
            else if (id=="open_referral" || id=="open_case") {
                action.name_path = lookup(this, 'name_path');
            }
            else if (id=="update_referral") {
                action.followup_date = lookup(this, 'followup_date');
            }
            action.condition = {'type': 'always'}; // default value
            $('.condition', this).each(function(){ // there is only one
                action.condition = {};
//                if($checkbox.is(":checked")) {
//                    action.condition.type = "never";
//                }
                if($('input[name="if"]', this).is(':checked')) {
                    action.condition.type = "if";
                }
                else {
                    action.condition.type = 'always';
                }
                if(action.condition.type == 'if') {
                    action.condition.question = lookup(this, 'condition-question');
                    action.condition.answer = lookup(this, 'condition-answer');
                }
            });
            actions[id] = action;

        });
        this.actions = actions;
    });

    CaseXML.prototype.renderAction = (function(action_type, label){
        var html =  this.action_ejs.render({
            casexml: this,
            id: action_type.replace("_", "-"),
            action_type: action_type,
            label: label,
            action_body: this.action_templates[action_type].render(this)
        });
        return html;
    });
    CaseXML.prototype.hasActions = (function(){
        for(a in this.actions) {
            if(action_is_active(this.actions[a])) {
                return true;
            }
        }
    });

    return CaseXML;
})();