drift.on('emailCapture',function(e){
    _hsq.push(['identify',{email:e.data.email}]);
    _hsq.push(['trackEvent',{id:'Identified via Drift'}]);
});
