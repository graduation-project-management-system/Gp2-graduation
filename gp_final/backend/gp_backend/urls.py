from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView, RedirectView
from rest_framework_simplejwt.views import TokenRefreshView
from gp_backend import admin_api
from apps.proposals import views as proposal_views


def page(name):
    return TemplateView.as_view(template_name=name)


urlpatterns = [
    # Root
    path('', RedirectView.as_view(url='/login.html'), name='root'),

    # Frontend pages
    path('login.html',                           page('login.html')),
    path('student_dashboard.html',               page('student_dashboard.html')),
    path('team_dashboard.html',                  page('team_dashboard.html')),
    path('chat.html',                            page('chat.html')),
    path('create_team.html',                     page('create_team.html')),
    path('join_team.html',                       page('join_team.html')),
    path('supervisors_list.html',                page('supervisors_list.html')),
    path('supervisor-request.html',              page('supervisor-request.html')),
    path('Supervisor_dashboard.html',            page('Supervisor_dashboard.html')),
    path('supervisor_student_requests.html',     page('supervisor_student_requests.html')),
    path('supervisor_my_teams.html',             page('supervisor_my_teams.html')),
    path('supervisor_schedule_discussions.html', page('supervisor_schedule_discussions.html')),
    path('supervisor_grading_reports.html',      page('supervisor_grading_reports.html')),
    path('supervisor_notifications.html',        page('supervisor_notifications.html')),
    path('supervisor_files.html',                page('supervisor_files.html')),
    path('admin.html', page('admin.html')),
    # Clean URL aliases for Cypress tests
    path('create-team/',      page('create_team.html')),
    path('team-dashboard/',   page('team_dashboard.html')),
    path('chat/',             page('chat.html')),
    path('supervisors-list/', page('supervisors_list.html')),
    # Django admin
    path('admin/', admin.site.urls),

    # JWT
    path('api/v1/auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # Original APIs
    path('api/v1/auth/',          include('apps.accounts.urls')),
    path('api/v1/teams/',         include('apps.teams.urls')),
    path('api/v1/requests/',      include('apps.requests.urls')),
    path('api/v1/meetings/',      include('apps.meetings.urls')),
    path('api/v1/grading/',       include('apps.grading.urls')),
    path('api/v1/notifications/', include('apps.notifications.urls')),
    path('api/v1/files/',         include('apps.files.urls')),
    path('api/v1/chat/',          include('apps.chat.urls')),
    path('api/v1/supervisor/',    include('apps.supervisor_context.interfaces.urls')),

    # ── Admin panel APIs ───────────────────────────────────────────────────────
    path('api/dashboard/',                   admin_api.dashboard,        name='admin-dashboard'),
    # Proposals
    path('api/proposals/',                   admin_api.proposals_list,   name='admin-proposals'),
    path('api/proposals/create/',            proposal_views.create_proposal_api, name='admin-proposals-create'),
    path('api/proposals/<int:pk>/',          admin_api.proposal_detail,  name='admin-proposal-detail'),
    path('api/proposals/<int:pk>/approve/',  admin_api.proposal_approve, name='admin-proposal-approve'),
    path('api/proposals/<int:pk>/reject/',   admin_api.proposal_reject,  name='admin-proposal-reject'),
    # Defense
    path('api/defense/',                     admin_api.defense_list,     name='admin-defense'),
    path('api/defense/<int:pk>/',            admin_api.defense_detail,   name='admin-defense-detail'),
    # Grades
    path('api/grades/',                      admin_api.grades_list,      name='admin-grades'),
    path('api/grades/create/',               admin_api.grades_create,    name='admin-grades-create'),
    path('api/grades/<int:pk>/approve/',     admin_api.grade_approve,    name='admin-grade-approve'),
    path('api/grades/<int:pk>/reject/',      admin_api.grade_reject,     name='admin-grade-reject'),
    path('api/grades/<int:pk>/',             admin_api.grade_delete,     name='admin-grade-delete'),
    # Activity
    path('api/activity/',                    admin_api.activity_list,    name='admin-activity'),
    # Students (admin CRUD)
    path('api/students/',                    admin_api.students_list,    name='admin-students'),
    path('api/students/create/',             admin_api.students_list,    name='admin-students-create'),
    path('api/students/<int:pk>/',           admin_api.student_detail,   name='admin-student-detail'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
