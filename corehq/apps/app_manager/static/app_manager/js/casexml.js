function initCondition() {
    $condition = $("#condition-template");
    $condition.removeAttr("id").remove();
    $('.casexml .action .config .condition').html($condition.html());
}
function truncateLabel(label) {
    var MAXLEN = 40;
    return (label.length <= MAXLEN) ? (label) : (label.slice(0, MAXLEN) + "...");
}
function makeConditionInteractive(questions) {
    $(".condition select[name='condition-question']").change(function(){
        var $answers = $(this).next("select[name='condition-answer']");
        $answers.html("");
        value = $(this).attr('value');
        found = false;
        for(i in questions) {
            q = questions[i];
            if(q.value == value) {
                found = true;
                break;
            }
        }
        if(found){
            $answers.show();
            for(i in q.options) {
                o = q.options[i];
                option = "<option value='" + o.value + "' title='" + o.label + "'>" +
                        truncateLabel(o.label)
                        + "</option>";
                $answers.append($(option));
            }
        }
    });
}
function escapeQuotes(string){
    return string.replace("'", "&apos;").replace("\"", "&quot;");
}
//function populateQuestions(questions) {
//    $("select.questions").each(function(){
//        //$answers = $(this).next("select[name='trigger_answer']");
//        //$answers.hide();
//        for(i in questions) {
//            q = questions[i];
//            if(($(this).hasClass("questions-all")) ||
//               ($(this).hasClass('questions-select1') && q.tag == "select1") ||
//               ($(this).hasClass('questions-select') && q.tag == "select") ||
//               ($(this).hasClass('questions-input') && q.tag == "input")) {
//                option = "<option value='" + q.value + "' title='" + escapeQuotes(q.label) + "'>" + truncateLabel(q.label) + "</option>";
//                $(this).append($(option));
//            }
//        }
//    });
//}

function add_update_row(){
    $new_row = initUpdateCase.template.clone();
    $new_row.addClass('action-update');
    $("#update-case-config").find('table').append($new_row);
}
function initUpdateCase() {
    $update_template = $("#action-update-template");
    $update_template.removeAttr("id").remove();
    initUpdateCase.template = $update_template;

    add_update_row();

    $('.casexml [name="action-update-value"]').live('change', function (){
        if($(this).closest('tr').is(':last-child')) {
            add_update_row();
        }
    });
}

function action_is_active(action) {
    return action && action.condition && action.condition.type in {'if': true, 'always': true};
}
function populateCasexmlForm(actions){
    //actions = JSON.parse(actions);

    for(a in actions) {
        action = actions[a];
        if(!action_is_active(action)) continue;
        id = a.replace('_', '-');
        $checkbox = $("#"+id);
        $action = $checkbox.parent();
        $checkbox.attr('checked', true).trigger('change');

        if(action.condition.type == 'if') {
            $if = $('.condition input[name="if"]', $action);
            $if.attr('checked', true).trigger('change');
            $('.condition [name="condition-question"]', $action).attr('value', action.condition.question).trigger('change');
            $('.condition [name="condition-answer"]', $action).attr('value', action.condition.answer);
        }

        if(a == 'update_case') {

            update = action.update;
            for(key in update) {
                val = update[key];
                $row = $('.action-update:last-child');
                $('[name="action-update-key"]', $row).attr('value', key);
                $('[name="action-update-value"]', $row).attr('value', val)
                        .trigger('change'); // create new row
            }
        }
        else if(a == "open_referral" || a == "open_case") {
            name_path = action.name_path;
            $('[name="name_path"]', $action).attr('value', name_path);
        }
        else if(a == "update_referral") {
            followup_date = action.followup_date;
            $('[name="followup_date"]', $action).attr('value', followup_date);
        }
    }
}
function get_actions() {
    return JSON.parse($("#casexml_json").text());
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
        $("#casexml-template").remove();
    }
    CaseXML.prototype.render = (function(){
        var casexml = this;
        this.template.update(this.home, this);
        initBlock("#" + this.home);
        initCondition();
        var questions = this.questions;
        if(questions.length) {
            //populateQuestions(questions);
            makeConditionInteractive(questions);
            //initUpdateCase();
            //populateCasexmlForm(this.actions);
            $(".casexml").delegate('*', 'change', function(){
                // recompute casexml_json
                casexml.refreshActions();
                $("#casexml_json").text(JSON.stringify(casexml.actions));
                casexml.render();
            }).find('*').first();
            $(".no-edit *").each(function(){
                if( ($(this).is('input[type="checkbox"]') && !$(this).is(":checked")) ||
                    (($(this).is('input[type="text"]') || $(this).is('select')) && !$(this).attr('value')) ||
                    ($(this).is('input[type="submit"]'))){
                    $(this).parent().hide();
                }
            }).attr("disabled", true);
            if($('.no-edit').size()) {
                if(actions.length == 0) {
                    $("#no_casexml_actions").show();
                }
            }
            //checkboxShowHide($("#open-case"), $("#update-case, #open-referral").parent());
            //checkboxShowHide($(".action input[type='checkbox']"), function(){return $(this).next();});
        }
    });
    CaseXML.prototype.init = (function(){
        $("#casexml_json").hide();
        this.render();
    });

    CaseXML.prototype.renderQuestions = (function(filter) {
        // filter can be "all", or any of "select1", "select", or "input" separated by spaces
        filter = filter.split(" ");
        var html = "";
        for(i in this.questions) {
            var q = this.questions[i];
            if(filter[0] == "all" || filter.indexOf(q.tag) != -1) {
                html += "<option value='" + q.value + "' title='" + escapeQuotes(q.label) + "'>" + truncateLabel(q.label) + "</option>";
            }
        }
        return html;
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
            var action = {};
            if(!$checkbox.is(":checked")) return;

            id = $checkbox.attr('id').replace('-','_');
            if(id=="update_case") {
                action.update = {};
                $('.action-update', this).each(function(){
                    key = lookup(this, "action-update-key");
                    val = lookup(this, "action-update-value");
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

    return CaseXML;
})();