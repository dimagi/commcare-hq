function get_danger_signs(danger_sign_value) {
    if (danger_sign_value) {
        var signs = danger_sign_value.trim().toLowerCase();
        signs = signs.split(' ');
        return signs;
    }
    return [];
}
