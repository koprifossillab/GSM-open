from django.contrib import admin

from .models import Layer, LayerGroup, Point, PointSet


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
