from django.contrib import admin
from django.urls import path
from django.views.generic import TemplateView
from django.conf import settings
from django.conf.urls.static import static
from apps.accounts import views as account_views
from apps.academics import views as academic_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', TemplateView.as_view(template_name='landing.html'), name='landing'),
    path('login/', account_views.portal_login_view, name='login'),
    path('logout/', account_views.portal_logout_view, name='logout'),
    path('student/dashboard/', account_views.student_dashboard_view, name='student_dashboard'),
    path('instructor/dashboard/', account_views.instructor_dashboard_view, name='instructor_dashboard'),
    path('administrator/dashboard/', account_views.admin_dashboard_view, name='admin_dashboard'),

    # Lesson 6 & 7 Interactive Academic Routes
    path('student/enroll/<int:course_id>/', academic_views.enroll_course_view, name='enroll_course'),
    path('student/withdraw/<int:enrollment_id>/', academic_views.withdraw_course_view, name='withdraw_course'),
    path('student/submit/<int:assignment_id>/', academic_views.submit_assignment_view, name='submit_assignment'),
    path('student/transcript/download/', academic_views.download_transcript_view, name='download_transcript'),
    path('instructor/grade/<int:enrollment_id>/', academic_views.instructor_grade_view, name='instructor_grade'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)