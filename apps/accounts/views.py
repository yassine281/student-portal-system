from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from .models import User, Student, Instructor, Notification
from apps.academics.models import (
    Department,
    AcademicSemester,
    Course,
    Enrollment,
    Assignment,
    Examination,
)


def portal_login_view(request):
    """Handles Student, Instructor, and Administrator authentication."""
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
    """STUDENT WORKSPACE DASHBOARD."""
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
    enrolled_course_ids = active_enrollments.values_list('course_id', flat=True)

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

    upcoming_assignments = Assignment.objects.filter(
        course_id__in=enrolled_course_ids
    ).select_related('course').order_by('due_date')[:5]

    upcoming_exams = Examination.objects.filter(
        course_id__in=enrolled_course_ids
    ).select_related('course').order_by('exam_date')[:5]

    notifications = Notification.objects.filter(recipient=request.user)[:5]

    context = {
        'student': student,
        'current_semester': current_semester,
        'gpa': student.calculate_gpa(),
        'attendance_pct': student.calculate_attendance_percentage(),
        'active_enrollments': active_enrollments,
        'all_enrollments': enrollments,
        'catalog_courses': catalog_courses,
        'upcoming_assignments': upcoming_assignments,
        'upcoming_exams': upcoming_exams,
        'notifications': notifications,
        'total_credits': sum(e.course.credits for e in active_enrollments),
    }
    return render(request, 'students/dashboard.html', context)


@login_required(login_url='login')
def student_profile_view(request):
    """Allows students to update their personal profile, upload an avatar photo, and change password."""
    student = get_object_or_404(Student, user=request.user)
    user = request.user

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'update_profile':
            user.first_name = request.POST.get('first_name', user.first_name).strip()
            user.last_name = request.POST.get('last_name', user.last_name).strip()
            user.email = request.POST.get('email', user.email).strip()
            user.phone_number = request.POST.get('phone_number', user.phone_number).strip()
            if 'avatar' in request.FILES:
                user.avatar = request.FILES['avatar']
            user.save()
            messages.success(request, 'Your profile information and photo have been updated!')
            return redirect('student_profile')

        elif action == 'change_password':
            current_pw = request.POST.get('current_password', '')
            new_pw = request.POST.get('new_password', '')
            confirm_pw = request.POST.get('confirm_password', '')

            if not user.check_password(current_pw):
                messages.error(request, 'Your current password was entered incorrectly.')
            elif len(new_pw) < 6:
                messages.error(request, 'New password must be at least 6 characters long.')
            elif new_pw != confirm_pw:
                messages.error(request, 'New password and confirmation do not match.')
            else:
                user.set_password(new_pw)
                user.save()
                update_session_auth_hash(request, user)
                messages.success(request, 'Your password has been changed securely!')
                return redirect('student_profile')

    return render(request, 'students/profile.html', {'student': student})


@login_required(login_url='login')
def instructor_dashboard_view(request):
    """INSTRUCTOR WORKSPACE DASHBOARD."""
    instructor = Instructor.objects.select_related('user', 'department').filter(user=request.user).first()
    if not instructor and not request.user.is_administrator:
        messages.warning(request, 'Access restricted to faculty members.')
        return redirect(request.user.get_dashboard_url())

    assigned_courses = (
        Course.objects.filter(instructor=instructor)
        .select_related('semester', 'department')
        .prefetch_related('enrollments__student__user', 'enrollments__grade')
    ) if instructor else Course.objects.all()

    enrollments = Enrollment.objects.filter(
        course__in=assigned_courses,
        status=Enrollment.Status.ENROLLED,
    ).select_related('student__user', 'course', 'grade')

    context = {
        'instructor': instructor,
        'assigned_courses': assigned_courses,
        'enrollments': enrollments,
        'total_students_taught': enrollments.count(),
        'total_courses': assigned_courses.count(),
    }
    return render(request, 'instructors/dashboard.html', context)


@login_required(login_url='login')
def admin_dashboard_view(request):
    """ADMINISTRATOR COMMAND CENTER."""
    if not request.user.is_administrator:
        messages.error(request, 'Access denied: Administrator privileges required.')
        return redirect(request.user.get_dashboard_url())

    context = {
        'total_students': Student.objects.count(),
        'total_instructors': Instructor.objects.count(),
        'total_courses': Course.objects.count(),
        'total_departments': Department.objects.count(),
        'total_enrollments': Enrollment.objects.count(),
        'students_list': Student.objects.select_related('user', 'department').all()[:10],
        'courses_list': Course.objects.select_related('department', 'instructor__user', 'semester').all()[:10],
        'semesters': AcademicSemester.objects.all(),
    }
    return render(request, 'admin_dashboard/dashboard.html', context)