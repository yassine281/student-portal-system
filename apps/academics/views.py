from datetime import date
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from apps.accounts.models import Student, Notification
from .models import Course, Enrollment, Assignment, Submission, Grade, Attendance
from .forms import SubmissionForm, GradeForm


@login_required(login_url='login')
def enroll_course_view(request, course_id):
    """Processes course registration using OOP prerequisite and capacity validation."""
    student = get_object_or_404(Student, user=request.user)
    course = get_object_or_404(Course, id=course_id)

    allowed, reason = course.can_student_enroll(student)
    if not allowed:
        messages.error(request, f"Enrollment blocked: {reason}")
    else:
        Enrollment.objects.update_or_create(
            student=student,
            course=course,
            semester=course.semester,
            defaults={'status': Enrollment.Status.ENROLLED},
        )
        messages.success(request, f"Successfully enrolled in {course.code} — {course.title}!")

    return redirect('student_dashboard')


@login_required(login_url='login')
def withdraw_course_view(request, enrollment_id):
    """Allows a student to withdraw from an active course enrollment."""
    student = get_object_or_404(Student, user=request.user)
    enrollment = get_object_or_404(Enrollment, id=enrollment_id, student=student)
    enrollment.status = Enrollment.Status.WITHDRAWN
    enrollment.save()
    messages.info(request, f"Successfully withdrew from {enrollment.course.code}.")
    return redirect('student_dashboard')


@login_required(login_url='login')
def submit_assignment_view(request, assignment_id):
    """Handles secure file uploads for assignment submissions."""
    student = get_object_or_404(Student, user=request.user)
    assignment = get_object_or_404(Assignment, id=assignment_id)

    submission, _ = Submission.objects.get_or_create(assignment=assignment, student=student)

    if request.method == 'POST':
        form = SubmissionForm(request.POST, request.FILES, instance=submission)
        if form.is_valid():
            form.save()
            messages.success(request, f"Assignment '{assignment.title}' uploaded and submitted successfully!")
            return redirect('student_dashboard')
    else:
        form = SubmissionForm(instance=submission)

    context = {
        'form': form,
        'assignment': assignment,
    }
    return render(request, 'students/submit_assignment.html', context)


@login_required(login_url='login')
def instructor_grade_view(request, enrollment_id):
    """Allows instructors to record or update component scores for a student enrollment."""
    enrollment = get_object_or_404(Enrollment, id=enrollment_id)
    grade, _ = Grade.objects.get_or_create(enrollment=enrollment)

    if request.method == 'POST':
        form = GradeForm(request.POST, instance=grade)
        if form.is_valid():
            form.save()
            Notification.objects.create(
                recipient=enrollment.student.user,
                category=Notification.Category.GRADE,
                title=f"Updated Grade: {enrollment.course.code}",
                message=f"Your grade in {enrollment.course.title} is now {grade.letter_grade} ({grade.total_percentage}%).",
            )
            messages.success(
                request,
                f"Grades updated for {enrollment.student.user.get_full_display_name()} ({enrollment.course.code}).",
            )
            return redirect('instructor_dashboard')
    else:
        form = GradeForm(instance=grade)

    context = {
        'form': form,
        'enrollment': enrollment,
    }
    return render(request, 'instructors/grade_form.html', context)


@login_required(login_url='login')
def quick_attendance_view(request, enrollment_id, status_code):
    """
    1-Click Present / Absent handler on the Instructor Dashboard.
    Automatically triggers a student warning notification if course attendance falls below 75%.
    """
    enrollment = get_object_or_404(Enrollment, id=enrollment_id)
    valid_statuses = {
        'PRESENT': Attendance.Status.PRESENT,
        'ABSENT': Attendance.Status.ABSENT,
    }
    chosen_status = valid_statuses.get(status_code.upper(), Attendance.Status.PRESENT)

    # Create a new session entry (using latest date + 1 day if today already has an entry so every click is visible)
    latest_record = enrollment.attendance_records.order_by('-session_date').first()
    target_date = date.today()
    if latest_record and latest_record.session_date >= target_date:
        from datetime import timedelta
        target_date = latest_record.session_date + timedelta(days=1)

    Attendance.objects.create(
        enrollment=enrollment,
        session_date=target_date,
        status=chosen_status,
        remarks=f"Recorded via 1-Click Instructor Console ({target_date})",
    )

    updated_pct = enrollment.course_attendance_percentage()
    if updated_pct < 75.0:
        Notification.objects.create(
            recipient=enrollment.student.user,
            category=Notification.Category.ATTENDANCE,
            title=f"⚠️ Attendance Warning: {enrollment.course.code}",
            message=f"Your attendance in {enrollment.course.title} dropped to {updated_pct}% (below the 75% minimum threshold).",
        )
        messages.warning(
            request,
            f"Marked {enrollment.student.user.get_full_display_name()} as {chosen_status}. Alert sent: Attendance is now {updated_pct}% (<75%)!",
        )
    else:
        messages.success(
            request,
            f"Marked {enrollment.student.user.get_full_display_name()} as {chosen_status} for {enrollment.course.code} (Attendance: {updated_pct}%).",
        )

    return redirect('instructor_dashboard')


@login_required(login_url='login')
def instructor_attendance_view(request, enrollment_id):
    """Allows instructors to record attendance for a specific custom date and view history."""
    enrollment = get_object_or_404(Enrollment, id=enrollment_id)

    if request.method == 'POST':
        status_val = request.POST.get('status', Attendance.Status.PRESENT)
        session_date = request.POST.get('session_date', str(date.today()))
        remarks = request.POST.get('remarks', '').strip()

        Attendance.objects.update_or_create(
            enrollment=enrollment,
            session_date=session_date,
            defaults={'status': status_val, 'remarks': remarks},
        )
        messages.success(
            request,
            f"Attendance recorded as '{status_val}' on {session_date} for {enrollment.student.user.get_full_display_name()}.",
        )
        return redirect('instructor_dashboard')

    context = {
        'enrollment': enrollment,
        'statuses': Attendance.Status.choices,
        'today': date.today(),
        'history': enrollment.attendance_records.all()[:10],
    }
    return render(request, 'instructors/attendance_form.html', context)


@login_required(login_url='login')
def download_transcript_view(request):
    """Generates an official downloadable academic transcript for the student."""
    student = get_object_or_404(Student, user=request.user)
    enrollments = student.enrollments.select_related('course', 'semester', 'grade').all()

    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Transcript - {student.student_id}</title>
    <style>
        body {{ font-family: Arial, sans-serif; padding: 40px; color: #111; }}
        .header {{ text-align: center; border-bottom: 2px solid #333; padding-bottom: 20px; margin-bottom: 30px; }}
        .info {{ margin-bottom: 20px; font-size: 14px; line-height: 1.6; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
        th, td {{ border: 1px solid #ccc; padding: 10px; text-align: left; font-size: 13px; }}
        th {{ background-color: #f4f4f4; }}
        .footer {{ margin-top: 40px; text-align: right; font-size: 12px; font-weight: bold; }}
    </style>
</head>
<body>
    <div class="header">
        <h2>AETHER UNIVERSITY</h2>
        <h3>Official Academic Transcript &amp; Record of Performance</h3>
    </div>
    <div class="info">
        <div><strong>Student Name:</strong> {student.user.get_full_display_name()}</div>
        <div><strong>Student ID:</strong> {student.student_id}</div>
        <div><strong>Department:</strong> {student.department.name}</div>
        <div><strong>Academic Status:</strong> {student.get_academic_status_display()}</div>
        <div><strong>Cumulative GPA:</strong> {student.calculate_gpa():.2f} / 4.00</div>
    </div>
    <table>
        <tr>
            <th>Course Code</th>
            <th>Course Title</th>
            <th>Credits</th>
            <th>Semester</th>
            <th>Status</th>
            <th>Letter Grade</th>
            <th>Grade Points</th>
        </tr>
"""
    for e in enrollments:
        has_grade = hasattr(e, 'grade') and e.grade is not None
        grade_letter = e.grade.letter_grade if has_grade else 'In Progress'
        grade_pts = f"{e.grade.grade_points:.1f}" if has_grade else '-'
        html_content += f"""        <tr>
            <td>{e.course.code}</td>
            <td>{e.course.title}</td>
            <td>{e.course.credits}</td>
            <td>{e.semester.name}</td>
            <td>{e.get_status_display()}</td>
            <td><strong>{grade_letter}</strong></td>
            <td>{grade_pts}</td>
        </tr>
"""

    html_content += """    </table>
    <div class="footer">
        <p>Verified Institutional Registrar Document • Generated securely via Aether University OS</p>
    </div>
</body>
</html>"""

    response = HttpResponse(html_content, content_type='text/html')
    response['Content-Disposition'] = f'attachment; filename="Transcript_{student.student_id}.html"'
    return response