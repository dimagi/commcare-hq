$(function () {
    $("#ko-playlist-generator").koApplyBindings(function () {
        return {
            genres: [
                "techno", "house", "acid", "electro", "bass", "drum & bass",
                "jungle", "club", "detroit techno", "detroit house", "chicago house",
                "soulful house", "west coast electro", "rave", "acid techno",
                "percussive techno", "hypnotic techno", "breaks", "deep house",
                "deep techno", "jack",
            ],
            value: ko.observable("acid"),
        };
    });
});