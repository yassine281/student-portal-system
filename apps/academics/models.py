from django.core.exceptions import ValidationError
from django.db import connection, models
from apps.accounts.models import TimeStampedModel


class Department(TimeStampedModel):
    code = models.CharField(max_length=15, unique=True)
    name = models.CharField(max_length=120)
    faculty_name = models.CharField(
        max_length=120,
        default='Faculty of Systems Engineering & Computing',
    )
    description = models.TextField(blank=True)

    def __str__(self) -> str:
        return f"{self.code} — {self.name}"


class AcademicSemester(TimeStampedModel):
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=80)
    start_date = models.DateField()
    end_date = models.DateField()
    is_current = models.BooleanField(default=False)
    enrollment_open = models.BooleanField(default=True)

    def __str__(self) -> str:
        status = "Active" if self.is_current else "Archived"
        return f"{self.name} ({status})"


class Course(TimeStampedModel):
    code = models.CharField(max_length=20, unique=True)
    title = models.CharField(max_length=140)
    description = models.TextField(blank=True)
    credits = models.PositiveSmallIntegerField(default=4)
    max_capacity = models.PositiveSmallIntegerField(default=35)
    department = models.ForeignKey(
        Department,
        on_delete=models.CASCADE,
        related_name='courses',
    )
    instructor = models.ForeignKey(
        'accounts.Instructor',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_courses',
    )
    semester = models.ForeignKey(
        AcademicSemester,
        on_delete=models.CASCADE,
        related_name='courses',
    )
    prerequisite = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='dependent_courses',
    )
    schedule_days = models.CharField(max_length=50, default='Mon / Wed')
    schedule_time = models.CharField(max_length=50, default='09:00 - 10:30')
    room_number = models.CharField(max_length=30, default='Lab A-304')

    @property
    def enrolled_count(self) -> int:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) FROM academics_enrollment WHERE course_id = %s AND status = 'ENROLLED'",
                [self.id],
            )
            return int(cursor.fetchone()[0])

    @property
    def remaining_seats(self) -> int:
        return max(0, self.max_capacity - self.enrolled_count)

    @property
    def is_full(self) -> bool:
        return self.remaining_seats <= 0

    def can_student_enroll(self, student) -> tuple[bool, str]:
        """Validates course enrollment rules using Pure Raw SQL (No ORM)."""
        from apps.academics.sql_repository import RawSQLPortalRepository
        student_pk = student['student_pk'] if isinstance(student, dict) else student.id
        return RawSQLPortalRepository.check_enrollment_eligibility_sql(student_pk, self.id)

    def __str__(self) -> str:
        return f"{self.code}: {self.title} ({self.credits} Cr)"


class Enrollment(TimeStampedModel):
    class Status(models.TextChoices):
        ENROLLED = 'ENROLLED', 'Enrolled'
        COMPLETED = 'COMPLETED', 'Completed'
        WITHDRAWN = 'WITHDRAWN', 'Withdrawn'

    student = models.ForeignKey(
        'accounts.Student',
        on_delete=models.CASCADE,
        related_name='enrollments',
    )
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='enrollments',
    )
    semester = models.ForeignKey(
        AcademicSemester,
        on_delete=models.CASCADE,
        related_name='enrollments',
    )
    status = models.CharField(
        max_length=15,
        choices=Status.choices,
        default=Status.ENROLLED,
    )

    class Meta:
        unique_together = ('student', 'course', 'semester')

    def course_attendance_percentage(self) -> float:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    COALESCE(
                        ROUND(
                            100.0 * SUM(CASE WHEN status IN ('PRESENT', 'LATE', 'EXCUSED') THEN 1 ELSE 0 END)
                            / NULLIF(COUNT(id), 0),
                            1
                        ),
                        100.0
                    )
                FROM academics_attendance
                WHERE enrollment_id = %s
                """,
                [self.id],
            )
            return float(cursor.fetchone()[0])

    def __str__(self) -> str:
        return f"{self.student.student_id} -> {self.course.code} ({self.status})"


class Attendance(TimeStampedModel):
    class Status(models.TextChoices):
        PRESENT = 'PRESENT', 'Present'
        ABSENT = 'ABSENT', 'Absent'
        LATE = 'LATE', 'Late'
        EXCUSED = 'EXCUSED', 'Excused'

    enrollment = models.ForeignKey(
        Enrollment,
        on_delete=models.CASCADE,
        related_name='attendance_records',
    )
    session_date = models.DateField()
    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.PRESENT,
    )
    remarks = models.CharField(max_length=150, blank=True)

    class Meta:
        unique_together = ('enrollment', 'session_date')
        ordering = ['-session_date']

    def __str__(self) -> str:
        return f"{self.enrollment.student.student_id} | {self.enrollment.course.code} | {self.session_date}: {self.status}"


class Grade(TimeStampedModel):
    enrollment = models.OneToOneField(
        Enrollment,
        on_delete=models.CASCADE,
        related_name='grade',
    )
    assignment_score = models.FloatField(default=0.0)
    midterm_score = models.FloatField(default=0.0)
    final_exam_score = models.FloatField(default=0.0)
    total_percentage = models.FloatField(default=0.0, editable=False)
    letter_grade = models.CharField(max_length=4, default='F', editable=False)
    grade_points = models.FloatField(default=0.0, editable=False)

    def compute_weighted_metrics(self) -> None:
        for label, score in [
            ('Assignment', self.assignment_score),
            ('Midterm', self.midterm_score),
            ('Final Exam', self.final_exam_score),
        ]:
            if score < 0.0 or score > 100.0:
                raise ValidationError(f"{label} score must be between 0 and 100.")

        self.total_percentage = round(
            (self.assignment_score * 0.30)
            + (self.midterm_score * 0.30)
            + (self.final_exam_score * 0.40),
            2,
        )

        pct = self.total_percentage
        if pct >= 93:
            self.letter_grade, self.grade_points = 'A', 4.0
        elif pct >= 90:
            self.letter_grade, self.grade_points = 'A-', 3.7
        elif pct >= 87:
            self.letter_grade, self.grade_points = 'B+', 3.3
        elif pct >= 83:
            self.letter_grade, self.grade_points = 'B', 3.0
        elif pct >= 80:
            self.letter_grade, self.grade_points = 'B-', 2.7
        elif pct >= 77:
            self.letter_grade, self.grade_points = 'C+', 2.3
        elif pct >= 73:
            self.letter_grade, self.grade_points = 'C', 2.0
        elif pct >= 70:
            self.letter_grade, self.grade_points = 'C-', 1.7
        elif pct >= 60:
            self.letter_grade, self.grade_points = 'D', 1.0
        else:
            self.letter_grade, self.grade_points = 'F', 0.0

    def save(self, *args, **kwargs):
        self.compute_weighted_metrics()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.enrollment.student.student_id} - {self.enrollment.course.code}: {self.letter_grade} ({self.grade_points})"


class Assignment(TimeStampedModel):
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='assignments',
    )
    title = models.CharField(max_length=140)
    description = models.TextField()
    due_date = models.DateTimeField()
    max_score = models.FloatField(default=100.0)

    def __str__(self) -> str:
        return f"{self.course.code} — {self.title}"


class Submission(TimeStampedModel):
    assignment = models.ForeignKey(
        Assignment,
        on_delete=models.CASCADE,
        related_name='submissions',
    )
    student = models.ForeignKey(
        'accounts.Student',
        on_delete=models.CASCADE,
        related_name='submissions',
    )
    submitted_file = models.FileField(upload_to='submissions/', blank=True, null=True)
    notes = models.TextField(blank=True)
    score = models.FloatField(null=True, blank=True)
    feedback = models.TextField(blank=True)

    class Meta:
        unique_together = ('assignment', 'student')

    def __str__(self) -> str:
        return f"{self.student.student_id} -> {self.assignment.title}"


class Examination(TimeStampedModel):
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='examinations',
    )
    title = models.CharField(max_length=120)
    exam_date = models.DateTimeField()
    room_number = models.CharField(max_length=40, default='Main Auditorium B-101')
    duration_minutes = models.PositiveSmallIntegerField(default=120)

    class Meta:
        ordering = ['exam_date']

    def __str__(self) -> str:
        return f"{self.course.code} - {self.title}"