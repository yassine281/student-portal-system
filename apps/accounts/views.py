import json
from datetime import date
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from .models import User, Student, Instructor, Notification
from apps.academics.models import (
    Department,
    AcademicSemester,
    Course,
    Enrollment,
    Assignment,
    Submission,
    Examination,
)


def portal_login_view(request):
    """
    Handles Student, Instructor, and Administrator authentication.
    Supports logging in with either username OR institutional email.
    """
    if request.user.is_authenticated:
        return redirect(request.user.get_dashboard_url())

    if request.method == 'POST':
        identifier = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')

        if '@' in identifier:
            matched_user = User.objects.filter(email__iexact=identifier).first()
            if matched_user:
                identifier = matched_user.username

        user = authenticate(request, username=identifier, password=password)
        if user is not None:
            login(request, user)
            messages.success(
                request,
                f"Welcome back, {user.get_full_display_name()}! Logged in as {user.get_role_display()}.",
            )
            return redirect(user.get_dashboard_url())
        else:
            messages.error(
                request,
                'Invalid username/email or password. Please check your credentials and try again.',
            )

    return render(request, 'accounts/login.html')


def portal_logout_view(request):
    """Logs the current user out and redirects to the login screen."""
    logout(request)
    messages.info(request, 'You have been securely logged out of the Student Portal.')
    return redirect('login')


@login_required(login_url='login')
def student_dashboard_view(request):
    """
    STUDENT WORKSPACE:
    Displays real-time GPA, attendance percentage, interactive enrollment/withdrawal,
    assignment file uploads, notifications, and Chart.js performance analytics.
    """
    student = Student.objects.select_related('user', 'department').filter(user=request.user).first()
    if not student:
        messages.warning(request, 'Redirected to your authorized role workspace.')
        return redirect(request.user.get_dashboard_url())

    current_semester = AcademicSemester.objects.filter(is_current=True).first()
    enrollments = (
        student.enrollments.select_related('course', 'course__instructor__user', 'semester', 'grade')
        .order_by('-semester__start_date', 'course__code')
    )
    active_enrollments = enrollments.filter(status=Enrollment.Status.ENROLLED)
    enrolled_course_ids = list(active_enrollments.values_list('course_id', flat=True))

    # Prepare Course Catalog with OOP Eligibility Check
    catalog_courses = []
    if current_semester:
        raw_catalog = (
            Course.objects.filter(semester=current_semester)
            .exclude(id__in=enrolled_course_ids)
            .select_related('instructor__user', 'prerequisite', 'department')
        )
        for course in raw_catalog:
            allowed, reason = course.can_student_enroll(student)
            catalog_courses.append({
                'course': course,
                'allowed': allowed,
                'reason': reason,
            })

    # Attach student's submission status to each assignment
    raw_assignments = Assignment.objects.filter(
        course_id__in=enrolled_course_ids
    ).select_related('course').order_by('due_date')

    submissions_map = {
        sub.assignment_id: sub
        for sub in Submission.objects.filter(student=student, assignment__in=raw_assignments)
    }
    assignments_with_status = [
        {
            'assignment': a,
            'submission': submissions_map.get(a.id),
        }
        for a in raw_assignments
    ]

    upcoming_exams = Examination.objects.filter(
        course_id__in=enrolled_course_ids
    ).select_related('course').order_by('exam_date')[:5]

    notifications = Notification.objects.filter(recipient=request.user, is_read=False)[:6]

    # Build Chart.js Datasets from real database records
    chart_labels = []
    chart_scores = []
    chart_attendance = []
    for e in enrollments.exclude(status=Enrollment.Status.WITHDRAWN):
        chart_labels.append(e.course.code)
        chart_scores.append(e.grade.total_percentage if hasattr(e, 'grade') and e.grade else 0)
        chart_attendance.append(e.course_attendance_percentage())

    context = {
        'student': student,
        'current_semester': current_semester,
        'gpa': student.calculate_gpa(),
        'attendance_pct': student.calculate_attendance_percentage(),
        'active_enrollments': active_enrollments,
        'all_enrollments': enrollments,
        'catalog_courses': catalog_courses,
        'assignments_with_status': assignments_with_status,
        'upcoming_exams': upcoming_exams,
        'notifications': notifications,
        'total_credits': sum(e.course.credits for e in active_enrollments),
        'chart_labels_json': json.dumps(chart_labels),
        'chart_scores_json': json.dumps(chart_scores),
        'chart_attendance_json': json.dumps(chart_attendance),
    }
    return render(request, 'students/dashboard.html', context)


@login_required(login_url='login')
def instructor_dashboard_view(request):
    """
    INSTRUCTOR WORKSPACE:
    Displays assigned courses, enrolled student rosters, interactive attendance logger,
    weighted grade calculator forms, and assignment publisher.
    """
    instructor = Instructor.objects.select_related('user', 'department').filter(user=request.user).first()
    if not instructor and not request.user.is_administrator:
        messages.warning(request, 'Access restricted to faculty members.')
        return redirect(request.user.get_dashboard_url())

    assigned_courses = (
        Course.objects.filter(instructor=instructor)
        .select_related('semester', 'department')
    ) if instructor else Course.objects.all()

    enrollments = Enrollment.objects.filter(
        course__in=assigned_courses,
        status=Enrollment.Status.ENROLLED,
    ).select_related('student__user', 'course', 'grade').order_by('course__code', 'student__student_id')

    recent_submissions = Submission.objects.filter(
        assignment__course__in=assigned_courses
    ).select_related('student__user', 'assignment__course').order_by('-created_at')[:8]

    context = {
        'instructor': instructor,
        'assigned_courses': assigned_courses,
        'enrollments': enrollments,
        'recent_submissions': recent_submissions,
        'total_students_taught': enrollments.count(),
        'total_courses': assigned_courses.count(),
        'today_iso': date.today().isoformat(),
    }
    return render(request, 'instructors/dashboard.html', context)


@login_required(login_url='login')
def admin_dashboard_view(request):
    """
    ADMINISTRATOR WORKSPACE:
    Displays institutional analytics, departments, courses, user records, and course creation form.
    """
    if not request.user.is_administrator:
        messages.error(request, 'Access denied: Administrator privileges required.')
        return redirect(request.user.get_dashboard_url())

    context = {
        'total_students': Student.objects.count(),
        'total_instructors': Instructor.objects.count(),
        'total_courses': Course.objects.count(),
        'total_departments': Department.objects.count(),
        'total_enrollments': Enrollment.objects.filter(status=Enrollment.Status.ENROLLED).count(),
        'students_list': Student.objects.select_related('user', 'department').all()[:10],
        'courses_list': Course.objects.select_related('department', 'instructor__user', 'semester').all(),
        'departments': Department.objects.all(),
        'instructors': Instructor.objects.select_related('user').all(),
        'semesters': AcademicSemester.objects.all(),
    }
    return render(request, 'admin_dashboard/dashboard.html', context)