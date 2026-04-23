from django.contrib import admin
from django.utils.html import format_html

from .models import Department, Employee, Holiday, LeaveBalance, LeaveRequest, LeaveType


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'head')
    search_fields = ('name',)


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ('user', 'department', 'designation', 'is_manager', 'date_of_joining', 'photo_preview')
    list_filter = ('department', 'is_manager')
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'designation')
    readonly_fields = ('photo_preview',)
    fields = ('user', 'department', 'designation', 'date_of_joining', 'is_manager', 'photo', 'photo_url', 'photo_preview')

    def photo_preview(self, obj):
        if obj.photo:
            return format_html('<img src="{}" alt="{}" style="width:64px;height:64px;border-radius:16px;object-fit:cover;" />', obj.photo.url, obj)
        if obj.photo_url:
            return format_html('<img src="{}" alt="{}" style="width:64px;height:64px;border-radius:16px;object-fit:cover;" />', obj.photo_url, obj)
        return 'No photo'

    photo_preview.short_description = 'Photo'


@admin.register(LeaveType)
class LeaveTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'max_days_per_year', 'is_paid', 'carry_forward')
    list_filter = ('is_paid', 'carry_forward')


@admin.register(Holiday)
class HolidayAdmin(admin.ModelAdmin):
    list_display = ('name', 'date')
    ordering = ('date',)


@admin.register(LeaveBalance)
class LeaveBalanceAdmin(admin.ModelAdmin):
    list_display = ('employee', 'leave_type', 'year', 'allocated_days', 'used_days', 'remaining_days')
    list_filter = ('year', 'leave_type')
    search_fields = ('employee__user__username', 'employee__user__first_name', 'employee__user__last_name')


@admin.register(LeaveRequest)
class LeaveRequestAdmin(admin.ModelAdmin):
    list_display = ('employee', 'leave_type', 'start_date', 'end_date', 'num_days', 'status', 'reviewed_by')
    list_filter = ('status', 'leave_type', 'start_date')
    search_fields = ('employee__user__username', 'employee__user__first_name', 'employee__user__last_name', 'reason')
