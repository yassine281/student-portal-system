from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, Student, Instructor, Administrator, Notification


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'role', 'is_active')
    list_filter = ('role', 'is_active')
    fieldsets = UserAdmin.fieldsets + (
        ('Institutional Role & Profile', {'fields': ('role', 'phone_number', 'avatar')}),
    )


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ('student_id', 'user', 'department', 'current_semester_number', 'academic_status')
    search_fields = ('student_id', 'user__username', 'user__first_name', 'user__last_name')


@admin.register(Instructor)
class InstructorAdmin(admin.ModelAdmin):
    list_display = ('employee_id', 'user', 'academic_title', 'department', 'office_location')


@admin.register(Administrator)
class AdministratorAdmin(admin.ModelAdmin):
    list_display = ('employee_id', 'user', 'office_title', 'clearance_level')


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('title', 'recipient', 'category', 'is_read', 'created_at')
    list_filter = ('category', 'is_read')