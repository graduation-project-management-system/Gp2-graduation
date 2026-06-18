from django.urls import path
from . import views

urlpatterns = [
    # Specific named paths (must be before <int:pk>/)
    path('supervisors/',                                views.supervisor_list,                 name='team-supervisors'),
    path('supervisor-inbox/',                           views.supervisor_inbox,                name='team-supervisor-inbox'),
    path('supervisor-requests/<int:req_id>/respond/',   views.respond_to_supervision_request,  name='team-supervisor-respond'),
    path('join-requests/<int:req_id>/vote/',            views.vote_join_request,               name='team-join-vote'),
    path('join-requests/<int:req_id>/cancel/',          views.cancel_join_request,             name='team-join-cancel'),
    path('my/',                                         views.my_team,                         name='team-my'),

    # Standard team endpoints
    path('',                                            views.team_list_create,                name='team-list-create'),
    path('<int:pk>/',                                   views.team_detail,                     name='team-detail'),
    path('<int:pk>/exam-dates/',                        views.team_exam_dates,                 name='team-exam-dates'),
    path('<int:pk>/join-requests/',                     views.membership_requests,             name='team-join-requests'),
    path('<int:pk>/join-requests/<int:req_id>/decide/', views.decide_membership,               name='team-join-decide'),
    path('<int:pk>/comment/',                           views.add_comment,                     name='team-comment'),
    path('<int:pk>/leave/',                             views.leave_team,                      name='leave_team'),
    path('<int:pk>/approve/',                           views.approve_team,                    name='team-approve'),
    path('<int:pk>/reject/',                            views.reject_team,                     name='team-reject'),
    path('<int:pk>/archive/',                           views.archive_team,                    name='team-archive'),
    path('<int:pk>/supervisor-request/',                views.create_supervision_request,      name='team-supervisor-request'),
    path('<int:pk>/supervisor-requests/',               views.team_supervision_requests,       name='team-supervisor-requests'),
]
