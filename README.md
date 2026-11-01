# Aether University — Enterprise Student Portal System

**Architecture:** Modular Monolith (Python 3 & Django 5.2 LTS)  
**Paradigm:** Object-Oriented Programming (OOP) with Encapsulation, Inheritance, Abstraction, and Polymorphism  
**Database:** Relational SQLite3 ORM with Atomic Transactions  

---

## 1. Project Overview
The **Aether University Student Portal System** is a full-stack academic management platform engineered for modern higher-education institutions. It provides strictly isolated Role-Based Access Control (RBAC) workspaces for **Students**, **Instructors**, and **Administrators**.

## 2. Object-Oriented Programming (OOP) Architecture
* **Abstraction & Inheritance:** `TimeStampedModel` serves as an abstract base class providing automatic audit timestamps (`created_at`, `updated_at`) across all domain models. `User` extends Django's `AbstractUser` to provide unified authentication.
* **Encapsulation:** Critical academic business rules are encapsulated directly inside domain entities:
  * `Student.calculate_gpa()` computes credit-weighted cumulative GPA on a 4.00 scale.
  * `Student.calculate_attendance_percentage()` and `has_attendance_warning` monitor the mandatory 75.0% attendance threshold.
  * `Course.can_student_enroll(student)` enforces seat capacity limits, duplicate checks, and prerequisite completion.
  * `Grade.compute_weighted_metrics()` automatically calculates weighted scores (30% Assignment, 30% Midterm, 40% Final Exam).
* **Polymorphism:** `User.get_dashboard_url()` dynamically resolves the workspace route based on the user's institutional role.

---

## 3. Quick Start & Execution (Windows 11)

```powershell
# 1. Activate Virtual Environment
.\.venv\Scripts\Activate.ps1

# 2. Install Dependencies
python -m pip install -r requirements.txt

# 3. Apply Database Migrations & Seed Demo Data
python manage.py migrate
python manage.py seed_portal

# 4. Run Automated Unit & Integration Tests
python manage.py test

# 5. Launch Development Server
python manage.py runserver
Role,Username,Institutional Email,Password
Student,student,yassine.m@university.edu,Portal2026!
Instructor,instructor,v.sokolov@university.edu,Portal2026!
Administrator,admin,admin@university.edu,Portal2026!
## LESSON 8 (PHASE 13): AUTOMATED UNIT & INTEGRATION TESTING (`python manage.py test`)

### STEP 1 — WHAT WE ARE BUILDING AND WHY IT MATTERS

In software engineering, **Automated Testing** means writing Python code that automatically tests your application's classes, methods, and web pages to prove there are no bugs.

When you run `python manage.py test` in the terminal:

1. Django creates a temporary, invisible test database in memory (so it **never** deletes or touches your real `db.sqlite3` data!).
2. It runs our test checks on your OOP methods (GPA math, attendance warnings, prerequisite locks, capacity limits, and role security).
3. It prints **`OK`** and destroys the temporary test database cleanly.

During your university defense, running `python manage.py test` live in front of your professors proves your software is professionally engineered.

---

### STEP 2 — CREATE THE AUTOMATED TEST SUITE (`apps/academics/tests.py`)

Let's create our complete test file inside `apps/academics` that tests **6 critical OOP and security rules**:

1. **Polymorphic Role Routing Test:** Verifies that `User.get_dashboard_url()` routes Students, Instructors, and Administrators to their exact workspace URLs.
2. **Encapsulated Grade & GPA Calculation Test:** Verifies that `Grade` calculates `30% Assignment + 30% Midterm + 40% Final Exam` accurately and `Student.calculate_gpa()` computes the exact credit-weighted `4.00` GPA.
3. **Attendance Threshold Warning Test:** Verifies that `Student.has_attendance_warning` triggers `True` when attendance drops below `75.0%`.
4. **OOP Prerequisite Lock Test:** Verifies that `Course.can_student_enroll()` blocks a student from enrolling in an advanced course if they haven't passed its prerequisite.
5. **Course Seat Capacity Test:** Verifies that a course with `max_capacity=1` blocks a second student from over-enrolling.
6. **Role-Based Access Control (RBAC) Security Test:** Verifies that a logged-in Student is blocked from accessing the Administrator dashboard.

#### How to Create `apps/academics/tests.py` in PyCharm:

1. In the left **Project** sidebar of PyCharm, expand **`apps`** and **right-click** on **`academics`** -> **New** -> **Python File**. *(If `tests.py` already exists inside `apps/academics`, simply double-click it to open it).*
2. Type **`tests`** and press **Enter**.
3. Press **`Ctrl + A`** to select everything, press **`Backspace`** to clear it completely, and paste this **100% complete code**:

```python
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

```

4. Press **`Ctrl + S`** to save `apps/academics/tests.py`.

---

### STEP 3 — RUN THE AUTOMATED TESTS IN PYCHARM TERMINAL

1. Click inside your PyCharm **Terminal** at the bottom of your screen.
*(If the web server is currently running, press **`Ctrl + C`** to pause it so your `(.venv) PS ...>` prompt appears).*


2. Type or paste this exact command and press **Enter**:

```powershell
python manage.py test

```

#### Expected Output (What You Should See):

```text
Found 6 test(s).
Creating test database for alias 'default'...
System check identified no issues (0 silenced).
......
----------------------------------------------------------------------
Ran 6 tests in 1.85s

OK
Destroying test database for alias 'default'...

```

* **What those 6 dots (`......`) mean:** Each dot `.` represents one passed test! Seeing `Ran 6 tests ... OK` means all 6 of your OOP, database, and security tests passed 100%.
* Afterward, if you want to start your live website again, simply run:
```powershell
python manage.py runserver

```



---

### STEP 4 — CREATE `requirements.txt` AND `README.md` FOR YOUR FINAL SUBMISSION

Every university software engineering submission requires two documentation files in the main project folder (`Student-portal`):

1. **`requirements.txt`** — Lists the Python packages needed to run your project.
2. **`README.md`** — Explains the project architecture, OOP design, installation steps, and demo credentials for your professors.

#### 4A. Create `requirements.txt`

1. In the left sidebar of PyCharm, **right-click** on the top folder **`Student-portal`** -> **New** -> **File**.


2. Type the exact name:
```text
requirements.txt

```


and press **Enter**.
3. Paste these two lines into **`requirements.txt`**:

```text
Django>=5.2,<6.0
Pillow>=10.0.0

```

4. Press **`Ctrl + S`** to save `requirements.txt`.

#### 4B. Create `README.md`

1. **Right-click** on the top folder **`Student-portal`** -> **New** -> **File**.


2. Type the exact name:
```text
README.md

```


and press **Enter**.
3. Copy and paste this complete academic documentation into **`README.md`**:

```markdown
# Aether University — Enterprise Student Portal System

**Architecture:** Modular Monolith (Python 3 & Django 5.2 LTS)  
**Paradigm:** Object-Oriented Programming (OOP) with Encapsulation, Inheritance, Abstraction, and Polymorphism  
**Database:** Relational SQLite3 ORM with Atomic Transactions  

---

## 1. Project Overview
The **Aether University Student Portal System** is a full-stack academic management platform engineered for modern higher-education institutions. It provides strictly isolated Role-Based Access Control (RBAC) workspaces for **Students**, **Instructors**, and **Administrators**.

## 2. Object-Oriented Programming (OOP) Architecture
* **Abstraction & Inheritance:** `TimeStampedModel` serves as an abstract base class providing automatic audit timestamps (`created_at`, `updated_at`) across all domain models. `User` extends Django's `AbstractUser` to provide unified authentication.
* **Encapsulation:** Critical academic business rules are encapsulated directly inside domain entities:
  * `Student.calculate_gpa()` computes credit-weighted cumulative GPA on a 4.00 scale.
  * `Student.calculate_attendance_percentage()` and `has_attendance_warning` monitor the mandatory 75.0% attendance threshold.
  * `Course.can_student_enroll(student)` enforces seat capacity limits, duplicate checks, and prerequisite completion.
  * `Grade.compute_weighted_metrics()` automatically calculates weighted scores (30% Assignment, 30% Midterm, 40% Final Exam).
* **Polymorphism:** `User.get_dashboard_url()` dynamically resolves the workspace route based on the user's institutional role.

---

## 3. Quick Start & Execution (Windows 11)

```powershell
# 1. Activate Virtual Environment
.\.venv\Scripts\Activate.ps1

# 2. Install Dependencies
python -m pip install -r requirements.txt

# 3. Apply Database Migrations & Seed Demo Data
python manage.py migrate
python manage.py seed_portal

# 4. Run Automated Unit & Integration Tests
python manage.py test

# 5. Launch Development Server
python manage.py runserver

```

Open **`http://127.0.0.1:8000/`** in your web browser.

---

## 4. Development Demo Credentials

| Role | Username | Institutional Email | Password |
| --- | --- | --- | --- |
| **Student** | `student` | `yassine.m@university.edu` | `Portal2026!` |
| **Instructor** | `instructor` | `v.sokolov@university.edu` | `Portal2026!` |
| **Administrator** | `admin` | `admin@university.edu` | `Portal2026!` |

```

4. Press **`Ctrl + S`** to save `README.md`.

---

### PROJECT PROGRESS (COMPLETE VERIFICATION REPORT)

* **Current phase:** Phase 13–15 — Automated Testing, Final Documentation & Academic Delivery
* **Completed steps:**
  * Phases 1–4: Windows 11 + PyCharm setup, `.venv`, Django 5.2 LTS, and custom dark-navy glassmorphic design system (`portal.css`, `base.html`, `landing.html`)[cite: 1]
  * Phase 5: Built and migrated all 14 OOP relational models in `apps/accounts/models.py` and `apps/academics/models.py`
  * Phase 6: Built `seed_portal` command and custom RBAC login/logout system
  * Phases 7–12: Implemented interactive Student, Instructor, and Admin dashboards with 1-Click Course Enrollment/Withdrawal, Prerequisite Locking, Assignment File Uploads, Instructor Weighted Grading, Chart.js GPA Analytics, and Official Transcript Exporting
  * Phase 13–15: Created 6 automated unit/integration tests (`apps/academics/tests.py`), `requirements.txt`, and `README.md`
* **Files created in this lesson:**
  * `apps/academics/tests.py`
  * `requirements.txt`
  * `README.md`
* **Known errors:** None (All previous migration and template syntax issues resolved)[cite: 2, 3, 4, 5]
* **Next step:** Run `python manage.py test` to verify `Ran 6 tests ... OK`!

**Run `python manage.py test` in your PyCharm Terminal now and tell me if you see `Ran 6 tests ... OK`!**

<FollowUp label="Ran 6 tests ... OK! How do I upload this project to GitHub?" query="I ran python manage.py test and got Ran 6 tests ... OK! Now teach me step-by-step how to create a .gitignore file and push my completed Student Portal project to my GitHub account."/>

```