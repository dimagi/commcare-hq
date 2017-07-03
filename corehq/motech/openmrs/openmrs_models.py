from dimagi.ext.jsonobject import *


class Name(JsonObject):
    uuid = StringProperty()
    display = StringProperty()
    givenName = StringProperty()
    middleName = StringProperty()
    familyName = StringProperty()


class Person(JsonObject):

    uuid = StringProperty()
    display = StringProperty()

    preferredName = ObjectProperty(Name)
    names = ListProperty(Name)

    preferredAddress = ObjectProperty(Address)
    addresses = ListProperty(Address)

    birthdate = DateProperty()
    birthdateEstimated = BooleanProperty()
    age = IntegerProperty()
    gender = StringProperty()

    dead = BooleanProperty()
    causeOfDeath = StringProperty()  # concept ID
    deathDate = DateProperty()

    attributes = ListProperty(Attribute)


class Address(JsonObject):
    uuid = StringProperty()
    address1 = StringProperty()
    address2 = StringProperty()
    cityVillage = StringProperty()
    stateProvince = StringProperty()
    country = StringProperty()
    postalCode = StringProperty()
    countyDistrict = StringProperty()
    address3 = StringProperty()
    address4 = StringProperty()
    address5 = StringProperty()
    address6 = StringProperty()
    startDate = DateProperty()
    endDate = DateProperty()
    latitude = StringProperty()
    longitude = StringProperty()


class Attribute(JsonObject):

    uuid = StringProperty()
    display = StringProperty()
    value = StringProperty()
    name = StringProperty()
    description = StringProperty()
    format = StringProperty()
    attributeType = ObjectProperty(AttributeType)


class AttributeType(JsonObject):

    display = StringProperty()
    uuid = StringProperty()
    format = StringProperty()
