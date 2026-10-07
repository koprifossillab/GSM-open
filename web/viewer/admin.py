from django.contrib import admin
from django.db import transaction

from . import sources
from .models import DataSource, DataSourceChange, FetchRun, Layer, LayerGroup, Point, PointSet


@admin.register(LayerGroup)
class LayerGroupAdmin(admin.ModelAdmin):
    list_display = ("name", "order")
    list_editable = ("order",)


@admin.register(Layer)
class LayerAdmin(admin.ModelAdmin):
    list_display = ("title", "name", "group", "enabled", "queryable", "verified_at")
    list_filter = ("group", "enabled", "queryable")
    search_fields = ("name", "title")
    list_editable = ("enabled",)


class PointInline(admin.TabularInline):
    model = Point
    extra = 0


@admin.register(PointSet)
class PointSetAdmin(admin.ModelAdmin):
    list_display = ("name", "source_filename", "visible", "created_at")
    inlines = [PointInline]


# ── 데이터소스 (jikhanjung P03) — 명세는 고치고, 고칠 때마다 이력에 앞뒤 줄을. 기록은 읽기만 ──

@admin.register(DataSource)
class DataSourceAdmin(admin.ModelAdmin):
    list_display = ("id", "name_ko", "kind", "schedule", "runs_on", "license", "updated_at", "updated_by")
    list_filter = ("kind", "schedule", "runs_on")
    search_fields = ("id", "name_ko", "name_en", "org", "license")
    readonly_fields = ("updated_at", "updated_by")
    fieldsets = (
        (None, {"fields": ("id", "order", "name_ko", "name_en", "org")}),
        ("무엇을·언제·어디서", {"fields": ("kind", "schedule", "runs_on", "commands")}),
        ("조건", {"fields": ("license", "flags"),
                 "description": "flags — nc(비상업)·sold(판매)·lab_only(내부용)·no_store(담지 않음) 가운데서, JSON 목록으로"}),
        ("산출물·원본", {"fields": ("outputs", "raw", "docs", "note")}),
        ("고친 것", {"fields": ("updated_at", "updated_by")}),
    )

    def get_readonly_fields(self, request, obj=None):
        # id 는 기록 표가 글로 가리킨다 — 만든 뒤에는 바꾸지 않는다
        return self.readonly_fields + (("id",) if obj else ())

    def save_model(self, request, obj, form, change):
        before = DataSource.objects.filter(pk=obj.pk).first() if change else None
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)
        sources.record_change(obj.pk, before.as_row() if before else None, obj.as_row(), "admin", request.user)

    def delete_model(self, request, obj):
        row = obj.as_row()
        super().delete_model(request, obj)
        sources.record_change(row["id"], row, None, "admin", request.user)

    def delete_queryset(self, request, queryset):
        with transaction.atomic():                    # 중간에 깨지면 지운 줄·이력이 일부만 남지 않게 (#381 검토 6)
            for obj in queryset:
                self.delete_model(request, obj)


@admin.register(DataSourceChange)
class DataSourceChangeAdmin(admin.ModelAdmin):
    list_display = ("at", "source", "origin", "by_name")
    list_filter = ("origin",)
    search_fields = ("source",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(FetchRun)
class FetchRunAdmin(admin.ModelAdmin):
    list_display = ("started_at", "source", "command", "result", "seconds", "rows", "origin")
    list_filter = ("result", "origin")
    search_fields = ("source", "command")
    date_hierarchy = "started_at"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
