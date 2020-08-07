import inspect

from django.core.management import BaseCommand

from corehq.extensions import extension_manager


class Command(BaseCommand):
    help = "List all defined extension points."

    def handle(self, *args, **options):
        title = "CommCare Extension Points\n"
        print("\n" + title + "=" * len(title) + "\n")
        for name, point in extension_manager.registry.items():
            func = point.definition_function
            header = f"{func.__module__}.{func.__name__}\n"
            print(header + "-" * len(header) + "\n")
            print(inspect.getdoc(point.definition_function))
            print("\nImplementations:\n")
            for extension in point.extensions:
                callable = extension.callable
                print(f"    * {callable.__module__}.{callable.__name__}")
            print("\n")
