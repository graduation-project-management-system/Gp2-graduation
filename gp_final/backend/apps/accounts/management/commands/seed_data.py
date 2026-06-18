"""
python manage.py seed_data

Seeds ALL users from database.js (students + supervisors from JUST university),
plus two demo teams ready to use immediately.

FIXED: now resets the password every run, even if the user already exists.
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

User = get_user_model()

# ── All supervisors from database.js ─────────────────────────────────────────
SUPERVISORS = [
    {'email': 'Hamza@just.edu.jo',    'display_name': 'Hamza Alkofahi',  'password': 'Hamza0*',    'department': 'Computer Science',  'expertise': 'AI,ML'},
    {'email': 'Mohammed@just.edu.jo', 'display_name': 'Mohammed Radaideh','password': 'Mohammed0*', 'department': 'Software Engineering','expertise': 'Web,Cloud'},
    {'email': 'Malik@just.edu.jo',    'display_name': 'Malik Qasimeh',   'password': 'Malik0*',    'department': 'Networks',          'expertise': 'IoT,Security'},
    {'email': 'sadeen@just.edu.jo',   'display_name': 'Sadeen',          'password': 'Sadeen0*',   'department': 'Data Science',      'expertise': 'Data,Analytics'},
    {'email': 'razan@just.edu.jo',    'display_name': 'Razan',           'password': 'Razan0*',    'department': 'HCI',               'expertise': 'UX,Mobile'},
    {'email': 'bayan@just.edu.jo',    'display_name': 'Bayan',           'password': 'Bayan0*',    'department': 'Computer Science',  'expertise': 'Systems'},
    {'email': 'Yanal@just.edu.jo',    'display_name': 'Yanal Alahmad',   'password': 'Yanal0*',    'department': 'Software Engineering','expertise': 'Agile,DevOps'},
    {'email': 'Zakarea@just.edu.jo',  'display_name': 'Zakarea Alshara', 'password': 'Zakaria0*',  'department': 'Networks',          'expertise': 'Cybersecurity'},
    {'email': 'Hasan@just.edu.jo',    'display_name': 'Hasan Albzoor',   'password': 'Hasan0*',    'department': 'Computer Science',  'expertise': 'Databases'},
    {'email': 'Khaldoon@just.edu.jo', 'display_name': 'Khaldoon Alzoubi','password': 'Khaldoon0*', 'department': 'IT',                'expertise': 'Cloud,DevOps'},
    {'email': 'Raed@just.edu.jo',     'display_name': 'Raed Shatnawi',   'password': 'Raed0*',     'department': 'Software Engineering','expertise': 'Software Testing'},
    {'email': 'Asmahan@just.edu.jo',  'display_name': 'Asmahan Alhasan', 'password': 'Asmahan0*',  'department': 'Computer Science',  'expertise': 'NLP,AI'},
    {'email': 'Luay@just.edu.jo',     'display_name': 'Luay Alawneh',    'password': 'Luay0*',     'department': 'Computer Science',  'expertise': 'Distributed Systems'},
]

# ── All students from database.js ─────────────────────────────────────────────
STUDENTS = [
    {'email': 'sadeen@cit.just.edu.jo',    'display_name': 'Sadeen',    'password': 'Sadeen0*'},
    {'email': 'razan@cit.just.edu.jo',     'display_name': 'Razan',     'password': 'Razan0*'},
    {'email': 'bayan@cit.just.edu.jo',     'display_name': 'Bayan',     'password': 'Bayan0*'},
    {'email': 'abdulKarim@cit.just.edu.jo','display_name': 'AbdulKarim','password': 'AbdulKarim0*'},
    {'email': 'hamam@cit.just.edu.jo',     'display_name': 'Hamam',     'password': 'Hamam0*'},
    {'email': 'sara@cit.just.edu.jo',      'display_name': 'Sara',      'password': 'Sara0*'},
    {'email': 'seham@cit.just.edu.jo',     'display_name': 'Seham',     'password': 'Seham0*'},
    {'email': 'omar@cit.just.edu.jo',      'display_name': 'Omar',      'password': 'Omar0*'},
    {'email': 'hala@cit.just.edu.jo',      'display_name': 'Hala',      'password': 'Hala0*'},
]


class Command(BaseCommand):
    help = 'Seed all users from database.js and create demo teams. Always resets passwords.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING('\n=== GP System — Seeding Database ===\n'))

        sup_objs = {}
        stu_objs = {}

        # ── Create / fix supervisors ──────────────────────────────────────────
        self.stdout.write(self.style.HTTP_INFO('-- Supervisors'))
        for s in SUPERVISORS:
            user, created = User.objects.get_or_create(
                email=s['email'],
                defaults={
                    'display_name': s['display_name'],
                    'role':         'supervisor',
                    'department':   s['department'],
                    'expertise':    s['expertise'],
                    'is_active':    True,
                },
            )
            # FIX: always (re)set the password, whether the user is new or already existed
            user.set_password(s['password'])
            user.is_active = True
            user.save()

            if created:
                self.stdout.write(f'  [+] Created supervisor: {user.display_name:25} ({user.email})')
            else:
                self.stdout.write(f'  [~] Reset password for supervisor: {user.display_name:25} ({user.email})')
            sup_objs[s['display_name']] = user

        # ── Create / fix students ─────────────────────────────────────────────
        self.stdout.write(self.style.HTTP_INFO('\n-- Students'))
        for s in STUDENTS:
            user, created = User.objects.get_or_create(
                email=s['email'],
                defaults={
                    'display_name': s['display_name'],
                    'role':         'student',
                    'is_active':    True,
                },
            )
            # FIX: always (re)set the password, whether the user is new or already existed
            user.set_password(s['password'])
            user.is_active = True
            user.save()

            if created:
                self.stdout.write(f'  [+] Created student: {user.display_name:20} ({user.email})')
            else:
                self.stdout.write(f'  [~] Reset password for student: {user.display_name:20} ({user.email})')
            stu_objs[s['display_name']] = user

        # ── Admin superuser ───────────────────────────────────────────────────
        self.stdout.write(self.style.HTTP_INFO('\n-- Admin'))
        admin_user = User.objects.filter(email='admin@just.edu.jo').first()
        if admin_user is None:
            User.objects.create_superuser(
                email='admin@just.edu.jo',
                password='Admin@GP2025',
                display_name='System Admin',
                role='admin',
            )
            self.stdout.write('  [+] Created superuser: admin@just.edu.jo / Admin@GP2025')
        else:
            # FIX: always (re)set the password for the admin too
            admin_user.set_password('Admin@GP2025')
            admin_user.is_active = True
            admin_user.is_staff = True
            admin_user.is_superuser = True
            admin_user.save()
            self.stdout.write('  [~] Reset password for superuser: admin@just.edu.jo / Admin@GP2025')

        # Summary table
        self.stdout.write(self.style.SUCCESS('\n' + '='*60))
        self.stdout.write(self.style.SUCCESS('  Database seeded / passwords reset successfully!\n'))
        self.stdout.write('  SUPERVISOR LOGIN CREDENTIALS')
        for s in SUPERVISORS:
            self.stdout.write(f'    {s["email"]}  /  {s["password"]}')
        self.stdout.write('  STUDENT LOGIN CREDENTIALS')
        for s in STUDENTS:
            self.stdout.write(f'    {s["email"]}  /  {s["password"]}')
        self.stdout.write('    admin@just.edu.jo  /  Admin@GP2025')
        self.stdout.write('\n  Open: http://127.0.0.1:8000/\n')

    def _create_demo_teams(self, sup_objs, stu_objs):
        from apps.teams.models import Team, ExamDate
        self.stdout.write(self.style.HTTP_INFO('\n-- Demo Teams'))

        hamza  = sup_objs.get('Hamza Alkofahi')
        sadeen_s = stu_objs.get('Sadeen')
        razan_s  = stu_objs.get('Razan')
        bayan_s  = stu_objs.get('Bayan')
        sara_s   = stu_objs.get('Sara')
        omar_s   = stu_objs.get('Omar')

        if hamza and sadeen_s and not Team.objects.filter(name='Team Alpha').exists():
            t = Team.objects.create(
                name='Team Alpha',
                project_title='AI Attendance System',
                project_description='Face-recognition attendance tracker for JUST.',
                status='active',
                leader=sadeen_s,
                assigned_supervisor=hamza,
                progress=45,
                academic_year='2025-2026',
            )
            members = [x for x in [sadeen_s, razan_s, bayan_s] if x]
            t.members.set(members)
            ExamDate.objects.get_or_create(team=t, date='2026-02-23')
            self.stdout.write('  [OK] Team Alpha created - assigned to Hamza Alkofahi')

        if hamza and sara_s and not Team.objects.filter(name='Team Nova').exists():
            t = Team.objects.create(
                name='Team Nova',
                project_title='Smart Clinic App',
                project_description='Mobile clinic appointment booking system.',
                status='active',
                leader=sara_s,
                assigned_supervisor=hamza,
                progress=62,
                academic_year='2025-2026',
            )
            members = [x for x in [sara_s, omar_s] if x]
            t.members.set(members)
            ExamDate.objects.get_or_create(team=t, date='2026-02-24')
            self.stdout.write('  [OK] Team Nova created - assigned to Hamza Alkofahi')
