from __future__ import absolute_import
import jsonobject


class ValueContainer(jsonobject.JsonObject):
    value = jsonobject.DictProperty()


class AnnotationTranslation(jsonobject.JsonObject):
    display_text = jsonobject.DictProperty()
    values = jsonobject.DictProperty()
    x = jsonobject.StringProperty()
    y = jsonobject.StringProperty()
    lang = jsonobject.StringProperty()


class SeriesTranslation(jsonobject.JsonObject):
    locale_specific_config = jsonobject.DictProperty()
    x_function = jsonobject.StringProperty()
    y_function = jsonobject.StringProperty()


class GraphConfigurationTranslation(jsonobject.JsonObject):
    annotations = jsonobject.ListProperty(AnnotationTranslation)
    series = jsonobject.ListProperty(SeriesTranslation)
    locale_specific_config = jsonobject.DictProperty()


class ColumnTranslation(jsonobject.JsonObject):
    header = jsonobject.DictProperty()
    enum = jsonobject.ListProperty(ValueContainer)
    graph_configuration = jsonobject.ObjectProperty(GraphConfigurationTranslation)


class DetailTranslation(jsonobject.JsonObject):
    columns = jsonobject.ListProperty(ColumnTranslation)


class CaseDetailsTranslation(jsonobject.JsonObject):
    long = jsonobject.ObjectProperty(DetailTranslation)
    short = jsonobject.ObjectProperty(DetailTranslation)


class ModuleTranslation(jsonobject.JsonObject):
    name = jsonobject.DictProperty()
    case_details = jsonobject.ObjectProperty(CaseDetailsTranslation)
    id_strings = jsonobject.DictProperty()


class LabelTranslation(jsonobject.JsonObject):
    default = jsonobject.ObjectProperty(ValueContainer)
    image = jsonobject.ObjectProperty(ValueContainer)
    audio = jsonobject.ObjectProperty(ValueContainer)
    video = jsonobject.ObjectProperty(ValueContainer)


class FormTranslation(jsonobject.JsonObject):
    name = jsonobject.DictProperty()
    text = jsonobject.DictProperty(LabelTranslation)
    id_strings = jsonobject.DictProperty()