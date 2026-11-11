from django.contrib.auth.models import AbstractUser
from django.db import models
from django.urls import reverse


class TimeStampedModel(models.Model):
    """
    ABSTRACT BASE CLASS (OOP Abstraction & Inheritance):
    Provides automatic created_at and updated_at audit fields to all child models.
    """
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class User(AbstractUser):
    """
    CORE USER ENTITY (OOP Inheritance & Polymorphism):
    Extends Django's AbstractUser with Role-Based Access Control (RBAC).
    """
    class Role(models.TextChoices):
        STUDENT = 'STUDENT', 'Student'
        INSTRUCTOR = 'INSTRUCTOR', 'Instructor'
        ADMINISTRATOR = 'ADMINISTRATOR', 'Administrator'

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.STUDENT,
    )
    phone_number = models.CharField(max_length=25, blank=True)
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)

    def get_full_display_name(self) -> str:
        full_name = f"{self.first_name} {self.last_name}".strip()
        return full_name if full_name else self.username

    def get_dashboard_url(self) -> str:
        if self.role == self.Role.ADMINISTRATOR or self.is_superuser:
            return reverse('admin_dashboard')
        if self.role == self.Role.INSTRUCTOR:
            return reverse('instructor_dashboard')
        return reverse('student_dashboard')

    @property
    def is_student(self) -> bool:
        return self.role == self.Role.STUDENT

    @property
    def is_instructor(self) -> bool:
        return self.role == self.Role.INSTRUCTOR

    @property
    def is_administrator(self) -> bool:
        return self.role == self.Role.ADMINISTRATOR or self.is_superuser

    def __str__(self) -> str:
        return f"{self.get_full_display_name()} ({self.get_role_display()})"


class Student(TimeStampedModel):
    """
    STUDENT DOMAIN ENTITY:
    Delegates GPA and attendance calculations to Pure Raw SQL aggregations.
    """
    class AcademicStatus(models.TextChoices):
        GOOD_STANDING = 'GOOD_STANDING', 'Good Standing'
        HONORS = 'HONORS', 'Dean’s Honors List'
        PROBATION = 'PROBATION', 'Academic Probation'

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='student_profile',
    )
    student_id = models.CharField(max_length=25, unique=True)
    department = models.ForeignKey(
        'academics.Department',
        on_delete=models.PROTECT,
        related_name='students',
    )
    current_semester_number = models.PositiveSmallIntegerField(default=1)
    admission_year = models.PositiveIntegerField(default=2026)
    academic_status = models.CharField(
        max_length=20,
        choices=AcademicStatus.choices,
        default=AcademicStatus.GOOD_STANDING,
    )

    def calculate_gpa(self) -> float:
        """Computes credit-weighted cumulative GPA via Raw SQL JOIN (No ORM)."""
        from apps.academics.sql_repository import RawSQLPortalRepository
        summary = RawSQLPortalRepository.get_student_analytical_summary_sql(self.id)
        return summary['gpa']

    def calculate_attendance_percentage(self) -> float:
        """Computes overall attendance percentage via Raw SQL JOIN (No ORM)."""
        from apps.academics.sql_repository import RawSQLPortalRepository
        summary = RawSQLPortalRepository.get_student_analytical_summary_sql(self.id)
        return summary['attendance_pct']

    @property
    def has_attendance_warning(self) -> bool:
        return self.calculate_attendance_percentage() < 75.0

    def __str__(self) -> str:
        return f"{self.student_id} - {self.user.get_full_display_name()}"


class Instructor(TimeStampedModel):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='instructor_profile',
    )
    employee_id = models.CharField(max_length=25, unique=True)
    academic_title = models.CharField(max_length=60, default='Associate Professor')
    department = models.ForeignKey(
        'academics.Department',
        on_delete=models.PROTECT,
        related_name='instructors',
    )
    office_location = models.CharField(max_length=50, default='Building A, Room 204')

    def __str__(self) -> str:
        return f"{self.academic_title} {self.user.get_full_display_name()} ({self.employee_id})"


class Administrator(TimeStampedModel):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='administrator_profile',
    )
    employee_id = models.CharField(max_length=25, unique=True)
    office_title = models.CharField(max_length=80, default='Chief Academic Registrar')
    clearance_level = models.PositiveSmallIntegerField(default=3)

    def __str__(self) -> str:
        return f"{self.user.get_full_display_name()} - {self.office_title}"


class Notification(TimeStampedModel):
    class Category(models.TextChoices):
        ACADEMIC = 'ACADEMIC', 'Academic Announcement'
        ATTENDANCE = 'ATTENDANCE', 'Attendance Warning'
        GRADE = 'GRADE', 'Grade Published'
        ASSIGNMENT = 'ASSIGNMENT', 'Assignment Deadline'

    recipient = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='notifications',
    )
    category = models.CharField(
        max_length=20,
        choices=Category.choices,
        default=Category.ACADEMIC,
    )
    title = models.CharField(max_length=140)
    message = models.TextField()
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f"[{self.category}] {self.title} -> {self.recipient.username}"