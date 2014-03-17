function getContactData(form) {
    // form = birth registration form
    var data = {};
    data.noPhoneDetails = !(
        form.phone_mother_number ||
        form.phone_husband_number ||
        form.phone_asha_number ||
        form.phone_house_number);

    data.noAddress = (form.address_information_filled === 'no');
    data.noContactInfo = (data.noPhoneDetails && data.noAddress);

    return data;
}
