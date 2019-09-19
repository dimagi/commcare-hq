from corehq.warehouse.const import ALL_TABLES
from corehq.warehouse.loaders import get_loader_by_slug


def test_validate_loaders():
    def check(slug):
        loader = get_loader_by_slug(slug)
        loader().validate()

    for slug in ALL_TABLES:
        yield check, slug


def check_for_loader_cycles(slug):
    loader = get_loader_by_slug(slug)
    path = list()

    def visit(vertex):
        path.append(vertex.slug)
        for dep in vertex().dependant_slugs():
            dep_cls = get_loader_by_slug(dep)
            if dep in path or visit(dep_cls):
                cycle = path + [dep]
                raise Exception(f'dependency cycle: {cycle}')
        path.remove(vertex.slug)

    return visit(loader)


def test_for_dependency_cycles():
    for slug in ALL_TABLES:
        yield check_for_loader_cycles, slug
