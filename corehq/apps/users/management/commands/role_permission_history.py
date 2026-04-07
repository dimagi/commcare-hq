from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

from field_audit.models import AuditEvent

from corehq.apps.users.models_role import (
    Permission,
    RoleAssignableBy,
    RolePermission,
    UserRole,
)


class Command(BaseCommand):
    help = """Show chronological history of permission changes on a user role.

    Usage:
        # List all roles in a domain
        ./manage.py role_permission_history my-domain --list

        # By role name
        ./manage.py role_permission_history my-domain --role-name "Field Worker"

        # By database ID or couch_id
        ./manage.py role_permission_history my-domain --role-id 123
        ./manage.py role_permission_history my-domain --role-id abc123def456
    """

    def add_arguments(self, parser):
        parser.add_argument("domain")
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument("--role-name", help="Name of the role")
        group.add_argument("--role-id", help="Database ID or couch_id of the role")
        group.add_argument("--list", action="store_true", dest="list_roles",
                           help="List all roles in the domain")

    def handle(self, domain, role_name, role_id, list_roles, **options):
        if list_roles:
            self._list_roles(domain)
            return

        role = self._get_role(domain, role_name, role_id)
        perm_map = {p.id: p.value for p in Permission.objects.all()}
        entries = self._collect_events(role)

        if not entries:
            self.stdout.write("No audit events found for this role.")
            return

        self.stdout.write(
            f"\n=== Permission History for Role: '{role.name}' "
            f"(id={role.id}, domain={role.domain}) ===\n"
        )
        for entry_type, event in entries:
            self._print_event(entry_type, event, perm_map)

    def _list_roles(self, domain):
        roles = UserRole.objects.get_by_domain(domain, include_archived=True)
        if not roles:
            self.stdout.write(f"No roles found in domain '{domain}'")
            return
        self.stdout.write(f"Roles in domain '{domain}':")
        for r in roles:
            archived = " (archived)" if r.is_archived else ""
            self.stdout.write(f"  {r.name} (id={r.id}, couch_id={r.couch_id}){archived}")

    def _get_role(self, domain, role_name, role_id):
        if role_id:
            if role_id.isdigit():
                try:
                    return UserRole.objects.get(domain=domain, id=int(role_id))
                except UserRole.DoesNotExist:
                    raise CommandError(f"No role found with id={role_id} in domain '{domain}'")
            else:
                try:
                    return UserRole.objects.get(domain=domain, couch_id=role_id)
                except UserRole.DoesNotExist:
                    raise CommandError(f"No role found with couch_id='{role_id}' in domain '{domain}'")

        roles = UserRole.objects.filter(domain=domain, name=role_name)
        if roles.count() == 0:
            raise CommandError(
                f"No role found with name '{role_name}' in domain '{domain}'. "
                f"Use --list to see available roles."
            )
        if roles.count() > 1:
            matches = ", ".join(
                f"id={r.id} (archived={r.is_archived})" for r in roles
            )
            raise CommandError(
                f"Multiple roles found with name '{role_name}': {matches}. "
                f"Use --role-id to specify one."
            )
        return roles.first()

    def _collect_events(self, role):
        entries = []

        for event in (AuditEvent.objects.by_model(UserRole)
                      .filter(object_pk=role.id)
                      .order_by("event_date")):
            entries.append(("role", event))

        # Collect RolePermission PKs that belong to this role from audit history,
        # since update events may not include the role field in their delta.
        rp_pks = self._get_role_permission_pks(role)
        for event in (AuditEvent.objects.by_model(RolePermission)
                      .filter(object_pk__in=rp_pks)
                      .order_by("event_date")):
            entries.append(("permission", event))

        rab_pks = self._get_role_assignable_by_pks(role)
        for event in (AuditEvent.objects.by_model(RoleAssignableBy)
                      .filter(object_pk__in=rab_pks)
                      .order_by("event_date")):
            entries.append(("assignable_by", event))

        entries.sort(key=lambda x: x[1].event_date)
        return entries

    def _get_related_pks_from_audit(self, model_class, role):
        """Get all PKs for a related model from audit events where role matches.

        The role field only appears in the delta for create and delete events
        (since it doesn't change during updates), but that's sufficient to
        discover all PKs that ever belonged to this role.
        """
        return set(
            AuditEvent.objects.by_model(model_class)
            .filter(Q(delta__role__new=role.id) | Q(delta__role__old=role.id))
            .values_list("object_pk", flat=True)
        )

    def _get_role_permission_pks(self, role):
        """Get all RolePermission PKs for this role, including deleted ones."""
        pks = set(role.rolepermission_set.values_list("pk", flat=True))
        pks.update(self._get_related_pks_from_audit(RolePermission, role))
        return pks

    def _get_role_assignable_by_pks(self, role):
        """Get all RoleAssignableBy PKs for this role, including deleted ones."""
        pks = set(role.roleassignableby_set.values_list("pk", flat=True))
        pks.update(self._get_related_pks_from_audit(RoleAssignableBy, role))
        return pks

    def _print_event(self, entry_type, event, perm_map):
        prefix = self._event_prefix(event)

        if entry_type == "role":
            for line in self._role_lines(event, event.delta):
                self.stdout.write(f"{prefix} {line}")
        elif entry_type == "permission":
            self.stdout.write(
                f"{prefix} {self._permission_line(event, event.delta, perm_map)}"
            )
        elif entry_type == "assignable_by":
            self.stdout.write(
                f"{prefix} {self._assignable_by_line(event, event.delta)}"
            )

    def _event_prefix(self, event):
        ts = event.event_date.strftime("%Y-%m-%d %H:%M:%S.%f UTC")
        return f"[{ts}] by {self._who(event)}"

    def _role_lines(self, event, delta):
        interesting = {
            k: v for k, v in delta.items() if k not in ("couch_id", "domain")
        }
        if event.is_create:
            fields = ", ".join(
                f"{field}: {change['new']}"
                for field, change in interesting.items()
                if change.get("new") is not None
                and change["new"] != ""
                and change["new"] is not False
            )
            yield f"Role CREATED: {fields}" if fields else "Role CREATED"
        else:
            for field, change in interesting.items():
                old = change.get("old", "\u2014")
                new = change.get("new", "\u2014")
                yield f"Role {field}: {old} \u2192 {new}"

    def _permission_line(self, event, delta, perm_map):
        perm_fk = delta.get("permission_fk", {})
        perm_id = perm_fk.get("new", perm_fk.get("old"))
        pname = perm_map.get(perm_id, f"unknown(id={perm_id})")

        if event.is_create:
            allow_all = delta.get("allow_all", {}).get("new", True)
            items = delta.get("allowed_items", {}).get("new")
            if allow_all:
                return f"Permission GRANTED: {pname} (allow all)"
            return f"Permission GRANTED: {pname} (items: {self._format_items(items)})"
        elif event.is_delete:
            allow_all = delta.get("allow_all", {}).get("old", True)
            items = delta.get("allowed_items", {}).get("old")
            if allow_all:
                return f"Permission REVOKED: {pname} (was allow all)"
            return f"Permission REVOKED: {pname} (was items: {self._format_items(items)})"
        else:
            changes = []
            if "allow_all" in delta:
                old_aa = delta["allow_all"].get("old")
                new_aa = delta["allow_all"].get("new")
                if old_aa != new_aa:
                    changes.append(f"allow_all: {old_aa} \u2192 {new_aa}")
            if "allowed_items" in delta:
                old_items = delta["allowed_items"].get("old")
                new_items = delta["allowed_items"].get("new")
                changes.append(
                    f"items: {self._format_items(old_items)} "
                    f"\u2192 {self._format_items(new_items)}"
                )
            return f"Permission CHANGED: {pname} ({', '.join(changes)})"

    def _assignable_by_line(self, event, delta):
        ab_ref = delta.get("assignable_by_role", {})
        ab_id = ab_ref.get("new", ab_ref.get("old"))
        try:
            ab_name = UserRole.objects.get(id=ab_id).name
        except UserRole.DoesNotExist:
            ab_name = f"deleted role (id={ab_id})"

        if event.is_create:
            return f"Assignable by ADDED: {ab_name}"
        elif event.is_delete:
            return f"Assignable by REMOVED: {ab_name}"
        return f"Assignable by CHANGED: {ab_name}"

    @staticmethod
    def _who(event):
        ctx = event.change_context or {}
        username = ctx.get("username", "unknown")
        user_type = ctx.get("user_type", "")
        if user_type and user_type != "RequestUser":
            return f"{username} ({user_type})"
        return username

    @staticmethod
    def _format_items(items):
        if not items:
            return "none"
        if len(items) <= 5:
            return ", ".join(str(i) for i in items)
        return f"{', '.join(str(i) for i in items[:5])}... ({len(items)} total)"
