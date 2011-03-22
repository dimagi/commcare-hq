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
        $answers = $(this).next("select[name='condition-answer']");
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
function populateQuestions(questions) {
    $("select.questions").each(function(){
        //$answers = $(this).next("select[name='trigger_answer']");
        //$answers.hide();
        for(i in questions) {
            q = questions[i];
            if(($(this).hasClass("questions-all")) ||
               ($(this).hasClass('questions-select1') && q.tag == "select1") ||
               ($(this).hasClass('questions-select') && q.tag == "select") ||
               ($(this).hasClass('questions-input') && q.tag == "input")) {
                option = "<option value='" + q.value + "' title='" + escapeQuotes(q.label) + "'>" + truncateLabel(q.label) + "</option>";
                $(this).append($(option));
            }
        }
    });
}
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

function generateCasexmlJson(){
    actions = {};
    function lookup(root, key){
        return $(root).find('[name="' + key + '"]').attr('value');
    }
    $(".casexml .action").each(function(){

        $checkbox = $(this).find('input[type="checkbox"]');
        if(!$checkbox.is(":checked")) return;
        action = {};
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
            action.condition.type = $('input[name="if"]', this).is(':checked') ? 'if' : 'always';
            if(action.condition.type == 'if') {
                action.condition.question = lookup(this, 'condition-question');
                action.condition.answer = lookup(this, 'condition-answer');
            }
        });
        actions[id] = action;

    });
    return JSON.stringify(actions);
}
function populateCasexmlForm(actions){
    //actions = JSON.parse(actions);
    function is_active(action) {
        return action.condition && action.condition.type in {'if': true, 'always': true};
    }
    for(a in actions) {
        action = actions[a];
        if(!is_active(action)) continue;
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
        this.template = new EJS({element:"casexml-template"});
    }
    CaseXML.prototype.init = (function(){
        this.template.update(this.home, this);
        initCondition();
        $("#casexml_json").hide();
        var questions = this.questions;
        if(questions.length) {
            populateQuestions(questions);

            makeConditionInteractive(questions);
            initUpdateCase();
            populateCasexmlForm(get_actions());
            $(".casexml").delegate('*', 'change', function(){
                // recompute casexml_json
                $("#casexml_json").text(generateCasexmlJson());
            }).find('*').first().trigger('change');
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
    return CaseXML;
})();