from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from apps.accounts.models import Student
from .models import Course, Enrollment, Assignment, Submission, Grade
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