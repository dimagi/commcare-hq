import functools
import json
from django.utils.translation import ugettext as _
from jsonobject.exceptions import BadValueError
from corehq.apps.userreports.exceptions import BadSpecError
from corehq.apps.userreports.expressions.specs import PropertyNameGetterSpec, PropertyPathGetterSpec, \
    ConditionalExpressionSpec, ConstantGetterSpec, RootDocExpressionSpec, RelatedDocExpressionSpec


class ExpressionFactory(object):
    spec_map = {}
    # spec_map is populated by use of the `register` method.

    @classmethod
    def register(cls, type_name):
        """
        Return a decorator function that registers an expression factory function
        for the given type_name.

        Usage example:

            @ExpressionFactory.register('conditional')
            def _conditional_expression(spec, context):
                ...

            my_expression = ExpressionFactory.from_spec({
                "type": "conditional",
                ...
            })

        Don't forget that files containing the registration must be imported
        for the registration to be executed.
        Bootstrap custom expressions by importing their modules in
        `expressions.__init__.py`.
        """
        if type_name in cls.spec_map:
            raise ValueError(
                "Expression factory function already "
                "registered for type '{}'!".format(type_name)
            )

        def register_factory_function(func):
            cls.spec_map[type_name] = func
            return func

        return register_factory_function

    @classmethod
    def from_spec(cls, spec, context=None):
        try:
            return cls.spec_map[spec['type']](spec, context)
        except KeyError:
            raise BadSpecError(_('Invalid or missing getter type: {}. Valid options are: {}').format(
                spec.get('type', '[missing]'),
                ', '.join(cls.spec_map.keys()),
            ))
        except BadValueError as e:
            raise BadSpecError(_('Problem creating getter: {}. Message is: {}').format(
                json.dumps(spec, indent=2),
                str(e),
            ))


def _simple_expression_generator(wrapper_class, spec, context):
    return wrapper_class.wrap(spec)

_constant_expression = ExpressionFactory.register('constant')(
    functools.partial(_simple_expression_generator, ConstantGetterSpec)
)
_property_name_expression = ExpressionFactory.register('property_name')(
    functools.partial(_simple_expression_generator, PropertyNameGetterSpec)
)
_property_path_expression = ExpressionFactory.register('property_path')(
    functools.partial(_simple_expression_generator, PropertyPathGetterSpec)
)


@ExpressionFactory.register("conditional")
def _conditional_expression(spec, context):
    # no way around this since the two factories inherently depend on each other
    from corehq.apps.userreports.filters.factory import FilterFactory
    wrapped = ConditionalExpressionSpec.wrap(spec)
    wrapped.configure(
        FilterFactory.from_spec(wrapped.test, context),
        ExpressionFactory.from_spec(wrapped.expression_if_true, context),
        ExpressionFactory.from_spec(wrapped.expression_if_false, context),
    )
    return wrapped


@ExpressionFactory.register("root_doc")
def _root_doc_expression(spec, context):
    wrapped = RootDocExpressionSpec.wrap(spec)
    wrapped.configure(ExpressionFactory.from_spec(wrapped.expression, context))
    return wrapped


@ExpressionFactory.register("related_doc")
def _related_doc_expression(spec, context):
    wrapped = RelatedDocExpressionSpec.wrap(spec)
    wrapped.configure(
        related_doc_type=wrapped.related_doc_type,
        doc_id_expression=ExpressionFactory.from_spec(wrapped.doc_id_expression, context),
        value_expression=ExpressionFactory.from_spec(wrapped.value_expression, context),
    )
    return wrapped
