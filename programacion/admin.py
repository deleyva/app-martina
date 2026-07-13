from django.contrib import admin

from .models import ContentCoverage, CoursePlan, PlanItem


class PlanItemInline(admin.TabularInline):
    model = PlanItem
    extra = 0
    fields = ("content_type", "object_id", "parent", "order", "status", "notes")


@admin.register(CoursePlan)
class CoursePlanAdmin(admin.ModelAdmin):
    list_display = ("name", "group", "teacher", "start_date", "end_date", "is_active")
    list_filter = ("is_active", "group")
    inlines = [PlanItemInline]


@admin.register(ContentCoverage)
class ContentCoverageAdmin(admin.ModelAdmin):
    list_display = (
        "group",
        "content_object",
        "elements_seen",
        "elements_total",
        "page_presented",
        "updated_at",
    )
    list_filter = ("group",)
