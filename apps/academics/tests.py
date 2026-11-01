from datetime import date
from django.test import TestCase, Client
from django.urls import reverse
from apps.accounts.models import User, Student, Instructor, Administrator
from apps.academics.models import (
    Department,
    AcademicSemester,
    Course,
    Enrollment,
    Attendance,
    Grade,
)


class StudentPortalOOPAndSecurityTests(TestCase):
    """
    Automated Unit & Integration Test Suite for the Student Portal System.
    Verifies OOP Encapsulation, Polymorphism, GPA Calculation, Prerequisite Locks,
    Attendance Warnings, and Role-Based Access Control (RBAC).
    """

    def setUp(self):
        """Runs automatically before every test method to prepare clean test objects."""
        self.client = Client()

        # 1. Create Department & Active Semester
        self.dept = Department.objects.create(
            code='SEC',
            name='Systems Engineering & Computing',
        )
        self.semester = AcademicSemester.objects.create(
            code='FALL-2026',
            name='Fall Semester 2026/2027',
            start_date=date(2026, 9, 1),
            end_date=date(2027, 1, 25),
            is_current=True,
            enrollment_open=True,
        )

        # 2. Create Student, Instructor, and Admin Users
        self.student_user = User.objects.create_user(
            username='test_student',
            email='student@university.edu',
            password='TestPassword123!',
            first_name='Yassine',
            last_name='Mouri',
            role=User.Role.STUDENT,
        )
        self.student = Student.objects.create(
            user=self.student_user,
            student_id='SEC-2026-001',
            department=self.dept,
            current_semester_number=5,
        )

        self.instructor_user = User.objects.create_user(
            username='test_instructor',
            email='instructor@university.edu',
            password='TestPassword123!',
            first_name='Viktor',
            last_name='Sokolov',
            role=User.Role.INSTRUCTOR,
        )
        self.instructor = Instructor.objects.create(
            user=self.instructor_user,
            employee_id='INST-001',
            department=self.dept,
        )

        self.admin_user = User.objects.create_user(
            username='test_admin',
            email='admin@university.edu',
            password='TestPassword123!',
            first_name='Elena',
            last_name='Rostova',
            role=User.Role.ADMINISTRATOR,
        )
        Administrator.objects.create(
            user=self.admin_user,
            employee_id='ADM-001',
        )

        # 3. Create Base Course & Advanced Course (with Prerequisite)
        self.course_base = Course.objects.create(
            code='SEC-201',
            title='Data Structures & Algorithms',
            credits=4,
            max_capacity=30,
            department=self.dept,
            instructor=self.instructor,
            semester=self.semester,
        )
        self.course_advanced = Course.objects.create(
            code='AERO-409',
            title='Autonomous Flight Control',
            credits=3,
            max_capacity=20,
            department=self.dept,
            instructor=self.instructor,
            semester=self.semester,
            prerequisite=self.course_base,
        )

    def test_1_polymorphic_role_dashboard_routing(self):
        """Verifies OOP Polymorphism: get_dashboard_url() routes each role accurately."""
        self.assertEqual(self.student_user.get_dashboard_url(), reverse('student_dashboard'))
        self.assertEqual(self.instructor_user.get_dashboard_url(), reverse('instructor_dashboard'))
        self.assertEqual(self.admin_user.get_dashboard_url(), reverse('admin_dashboard'))

    def test_2_weighted_grade_and_cumulative_gpa_calculation(self):
        """Verifies OOP Encapsulation: 30/30/40 grade weighting and 4.00 GPA calculation."""
        enrollment = Enrollment.objects.create(
            student=self.student,
            course=self.course_base,
            semester=self.semester,
            status=Enrollment.Status.ENROLLED,
        )
        # 90 * 0.30 (27) + 90 * 0.30 (27) + 95 * 0.40 (38) = 92.0% -> Letter 'A-', 3.7 Points
        grade = Grade.objects.create(
            enrollment=enrollment,
            assignment_score=90.0,
            midterm_score=90.0,
            final_exam_score=95.0,
        )

        self.assertEqual(grade.total_percentage, 92.0)
        self.assertEqual(grade.letter_grade, 'A-')
        self.assertEqual(grade.grade_points, 3.7)
        self.assertEqual(self.student.calculate_gpa(), 3.70)

    def test_3_attendance_percentage_and_early_warning_alert(self):
        """Verifies that attendance below 75.0% triggers the early-warning alert."""
        enrollment = Enrollment.objects.create(
            student=self.student,
            course=self.course_base,
            semester=self.semester,
        )
        # 2 Present, 2 Absent = 50.0% Attendance (< 75.0% threshold)
        Attendance.objects.create(enrollment=enrollment, session_date=date(2026, 10, 1), status=Attendance.Status.PRESENT)
        Attendance.objects.create(enrollment=enrollment, session_date=date(2026, 10, 2), status=Attendance.Status.PRESENT)
        Attendance.objects.create(enrollment=enrollment, session_date=date(2026, 10, 3), status=Attendance.Status.ABSENT)
        Attendance.objects.create(enrollment=enrollment, session_date=date(2026, 10, 4), status=Attendance.Status.ABSENT)

        self.assertEqual(self.student.calculate_attendance_percentage(), 50.0)
        self.assertTrue(self.student.has_attendance_warning)

    def test_4_prerequisite_validation_blocks_unqualified_enrollment(self):
        """Verifies that enrolling in AERO-409 is blocked until SEC-201 is passed."""
        allowed, reason = self.course_advanced.can_student_enroll(self.student)
        self.assertFalse(allowed)
        self.assertIn('Prerequisite not met', reason)

        # Now complete prerequisite SEC-201 with passing grade (95% -> 4.0 GPA)
        prereq_enrollment = Enrollment.objects.create(
            student=self.student,
            course=self.course_base,
            semester=self.semester,
            status=Enrollment.Status.COMPLETED,
        )
        Grade.objects.create(
            enrollment=prereq_enrollment,
            assignment_score=95.0,
            midterm_score=95.0,
            final_exam_score=95.0,
        )

        allowed_after, _ = self.course_advanced.can_student_enroll(self.student)
        self.assertTrue(allowed_after)

    def test_5_course_capacity_limit_prevents_over_enrollment(self):
        """Verifies that a course with 0 remaining seats rejects new enrollments."""
        small_course = Course.objects.create(
            code='SEC-999',
            title='Capstone Seminar',
            credits=2,
            max_capacity=1,
            department=self.dept,
            instructor=self.instructor,
            semester=self.semester,
        )
        # Fill the single seat with another student
        other_user = User.objects.create_user(username='other_stud', password='TestPassword123!')
        other_student = Student.objects.create(
            user=other_user,
            student_id='SEC-2026-002',
            department=self.dept,
        )
        Enrollment.objects.create(
            student=other_student,
            course=small_course,
            semester=self.semester,
            status=Enrollment.Status.ENROLLED,
        )

        allowed, reason = small_course.can_student_enroll(self.student)
        self.assertFalse(allowed)
        self.assertIn('full capacity', reason)

    def test_6_rbac_security_blocks_student_from_admin_dashboard(self):
        """Verifies Role-Based Access Control: Students cannot access Administrator views."""
        self.client.login(username='test_student', password='TestPassword123!')

        # Student dashboard should return HTTP 200 OK
        response_student = self.client.get(reverse('student_dashboard'))
        self.assertEqual(response_student.status_code, 200)

        # Admin dashboard should redirect (HTTP 302) back to student dashboard
        response_admin = self.client.get(reverse('admin_dashboard'))
        self.assertEqual(response_admin.status_code, 302)
        self.assertEqual(response_admin.url, reverse('student_dashboard'))