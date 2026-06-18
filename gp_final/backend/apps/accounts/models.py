"""
accounts/models.py — Custom User Model for the GP System

Why a custom user model?
  Django's default User model uses a username as the primary identifier.
  This project uses email addresses instead, which is more natural for an
  academic system where students and supervisors are identified by their
  university email.

Key design choices:
  - AbstractBaseUser: gives us full control over authentication fields
    (password hashing, last_login) without inheriting Django's username field.
  - PermissionsMixin: adds is_superuser, groups, and user_permissions so
    Django's admin and permission system work without modification.
  - UserManager: required by AbstractBaseUser to define create_user() and
    create_superuser() so Django's CLI (createsuperuser) still works.
  - UserRole: TextChoices enum keeps role values as readable strings in the DB
    ('student', 'supervisor', 'admin') rather than integers.
"""

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models


# ── Role choices ───────────────────────────────────────────────────────────────

class UserRole(models.TextChoices):
    """
    Allowed values for the User.role field.

    TextChoices stores the first value ('student') in the database and displays
    the second value ('Student') in the Django admin and serializers.

    Roles determine which pages and API endpoints a user can access:
      STUDENT    — can submit supervision requests, upload files, view meetings
      SUPERVISOR — can approve requests, create slots, grade teams, view files
      ADMIN      — full Django admin access (managed via Django admin panel)
    """
    STUDENT    = 'student',    'Student'
    SUPERVISOR = 'supervisor', 'Supervisor'
    ADMIN      = 'admin',      'Admin'


# ── Custom manager ─────────────────────────────────────────────────────────────

class UserManager(BaseUserManager):
    """
    Manager for the custom User model.

    BaseUserManager provides helpers like normalize_email() (lowercases the
    domain part of an email address) and is required when using AbstractBaseUser.

    Two methods are mandatory:
      create_user()      — used in the register API endpoint and seed_data command
      create_superuser() — used by Django's `createsuperuser` management command
    """

    def create_user(self, email, password=None, **extra):
        """
        Create and save a regular user with the given email and password.

        Steps:
          1. Validate that an email was provided (AbstractBaseUser has no username).
          2. Normalize the email (lowercase domain) so 'User@EXAMPLE.COM'
             and 'user@example.com' are treated as the same address.
          3. Build the User instance with any additional keyword arguments
             (display_name, role, department, etc.).
          4. Hash the password with Django's PBKDF2 hasher via set_password().
          5. Save to the database.

        @param email    - The user's email address (becomes their login identifier).
        @param password - Plaintext password; stored as a hash, never in plaintext.
        @param **extra  - Any additional User field values (display_name, role, etc.)
        @returns        - The newly created and saved User instance.
        """
        if not email:
            raise ValueError('Email required.')
        email = self.normalize_email(email)        # e.g. 'Ali@EXAMPLE.COM' → 'Ali@example.com'
        user  = self.model(email=email, **extra)   # build the model instance (not yet saved)
        user.set_password(password)                # hash the password via PBKDF2
        user.save(using=self._db)                  # write to the database
        return user

    def create_superuser(self, email, password=None, **extra):
        """
        Create and save a superuser (used by `manage.py createsuperuser`).

        Superusers get:
          - role='admin' so they appear correctly in the API
          - is_staff=True so they can log in to /admin/
          - is_superuser=True so they bypass all Django permission checks

        setdefault() lets the caller override these defaults if needed
        (though for createsuperuser this is rarely necessary).
        """
        extra.setdefault('role', UserRole.ADMIN)
        extra.setdefault('is_staff', True)
        extra.setdefault('is_superuser', True)
        return self.create_user(email, password, **extra)  # delegate to create_user


# ── User model ─────────────────────────────────────────────────────────────────

class User(AbstractBaseUser, PermissionsMixin):
    """
    The single user model for all roles in the GP System.

    AbstractBaseUser provides:
      - password     — hashed password field (managed by set_password / check_password)
      - last_login   — automatically updated on each authentication
      - is_active    — account enable/disable flag checked during authentication

    PermissionsMixin adds:
      - is_superuser         — bypasses all permission checks
      - groups               — many-to-many to Permission groups
      - user_permissions     — per-user permission overrides

    Fields:
      email        — login identifier (unique across all users)
      display_name — shown in the UI and notifications (e.g. "Dr. Ahmed Ali")
      role         — one of student / supervisor / admin (controls page access)
      department   — optional faculty/department affiliation
      expertise    — optional research area description (for supervisors)
      avatar       — optional profile photo uploaded to media/avatars/
      is_active    — if False, user cannot log in (soft delete)
      is_staff     — if True, user can access Django admin panel
      created_at   — auto-set to UTC now at creation time

    Configuration:
      USERNAME_FIELD  = 'email'           — email replaces username for authentication
      REQUIRED_FIELDS = ['display_name']  — asked by createsuperuser after email+password
    """

    # Login identifier — must be unique so no two users share an email
    email        = models.EmailField(unique=True)

    # Human-readable name shown in the UI (e.g. "Ahmed Al-Rashidi")
    display_name = models.CharField(max_length=150)

    # Role determines which parts of the system the user can access
    role         = models.CharField(max_length=20, choices=UserRole.choices, default=UserRole.STUDENT)

    # Optional fields — used in supervisor profiles and student registration
    department   = models.CharField(max_length=150, blank=True)
    expertise    = models.CharField(max_length=255, blank=True)
    gpa = models.DecimalField(max_digits=3,decimal_places=2,null=True,blank=True)
    gpa = models.DecimalField(
    max_digits=3,
    decimal_places=2,
    null=True,
    blank=True
)
    # Optional profile picture — stored in MEDIA_ROOT/avatars/ on the server
    avatar       = models.ImageField(upload_to='avatars/', null=True, blank=True)

    # Django-required flags: is_active controls login; is_staff controls admin access
    is_active    = models.BooleanField(default=True)
    is_staff     = models.BooleanField(default=False)

    # Automatically set to the creation timestamp — never updated after that
    created_at   = models.DateTimeField(auto_now_add=True)

    # Attach the custom manager so User.objects.create_user() works correctly
    objects = UserManager()

    # Tell Django to use email (not username) as the authentication field
    USERNAME_FIELD  = 'email'

    # Fields prompted by `manage.py createsuperuser` in addition to email + password
    REQUIRED_FIELDS = ['display_name']

    class Meta:
        # Explicit table name — avoids Django's default 'accounts_user' naming conflict
        # with the auth_user table if both apps are installed simultaneously
        db_table = 'accounts_user'

    def __str__(self):
        """String representation shown in Django admin and debug output."""
        return f'{self.display_name} <{self.email}>'

    # ── Convenience properties ─────────────────────────────────────────────────

    @property
    def is_supervisor(self):
        """Returns True if this user is a supervisor — used in permission checks."""
        return self.role == UserRole.SUPERVISOR

    @property
    def is_student(self):
        """Returns True if this user is a student — used in permission checks."""
        return self.role == UserRole.STUDENT
