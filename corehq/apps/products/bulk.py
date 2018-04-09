from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.apps.products.models import Product, SQLProduct
from django.utils.translation import ugettext as _
from corehq.apps.programs.models import Program


def import_products(domain, importer):
    from corehq.apps.products.views import ProductFieldsView
    results = {'errors': [], 'messages': []}
    to_save = []
    product_count = 0
    seen_codes = set()

    program_ids = [program._id for program in Program.by_domain(domain)]
    codes = {
        row['code']: row['product_id']
        for row in SQLProduct.objects.filter(domain=domain, is_archived=False).values('code', 'product_id')
    }

    custom_data_validator = ProductFieldsView.get_validator(domain)

    for row in importer.worksheet:
        try:
            p = Product.from_excel(row, custom_data_validator)
        except Exception as e:
            results['errors'].append(
                _('Failed to import product {name}: {ex}'.format(
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
                _("Product {product_name} belongs to another domain and was not updated").format(
                    product_name=p.name
                )
            )
            continue

        if p.code:
            if (p.code in codes and codes[p.code] != p.get_id) or (p.code in seen_codes):
                results['errors'].append(_(
                    "Product {product_name} could not be imported \
                    since its product ID is already assigned to another product"
                ).format(
                    product_name=p.name
                ))
                continue

            if p.code not in codes:
                seen_codes.add(p.code)

        if p.program_id and p.program_id not in program_ids:
            results['errors'].append(_(
                "Product {product_name} references a program that doesn't exist: {program_id}"
            ).format(
                product_name=p.name,
                program_id=p.program_id
            ))
            continue

        product_count += 1
        to_save.append(p)

        if len(to_save) > 500:
            Product.bulk_save(to_save)
            for couch_product in to_save:
                couch_product.sync_to_sql()
            to_save = []

    if to_save:
        Product.bulk_save(to_save)
        for couch_product in to_save:
            couch_product.sync_to_sql()

    if product_count:
        results['messages'].insert(
            0,
            _('Successfully updated {number_of_products} products with {errors} '
              'errors.').format(
                number_of_products=product_count, errors=len(results['errors'])
            )
        )

    return results
