from django.contrib import admin

from coldfront.core.department.models import Department


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'catalog_code',
        'academic_group',
        'academic_organization',
    )

    search_fields = ['name', 'catalog_number', 'academic_group', 'academic_organization']
