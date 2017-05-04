/* globals hqDefine, ko, $, CodeMirror */

hqDefine('case_search/js/case_search.js', function(){
    'use strict';
    return function(case_data_url){
        var self = this;
        self.codeMirror = null;
        self.type = ko.observable();
        self.owner_id = ko.observable();
        self.customQueryAddition = ko.observable();
        self.results = ko.observableArray();
        self.case_data_url = case_data_url;
        self.parameters = ko.observableArray([{
            key: "",
            value: "",
            clause: "must",
            fuzzy: false,
        }]);

        self.addParameter = function(){
            self.parameters.push({
                key: "",
                value: "",
                clause: "must",
                fuzzy: false,
            });
        };
        self.removeParameter = function(){
            self.parameters.remove(this);
        };

        self.submit = function(){
            self.results([]);
            $.post({
                url: window.location.href,
                data: {q: JSON.stringify({
                    type: self.type(),
                    owner_id: self.owner_id(),
                    parameters: self.parameters(),
                    customQueryAddition: self.customQueryAddition()}
                )},
                success: function(data){
                    self.results(data.values);
                    var values = JSON.stringify(data.values, null, '    ');
                    if (self.codeMirror === null){
                        self.codeMirror = CodeMirror( $("#raw-results").get(0), {
                            value: values,
                            mode: { name: 'javascript', json: true },
                            readOnly: true,
                            lineNumbers: true,
                            lineWrapping: true,
                            viewportMargin: Infinity,
                            foldGutter: true,
                            gutters: ["CodeMirror-linenumbers", "CodeMirror-foldgutter"],
                        });
                    } else {
                        self.codeMirror.setValue(values);
                    }
                },
            });
        };
    };
});
