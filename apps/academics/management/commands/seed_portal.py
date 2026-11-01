from datetime import date, timedelta
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from apps.accounts.models import User, Student, Instructor, Administrator, Notification
from apps.academics.models import (
    Department,
    AcademicSemester,
    Course,
    Enrollment,
    Attendance,
    Grade,
    Assignment,
    Examination,
)


class Command(BaseCommand):
    help = 'Seeds the Student Portal database with realistic university accounts, courses, grades, and attendance.'

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('Starting Student Portal database seed...'))

        # 1. Create Departments
        dept_sec, _ = Department.objects.update_or_create(
            code='SEC',
            defaults={
                'name': 'Systems Engineering & Computing',
                'faculty_name': 'Faculty of Informatics & Computer Engineering',
                'description': 'Covers software architecture, distributed systems, and algorithmic optimization.',
            },
        )
        dept_cs, _ = Department.objects.update_or_create(
            code='CSAI',
            defaults={
                'name': 'Computer Science & Applied AI',
                'faculty_name': 'Faculty of Informatics & Computer Engineering',
                'description': 'Covers machine intelligence, data engineering, and computational mathematics.',
            },
        )

        # 2. Create Academic Semesters
        sem_spring, _ = AcademicSemester.objects.update_or_create(
            code='SPRING-2026',
            defaults={
                'name': 'Spring Semester 2025/2026',
                'start_date': date(2026, 2, 1),
                'end_date': date(2026, 6, 30),
                'is_current': False,
                'enrollment_open': False,
            },
        )
        sem_fall, _ = AcademicSemester.objects.update_or_create(
            code='FALL-2026',
            defaults={
                'name': 'Fall Semester 2026/2027',
                'start_date': date(2026, 9, 1),
                'end_date': date(2027, 1, 25),
                'is_current': True,
                'enrollment_open': True,
            },
        )

        # 3. Create Administrator User & Profile
        admin_user, _ = User.objects.update_or_create(
            username='admin',
            defaults={
                'email': 'admin@university.edu',
                'first_name': 'Elena',
                'last_name': 'Rostova',
                'role': User.Role.ADMINISTRATOR,
                'is_staff': True,
                'is_superuser': True,
            },
        )
        admin_user.set_password('Portal2026!')
        admin_user.save()

        Administrator.objects.update_or_create(
            user=admin_user,
            defaults={
                'employee_id': 'ADM-2026-001',
                'office_title': 'Chief Academic Registrar',
                'clearance_level': 3,
            },
        )

        # 4. Create Instructor User & Profile
        inst_user, _ = User.objects.update_or_create(
            username='instructor',
            defaults={
                'email': 'v.sokolov@university.edu',
                'first_name': 'Viktor',
                'last_name': 'Sokolov',
                'role': User.Role.INSTRUCTOR,
            },
        )
        inst_user.set_password('Portal2026!')
        inst_user.save()

        instructor, _ = Instructor.objects.update_or_create(
            user=inst_user,
            defaults={
                'employee_id': 'INST-4092',
                'academic_title': 'Professor of Distributed Systems',
                'department': dept_sec,
                'office_location': 'Engineering Block A, Room 310',
            },
        )

        # 5. Create Student User & Profile
        stud_user, _ = User.objects.update_or_create(
            username='student',
            defaults={
                'email': 'yassine.m@university.edu',
                'first_name': 'Yassine',
                'last_name': 'Mouri',
                'role': User.Role.STUDENT,
                'phone_number': '+7 (900) 555-0199',
            },
        )
        stud_user.set_password('Portal2026!')
        stud_user.save()

        student, _ = Student.objects.update_or_create(
            user=stud_user,
            defaults={
                'student_id': 'SEC-2024-0891',
                'department': dept_sec,
                'current_semester_number': 5,
                'admission_year': 2024,
                'academic_status': Student.AcademicStatus.HONORS,
            },
        )

        # 6. Create Courses (Including Prerequisite Chains)
        course_sec201, _ = Course.objects.update_or_create(
            code='SEC-201',
            defaults={
                'title': 'Data Structures & Algorithmic Optimization',
                'description': 'Graph algorithms, trees, numerical optimization, and complexity analysis.',
                'credits': 4,
                'max_capacity': 35,
                'department': dept_sec,
                'instructor': instructor,
                'semester': sem_spring,
                'schedule_days': 'Mon / Wed',
                'schedule_time': '09:00 - 10:30',
                'room_number': 'Lab A-201',
            },
        )

        course_sec301, _ = Course.objects.update_or_create(
            code='SEC-301',
            defaults={
                'title': 'Object-Oriented Systems Architecture',
                'description': 'SOLID principles, design patterns, domain-driven design, and full-stack systems.',
                'credits': 4,
                'max_capacity': 35,
                'department': dept_sec,
                'instructor': instructor,
                'semester': sem_fall,
                'prerequisite': course_sec201,
                'schedule_days': 'Mon / Wed',
                'schedule_time': '10:00 - 11:30',
                'room_number': 'Lab A-304',
            },
        )

        course_sec302, _ = Course.objects.update_or_create(
            code='SEC-302',
            defaults={
                'title': 'Database Systems & Transaction Engines',
                'description': 'Relational algebra, ACID transactions, indexing, and ORM query optimization.',
                'credits': 4,
                'max_capacity': 30,
                'department': dept_sec,
                'instructor': instructor,
                'semester': sem_fall,
                'schedule_days': 'Tue / Thu',
                'schedule_time': '11:00 - 12:30',
                'room_number': 'Hall B-108',
            },
        )

        course_sec305, _ = Course.objects.update_or_create(
            code='SEC-305',
            defaults={
                'title': 'Distributed Systems & Real-Time Control',
                'description': 'Consensus algorithms, network fault tolerance, and telemetry architectures.',
                'credits': 4,
                'max_capacity': 25,
                'department': dept_sec,
                'instructor': instructor,
                'semester': sem_fall,
                'prerequisite': course_sec201,
                'schedule_days': 'Fri',
                'schedule_time': '14:00 - 17:00',
                'room_number': 'Lab C-210',
            },
        )

        course_aero409, _ = Course.objects.update_or_create(
            code='AERO-409',
            defaults={
                'title': 'Autonomous Flight Control & Guidance Systems',
                'description': 'State-space control, Kalman filtering, and aerospace navigation dynamics.',
                'credits': 3,
                'max_capacity': 20,
                'department': dept_cs,
                'instructor': instructor,
                'semester': sem_fall,
                'prerequisite': course_sec305,  # Unmet prerequisite to test OOP validation!
                'schedule_days': 'Thu',
                'schedule_time': '15:00 - 17:30',
                'room_number': 'Sim Lab D-12',
            },
        )

        # 7. Create Enrollments & Grades
        enroll_201, _ = Enrollment.objects.update_or_create(
            student=student,
            course=course_sec201,
            semester=sem_spring,
            defaults={'status': Enrollment.Status.COMPLETED},
        )
        Grade.objects.update_or_create(
            enrollment=enroll_201,
            defaults={
                'assignment_score': 95.0,
                'midterm_score': 92.0,
                'final_exam_score': 96.0,
            },
        )

        enroll_301, _ = Enrollment.objects.update_or_create(
            student=student,
            course=course_sec301,
            semester=sem_fall,
            defaults={'status': Enrollment.Status.ENROLLED},
        )
        Grade.objects.update_or_create(
            enrollment=enroll_301,
            defaults={
                'assignment_score': 91.0,
                'midterm_score': 88.0,
                'final_exam_score': 90.0,
            },
        )

        enroll_302, _ = Enrollment.objects.update_or_create(
            student=student,
            course=course_sec302,
            semester=sem_fall,
            defaults={'status': Enrollment.Status.ENROLLED},
        )
        Grade.objects.update_or_create(
            enrollment=enroll_302,
            defaults={
                'assignment_score': 86.0,
                'midterm_score': 84.0,
                'final_exam_score': 88.0,
            },
        )

        # 8. Seed Attendance Records (10 sessions across enrolled courses)
        today = date.today()
        for day_offset in range(1, 6):
            session_dt = today - timedelta(days=day_offset * 3)
            Attendance.objects.update_or_create(
                enrollment=enroll_301,
                session_date=session_dt,
                defaults={'status': Attendance.Status.PRESENT, 'remarks': 'On time'},
            )
            Attendance.objects.update_or_create(
                enrollment=enroll_302,
                session_date=session_dt,
                defaults={
                    'status': Attendance.Status.ABSENT if day_offset == 2 else Attendance.Status.PRESENT,
                    'remarks': 'Verified session log',
                },
            )

        # 9. Seed Assignments & Upcoming Examinations
        Assignment.objects.update_or_create(
            course=course_sec301,
            title='Milestone 1: OOP Domain Model & UML Class Architecture',
            defaults={
                'description': 'Submit your complete Python domain classes demonstrating Inheritance, Encapsulation, and Polymorphism.',
                'due_date': timezone.now() + timedelta(days=7),
                'max_score': 100.0,
            },
        )
        Assignment.objects.update_or_create(
            course=course_sec302,
            title='Lab 2: ACID Transactions & Relational Schema Normalization',
            defaults={
                'description': 'Design a 3NF normalized schema and verify atomic seat reservation queries.',
                'due_date': timezone.now() + timedelta(days=12),
                'max_score': 100.0,
            },
        )

        Examination.objects.update_or_create(
            course=course_sec301,
            title='Midterm Examination — Systems Architecture',
            defaults={
                'exam_date': timezone.now() + timedelta(days=14),
                'room_number': 'Auditorium A-101',
                'duration_minutes': 90,
            },
        )
        Examination.objects.update_or_create(
            course=course_sec302,
            title='Midterm Examination — Database Engines',
            defaults={
                'exam_date': timezone.now() + timedelta(days=18),
                'room_number': 'Hall B-204',
                'duration_minutes': 120,
            },
        )

        # 10. Seed Notifications
        Notification.objects.update_or_create(
            recipient=stud_user,
            title='Welcome to Fall Semester 2026/2027',
            defaults={
                'category': Notification.Category.ACADEMIC,
                'message': 'Course registration for Fall 2026/2027 is now open. Prerequisite verification is active.',
                'is_read': False,
            },
        )
        Notification.objects.update_or_create(
            recipient=stud_user,
            title='Grade Published: SEC-301 Midterm Assessment',
            defaults={
                'category': Notification.Category.GRADE,
                'message': 'Prof. Viktor Sokolov published updated component scores for SEC-301.',
                'is_read': False,
            },
        )

        self.stdout.write(self.style.SUCCESS('✅ Database seeded! Demo accounts ready (Password: Portal2026!):'))
        self.stdout.write(self.style.SUCCESS('   • Student:       username="student"    | email="yassine.m@university.edu"'))
        self.stdout.write(self.style.SUCCESS('   • Instructor:    username="instructor" | email="v.sokolov@university.edu"'))
        self.stdout.write(self.style.SUCCESS('   • Administrator: username="admin"      | email="admin@university.edu"'))