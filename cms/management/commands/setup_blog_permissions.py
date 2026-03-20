from django.contrib.auth.models import Group as AuthGroup
from django.contrib.auth.models import Permission
from django.core.management.base import BaseCommand
from wagtail.models import GroupPagePermission
from wagtail.models import Page
from wagtail.models import Workflow
from wagtail.models import WorkflowPage
from wagtail.models import WorkflowTask

from cms.models import BlogIndexPage

try:
    from wagtail.models import GroupApprovalTask
except ImportError:
    GroupApprovalTask = None


def _get_permission(codename):
    """Get a Permission object by codename (Wagtail 5.1+ uses Permission FK)."""
    return Permission.objects.get(codename=codename, content_type__app_label="wagtailcore")


class Command(BaseCommand):
    help = "Set up blog department groups, permissions, and workflows. Idempotent."

    def handle(self, *args, **options):
        # Find the hub page (root BlogIndexPage that has BlogIndexPage children)
        hub = None
        for bip in BlogIndexPage.objects.all():
            children = Page.objects.child_of(bip).type(BlogIndexPage)
            if children.exists():
                hub = bip
                break

        if not hub:
            self.stdout.write(self.style.WARNING("No hub BlogIndexPage found (one with department children)."))
            return

        departments = BlogIndexPage.objects.child_of(hub).live()
        self.stdout.write(f"Found hub: «{hub.title}» with {departments.count()} departments")

        for dept in departments:
            slug = dept.slug
            self.stdout.write(f"\n── {dept.title} (slug: {slug}) ──")

            # 1. Create department group (add + change, no publish)
            dept_group_name = f"blog_dept_{slug}"
            dept_group, created = AuthGroup.objects.get_or_create(name=dept_group_name)
            if created:
                self.stdout.write(self.style.SUCCESS(f"  Created group: {dept_group_name}"))
            else:
                self.stdout.write(f"  Group exists: {dept_group_name}")

            # Assign add + change permissions on the department page
            for codename in ["add_page", "change_page"]:
                perm = _get_permission(codename)
                _, perm_created = GroupPagePermission.objects.get_or_create(
                    group=dept_group,
                    page=dept,
                    permission=perm,
                )
                if perm_created:
                    self.stdout.write(self.style.SUCCESS(f"  Added permission: {codename}"))

            # 2. Create moderator group (publish permission)
            mod_group_name = f"blog_mod_{slug}"
            mod_group, created = AuthGroup.objects.get_or_create(name=mod_group_name)
            if created:
                self.stdout.write(self.style.SUCCESS(f"  Created group: {mod_group_name}"))
            else:
                self.stdout.write(f"  Group exists: {mod_group_name}")

            # Assign publish permission
            publish_perm = _get_permission("publish_page")
            _, perm_created = GroupPagePermission.objects.get_or_create(
                group=mod_group,
                page=dept,
                permission=publish_perm,
            )
            if perm_created:
                self.stdout.write(self.style.SUCCESS("  Added permission: publish_page"))

            # Also give moderators add + change
            for codename in ["add_page", "change_page"]:
                perm = _get_permission(codename)
                GroupPagePermission.objects.get_or_create(
                    group=mod_group,
                    page=dept,
                    permission=perm,
                )

            # Add moderator user to mod group if assigned
            dept_specific = dept.specific
            if dept_specific.moderator:
                dept_specific.moderator.groups.add(mod_group)
                self.stdout.write(
                    self.style.SUCCESS(f"  Added moderator {dept_specific.moderator.username} to {mod_group_name}")
                )

            # 3. Create workflow with GroupApprovalTask
            if GroupApprovalTask is None:
                self.stdout.write(self.style.WARNING("  GroupApprovalTask not available — skipping workflow"))
                continue

            workflow_name = f"Revisión: {dept.title}"
            workflow, wf_created = Workflow.objects.get_or_create(
                name=workflow_name,
                defaults={"active": True},
            )
            if wf_created:
                self.stdout.write(self.style.SUCCESS(f"  Created workflow: {workflow_name}"))
            else:
                self.stdout.write(f"  Workflow exists: {workflow_name}")

            # Create approval task
            task_name = f"Aprobación: {dept.title}"
            task, task_created = GroupApprovalTask.objects.get_or_create(
                name=task_name,
                defaults={"active": True},
            )
            if task_created:
                task.groups.add(mod_group)
                self.stdout.write(self.style.SUCCESS(f"  Created task: {task_name}"))
            else:
                self.stdout.write(f"  Task exists: {task_name}")

            # Link task to workflow
            WorkflowTask.objects.get_or_create(
                workflow=workflow,
                task=task,
                defaults={"sort_order": 0},
            )

            # Assign workflow to department page
            WorkflowPage.objects.get_or_create(
                workflow=workflow,
                page=dept,
            )
            self.stdout.write(self.style.SUCCESS(f"  Workflow assigned to «{dept.title}»"))

        self.stdout.write(self.style.SUCCESS("\nBlog permissions setup complete."))
