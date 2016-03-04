hqDefine('hqwebapp/js/pagecontext.js', function () {
    function PageContext() {
        var context = {};
        this.get = function (variableName) {
            if (context.hasOwnProperty(variableName)) {
                return context[variableName];
            } else {
                throw new Error('Variable ' + variableName + ' not found in page context');
            }
        };
        this.set = function (variableName, value) {
            if (context.hasOwnProperty(variableName)) {
                throw new Error('Variable ' + variableName + ' already defined in page context');
            } else {
                context[variableName] = value;
            }
        };
    }
    return {PageContext: PageContext};
});
