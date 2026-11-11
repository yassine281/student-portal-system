from datetime import date
from django.db import connection
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from apps.accounts.models import User, Student, Instructor, Administrator
from apps.academics.models import Department, AcademicSemester, Course
from apps.academics.sql_repository import RawSQLPortalRepository


class StudentPortalRawSQLAndOOPTests(TestCase):
    """
    Automated Unit & Integration Test Suite verifying Pure Raw SQL CRUD,
    Analytical Aggregations, OOP Encapsulation, Polymorphism, and RBAC Security.
    """

    def setUp(self):
        self.client = Client()
        now_ts = timezone.now()

        # Seed foundational test entities using Raw SQL INSERTs
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO academics_department (code, name, faculty_name, description, created_at, updated_at)
                VALUES ('SEC', 'Systems Engineering & Computing', 'Faculty of Informatics', '', %s, %s)
                """,
                [now_ts, now_ts],
            )
            self.dept_id = cursor.lastrowid

            cursor.execute(
                """
                INSERT INTO academics_academicsemester
                    (code, name, start_date, end_date, is_current, enrollment_open, created_at, updated_at)
                VALUES ('FALL-2026', 'Fall Semester 2026/2027', %s, %s, 1, 1, %s, %s)
                """,
                [date(2026, 9, 1), date(2027, 1, 25), now_ts, now_ts],
            )
            self.semester_id = cursor.lastrowid

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
            department_id=self.dept_id,
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
            department_id=self.dept_id,
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

        self.course_base = Course.objects.create(
            code='SEC-201',
            title='Data Structures & Algorithms',
            credits=4,
            max_capacity=30,
            department_id=self.dept_id,
            instructor=self.instructor,
            semester_id=self.semester_id,
        )
        self.course_advanced = Course.objects.create(
            code='AERO-409',
            title='Autonomous Flight Control',
            credits=3,
            max_capacity=20,
            department_id=self.dept_id,
            instructor=self.instructor,
            semester_id=self.semester_id,
            prerequisite=self.course_base,
        )

    def test_1_polymorphic_role_dashboard_routing(self):
        self.assertEqual(self.student_user.get_dashboard_url(), reverse('student_dashboard'))
        self.assertEqual(self.instructor_user.get_dashboard_url(), reverse('instructor_dashboard'))
        self.assertEqual(self.admin_user.get_dashboard_url(), reverse('admin_dashboard'))

    def test_2_raw_sql_enrollment_and_weighted_gpa_calculation(self):
        ok, _ = RawSQLPortalRepository.enroll_student_sql(self.student.id, self.course_base.id)
        self.assertTrue(ok)

        enrollments = RawSQLPortalRepository.get_student_enrollments(self.student.id, only_active=True)
        self.assertEqual(len(enrollments), 1)
        enrollment_id = enrollments[0]['enrollment_id']

        grade_res = RawSQLPortalRepository.upsert_grade_sql(enrollment_id, 90.0, 90.0, 95.0)
        self.assertEqual(grade_res['total_percentage'], 92.0)
        self.assertEqual(grade_res['letter_grade'], 'A-')
        self.assertEqual(grade_res['grade_points'], 3.7)
        self.assertEqual(self.student.calculate_gpa(), 3.70)

    def test_3_raw_sql_attendance_percentage_and_warning_alert(self):
        RawSQLPortalRepository.enroll_student_sql(self.student.id, self.course_base.id)
        enrollment_id = RawSQLPortalRepository.get_student_enrollments(self.student.id)[0]['enrollment_id']

        RawSQLPortalRepository.record_attendance_sql(enrollment_id, '2026-10-01', 'PRESENT')
        RawSQLPortalRepository.record_attendance_sql(enrollment_id, '2026-10-02', 'PRESENT')
        RawSQLPortalRepository.record_attendance_sql(enrollment_id, '2026-10-03', 'ABSENT')
        RawSQLPortalRepository.record_attendance_sql(enrollment_id, '2026-10-04', 'ABSENT')

        self.assertEqual(self.student.calculate_attendance_percentage(), 50.0)
        self.assertTrue(self.student.has_attendance_warning)

    def test_4_raw_sql_prerequisite_validation_blocks_unqualified_enrollment(self):
        allowed, reason = self.course_advanced.can_student_enroll(self.student)
        self.assertFalse(allowed)
        self.assertIn('Prerequisite not met', reason)

        RawSQLPortalRepository.enroll_student_sql(self.student.id, self.course_base.id)
        enrollment_id = RawSQLPortalRepository.get_student_enrollments(self.student.id)[0]['enrollment_id']
        RawSQLPortalRepository.upsert_grade_sql(enrollment_id, 95.0, 95.0, 95.0)

        allowed_after, _ = self.course_advanced.can_student_enroll(self.student)
        self.assertTrue(allowed_after)

    def test_5_raw_sql_analytical_queries_return_department_and_course_metrics(self):
        dept_stats = RawSQLPortalRepository.get_department_performance_analytics_sql(self.dept_id)
        self.assertEqual(len(dept_stats), 1)
        self.assertEqual(dept_stats[0]['department_code'], 'SEC')

        course_stats = RawSQLPortalRepository.get_course_analytics_report_sql(self.dept_id)
        self.assertEqual(len(course_stats), 2)

    def test_6_rbac_security_blocks_student_from_admin_dashboard(self):
        self.client.login(username='test_student', password='TestPassword123!')

        response_student = self.client.get(reverse('student_dashboard'))
        self.assertEqual(response_student.status_code, 200)

        response_admin = self.client.get(reverse('admin_dashboard'))
        self.assertEqual(response_admin.status_code, 302)
        self.assertEqual(response_admin.url, reverse('student_dashboard'))