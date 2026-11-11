from datetime import date, timedelta
from django.db import connection, transaction
from django.utils import timezone


class RawSQLPortalRepository:
    """
    PURE RAW SQL DATA ACCESS LAYER (NO ORM):
    Executes all CRUD operations (SELECT ... JOIN, INSERT, UPDATE, DELETE)
    and analytical queries (GROUP BY, AVG, COUNT, SUM) via connection.cursor().
    """

    @staticmethod
    def _dictfetchall(cursor) -> list[dict]:
        columns = [col[0] for col in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    @staticmethod
    def _dictfetchone(cursor) -> dict | None:
        row = cursor.fetchone()
        if row is None:
            return None
        columns = [col[0] for col in cursor.description]
        return dict(zip(columns, row))

    # =========================================================================
    # 1. USER, STUDENT & INSTRUCTOR LOOKUPS (WITH SQL INNER JOIN)
    # =========================================================================
    @classmethod
    def find_username_by_email(cls, email: str) -> str | None:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT username FROM accounts_user WHERE LOWER(email) = LOWER(%s) LIMIT 1",
                [email],
            )
            row = cursor.fetchone()
            return row[0] if row else None

    @classmethod
    def get_student_by_user_id(cls, user_id: int) -> dict | None:
        sql = """
            SELECT
                s.id AS id,
                s.id AS student_pk,
                s.student_id AS student_id,
                s.student_id AS student_number,
                s.current_semester_number,
                s.admission_year,
                s.academic_status,
                s.department_id,
                u.id AS user_id,
                u.username,
                u.first_name,
                u.last_name,
                u.email,
                u.phone_number,
                u.avatar,
                (u.first_name || ' ' || u.last_name) AS full_name,
                d.code AS department_code,
                d.name AS department_name,
                d.faculty_name
            FROM accounts_student s
            INNER JOIN accounts_user u ON s.user_id = u.id
            INNER JOIN academics_department d ON s.department_id = d.id
            WHERE s.user_id = %s
            LIMIT 1
        """
        with connection.cursor() as cursor:
            cursor.execute(sql, [user_id])
            data = cls._dictfetchone(cursor)

        if data:
            # Maintain compatibility with both dictionary keys and nested template attributes
            status_labels = {
                'GOOD_STANDING': 'Good Standing',
                'HONORS': 'Dean’s Honors List',
                'PROBATION': 'Academic Probation',
            }
            data['get_academic_status_display'] = status_labels.get(
                data['academic_status'], data['academic_status']
            )
            data['department'] = {
                'id': data['department_id'],
                'code': data['department_code'],
                'name': data['department_name'],
            }
        return data

    @classmethod
    def update_student_user_profile(
        cls,
        user_id: int,
        first_name: str,
        last_name: str,
        email: str,
        phone: str,
        avatar_path: str | None = None,
    ) -> None:
        with connection.cursor() as cursor:
            if avatar_path:
                cursor.execute(
                    """
                    UPDATE accounts_user
                    SET first_name = %s, last_name = %s, email = %s, phone_number = %s, avatar = %s
                    WHERE id = %s
                    """,
                    [first_name, last_name, email, phone, avatar_path, user_id],
                )
            else:
                cursor.execute(
                    """
                    UPDATE accounts_user
                    SET first_name = %s, last_name = %s, email = %s, phone_number = %s
                    WHERE id = %s
                    """,
                    [first_name, last_name, email, phone, user_id],
                )

    @classmethod
    def get_instructor_by_user_id(cls, user_id: int) -> dict | None:
        sql = """
            SELECT
                i.id AS id,
                i.id AS instructor_pk,
                i.employee_id,
                i.academic_title,
                i.office_location,
                i.department_id,
                (u.first_name || ' ' || u.last_name) AS full_name,
                u.email,
                d.code AS department_code,
                d.name AS department_name
            FROM accounts_instructor i
            INNER JOIN accounts_user u ON i.user_id = u.id
            INNER JOIN academics_department d ON i.department_id = d.id
            WHERE i.user_id = %s
            LIMIT 1
        """
        with connection.cursor() as cursor:
            cursor.execute(sql, [user_id])
            data = cls._dictfetchone(cursor)

        if data:
            data['department'] = {
                'id': data['department_id'],
                'code': data['department_code'],
                'name': data['department_name'],
            }
        return data

    @classmethod
    def get_current_semester(cls) -> dict | None:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, code, name, start_date, end_date, is_current, enrollment_open
                FROM academics_academicsemester
                WHERE is_current = 1
                LIMIT 1
                """
            )
            return cls._dictfetchone(cursor)

    # =========================================================================
    # 2. STUDENT ENROLLMENTS & CATALOG CRUD (RAW SQL JOINS)
    # =========================================================================
    @classmethod
    def get_student_enrollments(cls, student_pk: int, only_active: bool = False) -> list[dict]:
        status_clause = "AND e.status = 'ENROLLED'" if only_active else ""
        sql = f"""
            SELECT
                e.id AS id,
                e.id AS enrollment_id,
                e.status,
                e.course_id,
                c.code AS course_code,
                c.title AS course_title,
                c.credits,
                c.schedule_days,
                c.schedule_time,
                c.room_number,
                sem.code AS semester_code,
                sem.name AS semester_name,
                COALESCE(inst.academic_title || ' ' || u_inst.first_name || ' ' || u_inst.last_name, 'TBA') AS instructor_name,
                g.assignment_score,
                g.midterm_score,
                g.final_exam_score,
                g.total_percentage,
                g.letter_grade,
                g.grade_points,
                COALESCE(
                    ROUND(
                        100.0 * SUM(CASE WHEN a.status IN ('PRESENT', 'LATE', 'EXCUSED') THEN 1 ELSE 0 END)
                        / NULLIF(COUNT(a.id), 0),
                        1
                    ),
                    100.0
                ) AS attendance_pct
            FROM academics_enrollment e
            INNER JOIN academics_course c ON e.course_id = c.id
            INNER JOIN academics_academicsemester sem ON e.semester_id = sem.id
            LEFT JOIN accounts_instructor inst ON c.instructor_id = inst.id
            LEFT JOIN accounts_user u_inst ON inst.user_id = u_inst.id
            LEFT JOIN academics_grade g ON g.enrollment_id = e.id
            LEFT JOIN academics_attendance a ON a.enrollment_id = e.id
            WHERE e.student_id = %s {status_clause}
            GROUP BY
                e.id, e.status, e.course_id, c.code, c.title, c.credits,
                c.schedule_days, c.schedule_time, c.room_number,
                sem.code, sem.name, instructor_name,
                g.assignment_score, g.midterm_score, g.final_exam_score,
                g.total_percentage, g.letter_grade, g.grade_points
            ORDER BY sem.start_date DESC, c.code ASC
        """
        with connection.cursor() as cursor:
            cursor.execute(sql, [student_pk])
            rows = cls._dictfetchall(cursor)

        for r in rows:
            r['course_attendance_percentage'] = r['attendance_pct']
            r['course'] = {
                'id': r['course_id'],
                'code': r['course_code'],
                'title': r['course_title'],
                'credits': r['credits'],
                'schedule_days': r['schedule_days'],
                'schedule_time': r['schedule_time'],
                'room_number': r['room_number'],
                'instructor': r['instructor_name'],
            }
            r['grade'] = (
                {
                    'letter_grade': r['letter_grade'],
                    'total_percentage': r['total_percentage'],
                    'grade_points': r['grade_points'],
                }
                if r['letter_grade']
                else None
            )
        return rows

    @classmethod
    def check_enrollment_eligibility_sql(cls, student_pk: int, course_id: int) -> tuple[bool, str]:
        sql = """
            SELECT
                c.code,
                c.max_capacity,
                c.prerequisite_id,
                prereq.code AS prereq_code,
                sem.enrollment_open,
                sem.name AS semester_name,
                (
                    SELECT COUNT(*)
                    FROM academics_enrollment e
                    WHERE e.course_id = c.id AND e.status = 'ENROLLED'
                ) AS enrolled_count,
                (
                    SELECT COUNT(*)
                    FROM academics_enrollment e_dup
                    WHERE e_dup.course_id = c.id AND e_dup.student_id = %s AND e_dup.status = 'ENROLLED'
                ) AS already_enrolled
            FROM academics_course c
            INNER JOIN academics_academicsemester sem ON c.semester_id = sem.id
            LEFT JOIN academics_course prereq ON c.prerequisite_id = prereq.id
            WHERE c.id = %s
        """
        with connection.cursor() as cursor:
            cursor.execute(sql, [student_pk, course_id])
            course = cls._dictfetchone(cursor)

        if not course:
            return False, "Course does not exist."
        if not course['enrollment_open']:
            return False, f"Enrollment for {course['semester_name']} is currently closed."
        if course['already_enrolled'] > 0:
            return False, f"You are already enrolled in {course['code']}."
        if course['enrolled_count'] >= course['max_capacity']:
            return False, f"Course {course['code']} has reached its full capacity of {course['max_capacity']} seats."

        if course['prerequisite_id']:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT COUNT(*)
                    FROM academics_enrollment e
                    INNER JOIN academics_grade g ON g.enrollment_id = e.id
                    WHERE e.student_id = %s
                      AND e.course_id = %s
                      AND g.grade_points >= 2.0
                    """,
                    [student_pk, course['prerequisite_id']],
                )
                passed_prereq = cursor.fetchone()[0] > 0
            if not passed_prereq:
                return (
                    False,
                    f"Prerequisite not met: You must pass {course['prereq_code']} (min 2.0 GPA) first.",
                )

        return True, "Eligible for enrollment."

    @classmethod
    def get_available_catalog_for_student(
        cls, student_pk: int, semester_id: int, department_filter_id: int | None = None
    ) -> list[dict]:
        dept_clause = "AND c.department_id = %s" if department_filter_id else ""
        ordered_params = [semester_id, student_pk] + (
            [department_filter_id] if department_filter_id else []
        )

        sql = f"""
            SELECT
                c.id AS id,
                c.id AS course_id,
                c.code,
                c.title,
                c.credits,
                c.max_capacity,
                c.schedule_days,
                c.schedule_time,
                c.room_number,
                c.prerequisite_id,
                prereq.code AS prerequisite_code,
                d.code AS department_code,
                d.name AS department_name,
                COALESCE(inst.academic_title || ' ' || u_inst.first_name || ' ' || u_inst.last_name, 'TBA') AS instructor_name,
                (
                    SELECT COUNT(*)
                    FROM academics_enrollment e_cnt
                    WHERE e_cnt.course_id = c.id AND e_cnt.status = 'ENROLLED'
                ) AS enrolled_count
            FROM academics_course c
            INNER JOIN academics_department d ON c.department_id = d.id
            LEFT JOIN accounts_instructor inst ON c.instructor_id = inst.id
            LEFT JOIN accounts_user u_inst ON inst.user_id = u_inst.id
            LEFT JOIN academics_course prereq ON c.prerequisite_id = prereq.id
            WHERE c.semester_id = %s
              AND c.id NOT IN (
                  SELECT e_sub.course_id
                  FROM academics_enrollment e_sub
                  WHERE e_sub.student_id = %s AND e_sub.status = 'ENROLLED'
              )
              {dept_clause}
            ORDER BY c.code ASC
        """
        with connection.cursor() as cursor:
            cursor.execute(sql, ordered_params)
            courses = cls._dictfetchall(cursor)

        for item in courses:
            item['remaining_seats'] = max(0, item['max_capacity'] - item['enrolled_count'])
            allowed, reason = cls.check_enrollment_eligibility_sql(student_pk, item['course_id'])
            item['allowed'] = allowed
            item['reason'] = reason
            item['course'] = item

        return courses

    @classmethod
    @transaction.atomic
    def enroll_student_sql(cls, student_pk: int, course_id: int) -> tuple[bool, str]:
        allowed, reason = cls.check_enrollment_eligibility_sql(student_pk, course_id)
        if not allowed:
            return False, reason

        now_ts = timezone.now()
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT semester_id, code, title FROM academics_course WHERE id = %s",
                [course_id],
            )
            course_row = cls._dictfetchone(cursor)

            cursor.execute(
                """
                SELECT id FROM academics_enrollment
                WHERE student_id = %s AND course_id = %s AND semester_id = %s
                """,
                [student_pk, course_id, course_row['semester_id']],
            )
            existing = cursor.fetchone()

            if existing:
                cursor.execute(
                    """
                    UPDATE academics_enrollment
                    SET status = 'ENROLLED', updated_at = %s
                    WHERE id = %s
                    """,
                    [now_ts, existing[0]],
                )
            else:
                cursor.execute(
                    """
                    INSERT INTO academics_enrollment
                        (student_id, course_id, semester_id, status, created_at, updated_at)
                    VALUES (%s, %s, %s, 'ENROLLED', %s, %s)
                    """,
                    [student_pk, course_id, course_row['semester_id'], now_ts, now_ts],
                )

        return True, f"Successfully enrolled in {course_row['code']} — {course_row['title']}!"

    @classmethod
    def delete_or_withdraw_enrollment_sql(cls, enrollment_id: int, student_pk: int | None = None) -> str:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT c.code
                FROM academics_enrollment e
                INNER JOIN academics_course c ON e.course_id = c.id
                WHERE e.id = %s
                """,
                [enrollment_id],
            )
            row = cursor.fetchone()
            course_code = row[0] if row else "Course"

            if student_pk is not None:
                cursor.execute(
                    "DELETE FROM academics_enrollment WHERE id = %s AND student_id = %s",
                    [enrollment_id, student_pk],
                )
            else:
                cursor.execute("DELETE FROM academics_enrollment WHERE id = %s", [enrollment_id])

        return course_code

    # =========================================================================
    # 3. ANALYTICAL QUERIES (АНАЛИТИЧЕСКИЕ ЗАПРОСЫ — LAB 6 & 7)
    # =========================================================================
    @classmethod
    def get_student_analytical_summary_sql(cls, student_pk: int) -> dict:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    COALESCE(
                        ROUND(
                            SUM(CASE WHEN g.id IS NOT NULL THEN g.grade_points * c.credits ELSE 0 END)
                            / NULLIF(SUM(CASE WHEN g.id IS NOT NULL THEN c.credits ELSE 0 END), 0),
                            2
                        ),
                        0.00
                    ) AS weighted_gpa,
                    COALESCE(SUM(CASE WHEN e.status = 'ENROLLED' THEN c.credits ELSE 0 END), 0) AS active_credits
                FROM academics_enrollment e
                INNER JOIN academics_course c ON e.course_id = c.id
                LEFT JOIN academics_grade g ON g.enrollment_id = e.id
                WHERE e.student_id = %s
                """,
                [student_pk],
            )
            gpa_row = cls._dictfetchone(cursor)

            cursor.execute(
                """
                SELECT
                    COALESCE(
                        ROUND(
                            100.0 * SUM(CASE WHEN a.status IN ('PRESENT', 'LATE', 'EXCUSED') THEN 1 ELSE 0 END)
                            / NULLIF(COUNT(a.id), 0),
                            1
                        ),
                        100.0
                    ) AS overall_attendance_pct
                FROM academics_attendance a
                INNER JOIN academics_enrollment e ON a.enrollment_id = e.id
                WHERE e.student_id = %s
                """,
                [student_pk],
            )
            att_row = cls._dictfetchone(cursor)

        return {
            'gpa': float(gpa_row['weighted_gpa']) if gpa_row else 0.0,
            'active_credits': int(gpa_row['active_credits']) if gpa_row else 0,
            'attendance_pct': float(att_row['overall_attendance_pct']) if att_row else 100.0,
        }

    @classmethod
    def get_department_performance_analytics_sql(cls, department_id: int | None = None) -> list[dict]:
        params = [department_id] if department_id else []
        where_clause = "WHERE d.id = %s" if department_id else ""

        sql = f"""
            SELECT
                d.id AS department_id,
                d.code AS department_code,
                d.name AS department_name,
                d.faculty_name,
                COUNT(DISTINCT s.id) AS student_count,
                COUNT(DISTINCT c.id) AS course_count,
                COUNT(DISTINCT e.id) AS enrollment_count,
                COALESCE(ROUND(AVG(g.total_percentage), 1), 0.0) AS avg_score_pct,
                COALESCE(ROUND(AVG(g.grade_points), 2), 0.00) AS avg_gpa
            FROM academics_department d
            LEFT JOIN accounts_student s ON s.department_id = d.id
            LEFT JOIN academics_course c ON c.department_id = d.id
            LEFT JOIN academics_enrollment e ON e.course_id = c.id
            LEFT JOIN academics_grade g ON g.enrollment_id = e.id
            {where_clause}
            GROUP BY d.id, d.code, d.name, d.faculty_name
            ORDER BY avg_gpa DESC, d.code ASC
        """
        with connection.cursor() as cursor:
            cursor.execute(sql, params)
            return cls._dictfetchall(cursor)

    @classmethod
    def get_course_analytics_report_sql(cls, department_id: int | None = None) -> list[dict]:
        params = [department_id] if department_id else []
        where_clause = "WHERE c.department_id = %s" if department_id else ""

        sql = f"""
            SELECT
                c.id AS course_id,
                c.code AS course_code,
                c.title AS course_title,
                c.credits,
                c.max_capacity,
                d.code AS department_code,
                d.name AS department_name,
                sem.code AS semester_code,
                COALESCE(inst.academic_title || ' ' || u.first_name || ' ' || u.last_name, 'Unassigned') AS instructor_name,
                COUNT(DISTINCT CASE WHEN e.status = 'ENROLLED' THEN e.id END) AS enrolled_students,
                ROUND(
                    100.0 * COUNT(DISTINCT CASE WHEN e.status = 'ENROLLED' THEN e.id END) / NULLIF(c.max_capacity, 0),
                    1
                ) AS occupancy_pct,
                COALESCE(ROUND(AVG(g.total_percentage), 1), 0.0) AS avg_course_score,
                COALESCE(ROUND(AVG(g.grade_points), 2), 0.00) AS avg_course_gpa
            FROM academics_course c
            INNER JOIN academics_department d ON c.department_id = d.id
            INNER JOIN academics_academicsemester sem ON c.semester_id = sem.id
            LEFT JOIN accounts_instructor inst ON c.instructor_id = inst.id
            LEFT JOIN accounts_user u ON inst.user_id = u.id
            LEFT JOIN academics_enrollment e ON e.course_id = c.id
            LEFT JOIN academics_grade g ON g.enrollment_id = e.id
            {where_clause}
            GROUP BY
                c.id, c.code, c.title, c.credits, c.max_capacity,
                d.code, d.name, sem.code, instructor_name
            ORDER BY c.code ASC
        """
        with connection.cursor() as cursor:
            cursor.execute(sql, params)
            return cls._dictfetchall(cursor)

    # =========================================================================
    # 4. INSTRUCTOR ROSTER, GRADING & ATTENDANCE CRUD (RAW SQL)
    # =========================================================================
    @classmethod
    def get_instructor_roster_sql(
        cls, instructor_pk: int | None = None, course_filter_id: int | None = None
    ) -> list[dict]:
        clauses = ["e.status = 'ENROLLED'"]
        params: list = []
        if instructor_pk:
            clauses.append("c.instructor_id = %s")
            params.append(instructor_pk)
        if course_filter_id:
            clauses.append("c.id = %s")
            params.append(course_filter_id)

        where_sql = " AND ".join(clauses)
        sql = f"""
            SELECT
                e.id AS id,
                e.id AS enrollment_id,
                s.student_id AS student_number,
                (u.first_name || ' ' || u.last_name) AS student_name,
                d.name AS student_department,
                c.id AS course_id,
                c.code AS course_code,
                c.title AS course_title,
                g.assignment_score,
                g.midterm_score,
                g.final_exam_score,
                g.total_percentage,
                g.letter_grade,
                g.grade_points,
                COALESCE(
                    ROUND(
                        100.0 * SUM(CASE WHEN a.status IN ('PRESENT', 'LATE', 'EXCUSED') THEN 1 ELSE 0 END)
                        / NULLIF(COUNT(a.id), 0),
                        1
                    ),
                    100.0
                ) AS attendance_pct
            FROM academics_enrollment e
            INNER JOIN accounts_student s ON e.student_id = s.id
            INNER JOIN accounts_user u ON s.user_id = u.id
            INNER JOIN academics_department d ON s.department_id = d.id
            INNER JOIN academics_course c ON e.course_id = c.id
            LEFT JOIN academics_grade g ON g.enrollment_id = e.id
            LEFT JOIN academics_attendance a ON a.enrollment_id = e.id
            WHERE {where_sql}
            GROUP BY
                e.id, s.student_id, student_name, d.name,
                c.id, c.code, c.title,
                g.assignment_score, g.midterm_score, g.final_exam_score,
                g.total_percentage, g.letter_grade, g.grade_points
            ORDER BY c.code ASC, s.student_id ASC
        """
        with connection.cursor() as cursor:
            cursor.execute(sql, params)
            return cls._dictfetchall(cursor)

    @classmethod
    def get_enrollment_detail_sql(cls, enrollment_id: int) -> dict | None:
        sql = """
            SELECT
                e.id AS id,
                e.id AS enrollment_id,
                e.status,
                s.id AS student_pk,
                s.user_id AS student_user_id,
                s.student_id AS student_number,
                (u.first_name || ' ' || u.last_name) AS student_name,
                c.id AS course_id,
                c.code AS course_code,
                c.title AS course_title,
                COALESCE(g.assignment_score, 0.0) AS assignment_score,
                COALESCE(g.midterm_score, 0.0) AS midterm_score,
                COALESCE(g.final_exam_score, 0.0) AS final_exam_score,
                g.total_percentage,
                g.letter_grade,
                g.grade_points
            FROM academics_enrollment e
            INNER JOIN accounts_student s ON e.student_id = s.id
            INNER JOIN accounts_user u ON s.user_id = u.id
            INNER JOIN academics_course c ON e.course_id = c.id
            LEFT JOIN academics_grade g ON g.enrollment_id = e.id
            WHERE e.id = %s
            LIMIT 1
        """
        with connection.cursor() as cursor:
            cursor.execute(sql, [enrollment_id])
            return cls._dictfetchone(cursor)

    @classmethod
    @transaction.atomic
    def upsert_grade_sql(
        cls, enrollment_id: int, assignment_score: float, midterm_score: float, final_exam_score: float
    ) -> dict:
        total_pct = round(
            (assignment_score * 0.30) + (midterm_score * 0.30) + (final_exam_score * 0.40), 2
        )
        if total_pct >= 93:
            letter, pts = 'A', 4.0
        elif total_pct >= 90:
            letter, pts = 'A-', 3.7
        elif total_pct >= 87:
            letter, pts = 'B+', 3.3
        elif total_pct >= 83:
            letter, pts = 'B', 3.0
        elif total_pct >= 80:
            letter, pts = 'B-', 2.7
        elif total_pct >= 77:
            letter, pts = 'C+', 2.3
        elif total_pct >= 73:
            letter, pts = 'C', 2.0
        elif total_pct >= 70:
            letter, pts = 'C-', 1.7
        elif total_pct >= 60:
            letter, pts = 'D', 1.0
        else:
            letter, pts = 'F', 0.0

        now_ts = timezone.now()
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT id FROM academics_grade WHERE enrollment_id = %s", [enrollment_id]
            )
            existing = cursor.fetchone()
            if existing:
                cursor.execute(
                    """
                    UPDATE academics_grade
                    SET assignment_score = %s,
                        midterm_score = %s,
                        final_exam_score = %s,
                        total_percentage = %s,
                        letter_grade = %s,
                        grade_points = %s,
                        updated_at = %s
                    WHERE enrollment_id = %s
                    """,
                    [
                        assignment_score,
                        midterm_score,
                        final_exam_score,
                        total_pct,
                        letter,
                        pts,
                        now_ts,
                        enrollment_id,
                    ],
                )
            else:
                cursor.execute(
                    """
                    INSERT INTO academics_grade
                        (enrollment_id, assignment_score, midterm_score, final_exam_score,
                         total_percentage, letter_grade, grade_points, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    [
                        enrollment_id,
                        assignment_score,
                        midterm_score,
                        final_exam_score,
                        total_pct,
                        letter,
                        pts,
                        now_ts,
                        now_ts,
                    ],
                )

        return {'total_percentage': total_pct, 'letter_grade': letter, 'grade_points': pts}

    @classmethod
    @transaction.atomic
    def record_attendance_sql(
        cls, enrollment_id: int, session_date: str | date, status: str, remarks: str = ''
    ) -> float:
        now_ts = timezone.now()
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT id FROM academics_attendance WHERE enrollment_id = %s AND session_date = %s",
                [enrollment_id, str(session_date)],
            )
            existing = cursor.fetchone()
            if existing:
                cursor.execute(
                    """
                    UPDATE academics_attendance
                    SET status = %s, remarks = %s, updated_at = %s
                    WHERE id = %s
                    """,
                    [status, remarks, now_ts, existing[0]],
                )
            else:
                cursor.execute(
                    """
                    INSERT INTO academics_attendance
                        (enrollment_id, session_date, status, remarks, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    [enrollment_id, str(session_date), status, remarks, now_ts, now_ts],
                )

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
                [enrollment_id],
            )
            return float(cursor.fetchone()[0])

    @classmethod
    def get_attendance_history_sql(cls, enrollment_id: int) -> list[dict]:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, session_date, status, remarks
                FROM academics_attendance
                WHERE enrollment_id = %s
                ORDER BY session_date DESC
                LIMIT 12
                """,
                [enrollment_id],
            )
            return cls._dictfetchall(cursor)

    # =========================================================================
    # 5. COURSE CRUD & FOREIGN KEY DROPDOWN QUERIES
    # =========================================================================
    @classmethod
    def get_all_departments_sql(cls) -> list[dict]:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT id, code, name, faculty_name FROM academics_department ORDER BY code ASC"
            )
            return cls._dictfetchall(cursor)

    @classmethod
    def get_all_instructors_sql(cls) -> list[dict]:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    i.id,
                    i.employee_id,
                    (i.academic_title || ' ' || u.first_name || ' ' || u.last_name) AS display_name,
                    d.name AS department_name
                FROM accounts_instructor i
                INNER JOIN accounts_user u ON i.user_id = u.id
                INNER JOIN academics_department d ON i.department_id = d.id
                ORDER BY u.last_name ASC
                """
            )
            return cls._dictfetchall(cursor)

    @classmethod
    def get_all_semesters_sql(cls) -> list[dict]:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT id, code, name, start_date, end_date, is_current FROM academics_academicsemester ORDER BY start_date DESC"
            )
            return cls._dictfetchall(cursor)

    @classmethod
    def get_course_by_id_sql(cls, course_id: int) -> dict | None:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    id, code, title, description, credits, max_capacity,
                    department_id, instructor_id, semester_id, prerequisite_id,
                    schedule_days, schedule_time, room_number
                FROM academics_course
                WHERE id = %s
                """,
                [course_id],
            )
            return cls._dictfetchone(cursor)

    @classmethod
    def create_course_sql(cls, data: dict) -> None:
        now_ts = timezone.now()
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO academics_course
                    (code, title, description, credits, max_capacity,
                     department_id, instructor_id, semester_id, prerequisite_id,
                     schedule_days, schedule_time, room_number, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                [
                    data['code'].strip().upper(),
                    data['title'].strip(),
                    data.get('description', '').strip(),
                    int(data['credits']),
                    int(data['max_capacity']),
                    int(data['department_id']),
                    int(data['instructor_id']) if data.get('instructor_id') else None,
                    int(data['semester_id']),
                    int(data['prerequisite_id']) if data.get('prerequisite_id') else None,
                    data.get('schedule_days', 'Mon / Wed').strip(),
                    data.get('schedule_time', '09:00 - 10:30').strip(),
                    data.get('room_number', 'Lab A-304').strip(),
                    now_ts,
                    now_ts,
                ],
            )

    @classmethod
    def update_course_sql(cls, course_id: int, data: dict) -> None:
        now_ts = timezone.now()
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE academics_course
                SET code = %s,
                    title = %s,
                    description = %s,
                    credits = %s,
                    max_capacity = %s,
                    department_id = %s,
                    instructor_id = %s,
                    semester_id = %s,
                    schedule_days = %s,
                    schedule_time = %s,
                    room_number = %s,
                    updated_at = %s
                WHERE id = %s
                """,
                [
                    data['code'].strip().upper(),
                    data['title'].strip(),
                    data.get('description', '').strip(),
                    int(data['credits']),
                    int(data['max_capacity']),
                    int(data['department_id']),
                    int(data['instructor_id']) if data.get('instructor_id') else None,
                    int(data['semester_id']),
                    data.get('schedule_days', 'Mon / Wed').strip(),
                    data.get('schedule_time', '09:00 - 10:30').strip(),
                    data.get('room_number', 'Lab A-304').strip(),
                    now_ts,
                    course_id,
                ],
            )

    @classmethod
    def delete_course_sql(cls, course_id: int) -> str:
        with connection.cursor() as cursor:
            cursor.execute("SELECT code FROM academics_course WHERE id = %s", [course_id])
            row = cursor.fetchone()
            code = row[0] if row else "Course"
            cursor.execute("DELETE FROM academics_course WHERE id = %s", [course_id])
            return code

    # =========================================================================
    # 6. ASSIGNMENTS, SUBMISSIONS, EXAMS & NOTIFICATIONS (RAW SQL)
    # =========================================================================
    @classmethod
    def get_student_assignments_sql(cls, student_pk: int) -> list[dict]:
        sql = """
            SELECT
                a.id AS id,
                a.id AS assignment_id,
                a.title,
                a.description,
                a.due_date,
                a.max_score,
                c.code AS course_code,
                c.title AS course_title,
                sub.submitted_file,
                sub.notes AS submission_notes
            FROM academics_assignment a
            INNER JOIN academics_course c ON a.course_id = c.id
            INNER JOIN academics_enrollment e ON e.course_id = c.id
            LEFT JOIN academics_submission sub ON sub.assignment_id = a.id AND sub.student_id = %s
            WHERE e.student_id = %s AND e.status = 'ENROLLED'
            ORDER BY a.due_date ASC
        """
        with connection.cursor() as cursor:
            cursor.execute(sql, [student_pk, student_pk])
            return cls._dictfetchall(cursor)

    @classmethod
    def get_assignment_by_id_sql(cls, assignment_id: int) -> dict | None:
        sql = """
            SELECT
                a.id AS id,
                a.id AS assignment_id,
                a.title,
                a.description,
                a.due_date,
                a.max_score,
                c.code AS course_code,
                c.title AS course_title
            FROM academics_assignment a
            INNER JOIN academics_course c ON a.course_id = c.id
            WHERE a.id = %s
        """
        with connection.cursor() as cursor:
            cursor.execute(sql, [assignment_id])
            return cls._dictfetchone(cursor)

    @classmethod
    def upsert_submission_sql(
        cls, assignment_id: int, student_pk: int, file_path: str | None, notes: str
    ) -> None:
        now_ts = timezone.now()
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT id FROM academics_submission WHERE assignment_id = %s AND student_id = %s",
                [assignment_id, student_pk],
            )
            existing = cursor.fetchone()
            if existing:
                cursor.execute(
                    """
                    UPDATE academics_submission
                    SET submitted_file = COALESCE(%s, submitted_file),
                        notes = %s,
                        updated_at = %s
                    WHERE id = %s
                    """,
                    [file_path, notes, now_ts, existing[0]],
                )
            else:
                cursor.execute(
                    """
                    INSERT INTO academics_submission
                        (assignment_id, student_id, submitted_file, notes, score, feedback, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, NULL, '', %s, %s)
                    """,
                    [assignment_id, student_pk, file_path or '', notes, now_ts, now_ts],
                )

    @classmethod
    def get_student_examinations_sql(cls, student_pk: int) -> list[dict]:
        sql = """
            SELECT
                ex.title,
                ex.exam_date,
                ex.room_number,
                ex.duration_minutes,
                c.code AS course_code,
                c.title AS course_title
            FROM academics_examination ex
            INNER JOIN academics_course c ON ex.course_id = c.id
            INNER JOIN academics_enrollment e ON e.course_id = c.id
            WHERE e.student_id = %s AND e.status = 'ENROLLED'
            ORDER BY ex.exam_date ASC
        """
        with connection.cursor() as cursor:
            cursor.execute(sql, [student_pk])
            return cls._dictfetchall(cursor)

    @classmethod
    def get_user_notifications_sql(cls, user_id: int) -> list[dict]:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT title, message, category, created_at
                FROM accounts_notification
                WHERE recipient_id = %s
                ORDER BY created_at DESC
                LIMIT 6
                """,
                [user_id],
            )
            return cls._dictfetchall(cursor)

    @classmethod
    def create_notification_sql(
        cls, recipient_user_id: int, category: str, title: str, message: str
    ) -> None:
        now_ts = timezone.now()
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO accounts_notification
                    (recipient_id, category, title, message, is_read, created_at, updated_at)
                VALUES (%s, %s, %s, %s, 0, %s, %s)
                """,
                [recipient_user_id, category, title, message, now_ts, now_ts],
            )