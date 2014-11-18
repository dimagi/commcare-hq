from corehq.apps.products.models import Product
from django.utils.translation import ugettext as _


def import_products(domain, importer):
    from corehq.apps.products.views import ProductFieldsView
    results = {'errors': [], 'messages': []}
    to_save = []
    product_count = 0
    seen_product_ids = set()

    custom_data_validator = ProductFieldsView.get_validator(domain)

    for row in importer.worksheet:
        try:
            p = Product.from_excel(row, custom_data_validator)
        except Exception, e:
            results['errors'].append(
                _(u'Failed to import product {name}: {ex}'.format(
                    name=row['name'] or '',
                    ex=e,
                ))
            )
            continue

        importer.add_progress()
        if not p:
            # skip if no product is found (or the row is blank)
            continue
        if not p.domain:
            # if product doesn't have domain, use from context
            p.domain = domain
        elif p.domain != domain:
            # don't let user import against another domains products
            results['errors'].append(
                _(u"Product {product_name} belongs to another domain and was not updated").format(
                    product_name=p.name
                )
            )
            continue

        if p.code and p.code in seen_product_ids:
            results['errors'].append(_(
                u"Product {product_name} could not be imported \
                due to duplicated product ids in the excel \
                file"
            ).format(
                product_name=p.name
            ))
            continue
        elif p.code:
            seen_product_ids.add(p.code)

        product_count += 1
        to_save.append(p)

        if len(to_save) > 500:
            Product.get_db().bulk_save(to_save)
            to_save = []

    if to_save:
        Product.get_db().bulk_save(to_save)

    if product_count:
        results['messages'].insert(
            0,
            _('Successfully updated {number_of_products} products with {errors} '
              'errors.').format(
                number_of_products=product_count, errors=len(results['errors'])
            )
        )

    return results
