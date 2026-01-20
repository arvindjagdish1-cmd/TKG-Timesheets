from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from simple_history.models import HistoricalRecords


class UserManager(BaseUserManager):
    """Custom user manager using email as the unique identifier."""

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Email address is required")
        email = self.normalize_email(email).lower()
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """
    Custom User model using email as the unique identifier.
    Works with Microsoft OAuth via django-allauth.
    """

    email = models.EmailField("email address", unique=True, db_index=True)
    first_name = models.CharField("first name", max_length=150, blank=True)
    last_name = models.CharField("last name", max_length=150, blank=True)

    is_staff = models.BooleanField(
        "staff status",
        default=False,
        help_text="Designates whether the user can log into the admin site.",
    )
    is_active = models.BooleanField(
        "active",
        default=True,
        help_text="Designates whether this user should be treated as active.",
    )
    date_joined = models.DateTimeField("date joined", auto_now_add=True)

    # Audit trail
    history = HistoricalRecords()

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []  # Email is already required via USERNAME_FIELD

    class Meta:
        verbose_name = "user"
        verbose_name_plural = "users"
        ordering = ["email"]

    def __str__(self):
        return self.email

    def get_full_name(self):
        full_name = f"{self.first_name} {self.last_name}".strip()
        return full_name if full_name else self.email

    def get_short_name(self):
        return self.first_name if self.first_name else self.email.split("@")[0]

    @property
    def display_name(self):
        """Return full name if available, otherwise email."""
        return self.get_full_name()


class EmployeeProfile(models.Model):
    """
    Extended profile for employees.
    Contains employment details, seniority for report ordering, etc.
    """

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="profile",
        primary_key=True,
    )

    # Employment info
    employee_id = models.CharField(
        "employee ID",
        max_length=50,
        blank=True,
        help_text="Internal employee identifier (optional).",
    )
    title = models.CharField("job title", max_length=150, blank=True)
    department = models.CharField("department", max_length=100, blank=True)

    # For sorting in export PDFs
    seniority_order = models.PositiveIntegerField(
        "seniority order",
        default=999,
        help_text="Lower number = more senior. Used for sorting reports.",
    )

    # Employment status
    hire_date = models.DateField("hire date", null=True, blank=True)
    termination_date = models.DateField("termination date", null=True, blank=True)
    is_exempt = models.BooleanField(
        "exempt employee",
        default=True,
        help_text="Whether the employee is exempt from overtime rules.",
    )

    # Contact
    phone = models.CharField("phone number", max_length=30, blank=True)
    emergency_contact_name = models.CharField(max_length=150, blank=True)
    emergency_contact_phone = models.CharField(max_length=30, blank=True)

    # Mileage reimbursement
    mileage_rate = models.DecimalField(
        "mileage rate ($/mile)",
        max_digits=5,
        decimal_places=3,
        default=0.67,
        help_text="IRS standard mileage rate for reimbursement.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Audit trail
    history = HistoricalRecords()

    class Meta:
        verbose_name = "employee profile"
        verbose_name_plural = "employee profiles"
        ordering = ["seniority_order", "user__last_name", "user__first_name"]

    def __str__(self):
        return f"{self.user.get_full_name()} Profile"

    @property
    def is_active_employee(self):
        """Check if employee is currently active (no termination date or future)."""
        from django.utils import timezone

        if not self.termination_date:
            return True
        return self.termination_date > timezone.now().date()

    @property
    def full_name(self):
        return self.user.get_full_name()

    @property
    def email(self):
        return self.user.email
