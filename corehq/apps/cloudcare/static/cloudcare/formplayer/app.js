var FormplayerFrontend = new Marionette.Application();

FormplayerFrontend.on("before:start", function(){
    var RegionContainer = Marionette.LayoutView.extend({
        el: "app-container",

        regions: {
            main: "main-region"
        }
    });

    FormplayerFrontend.regions = new RegionContainer();
});

FormplayerFrontend.navigate = function(route,  options){
  options || (options = {});
  Backbone.history.navigate(route, options);
};

FormplayerFrontend.getCurrentRoute = function(){
  return Backbone.history.fragment
};

FormplayerFrontend.on("start", function(){
    console.log("Starting!");

    if(this.getCurrentRoute() === ""){
        FormplayerFrontend.trigger("apps:list");
    }
})