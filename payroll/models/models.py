"""
models.py
Used to register models
"""
import calendar
from collections.abc import Iterable
from datetime import date, datetime, timedelta
import threading
from typing import Any
from django import forms
from django.db import models
from django.dispatch import receiver
from django.contrib import messages
from django.db.models.signals import post_save
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.db.models.signals import pre_save, pre_delete
from django.http import QueryDict
from asset.models import Asset
from base import thread_local_middleware
from employee.models import EmployeeWorkInformation
from employee.models import Employee, Department, JobPosition
from base.models import Company, EmployeeShift, WorkType, JobRole
from base.horilla_company_manager import HorillaCompanyManager
from attendance.models import (
    validate_time_format,
)
from attendance.models import (
    Attendance,
    strtime_seconds,
)
from leave.models import LeaveRequest, LeaveType


# Create your models here.


def get_date_range(start_date, end_date):
    """
    Returns a list of all dates within a given date range.

    Args:
        start_date (date): The start date of the range.
        end_date (date): The end date of the range.

    Returns:
        list: A list of date objects representing all dates within the range.

    Example:
        start_date = date(2023, 1, 1)
        end_date = date(2023, 1, 10)
        date_range = get_date_range(start_date, end_date)
        for date_obj in date_range:
            print(date_obj)
    """
    date_list = []
    delta = end_date - start_date

    for i in range(delta.days + 1):
        current_date = start_date + timedelta(days=i)
        date_list.append(current_date)

    return date_list


class FilingStatus(models.Model):
    """
    FilingStatus model
    """

    based_on_choice = [
        ("basic_pay", _("Basic Pay")),
        ("gross_pay", _("Gross Pay")),
        ("taxable_gross_pay", _("Taxable Gross Pay")),
    ]
    filing_status = models.CharField(
        max_length=30,
        blank=False,
        verbose_name=_("Filing status"),
    )
    based_on = models.CharField(
        max_length=255,
        choices=based_on_choice,
        null=False,
        blank=False,
        default="taxable_gross_pay",
        verbose_name=_("Based on"),
    )
    description = models.TextField(
        blank=True,
        verbose_name=_("Description"),
    )
    company_id = models.ForeignKey(
        Company, null=True, editable=False, on_delete=models.PROTECT
    )
    objects = HorillaCompanyManager()

    def __str__(self) -> str:
        return str(self.filing_status)


class Contract(models.Model):
    """
    Contract Model
    """

    COMPENSATION_CHOICES = (
        ("salary", _("Salary")),
        ("hourly", _("Hourly")),
        ("commission", _("Commission")),
    )

    PAY_FREQUENCY_CHOICES = (
        ("weekly", _("Weekly")),
        ("monthly", _("Monthly")),
        ("semi_monthly", _("Semi-Monthly")),
    )
    WAGE_CHOICES = (
        ("hourly", _("Hourly")),
        ("daily", _("Daily")),
        ("monthly", _("Monthly")),
    )
    CONTRACT_STATUS_CHOICES = (
        ("draft", _("Draft")),
        ("active", _("Active")),
        ("expired", _("Expired")),
        ("terminated", _("Terminated")),
    )

    contract_name = models.CharField(
        max_length=250, help_text=_("Contract Title"), verbose_name=_("Contract")
    )
    employee_id = models.ForeignKey(
        Employee,
        on_delete=models.PROTECT,
        related_name="contract_set",
        verbose_name=_("Employee"),
    )
    contract_start_date = models.DateField(verbose_name=_("Start date"))
    contract_end_date = models.DateField(
        null=True, blank=True, verbose_name=_("End date")
    )
    wage_type = models.CharField(
        choices=WAGE_CHOICES,
        max_length=250,
        default="monthly",
        verbose_name=_("Wage Type"),
    )
    pay_frequency = models.CharField(
        max_length=20,
        null=True,
        choices=PAY_FREQUENCY_CHOICES,
        default="monthly",
        verbose_name=_("Pay Frequency"),
    )
    wage = models.FloatField(verbose_name=_("Basic Salary"), null=True, default=0)
    filing_status = models.ForeignKey(
        FilingStatus,
        on_delete=models.PROTECT,
        related_name="contracts",
        null=True,
        blank=True,
        verbose_name=_("Filing Status"),
    )
    contract_status = models.CharField(
        choices=CONTRACT_STATUS_CHOICES,
        max_length=250,
        default="draft",
        verbose_name=_("Status"),
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="contracts",
        verbose_name=_("Department"),
    )
    job_position = models.ForeignKey(
        JobPosition,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="contracts",
        verbose_name=_("Job Position"),
    )
    job_role = models.ForeignKey(
        JobRole,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="contracts",
        verbose_name=_("Job Role"),
    )
    shift = models.ForeignKey(
        EmployeeShift,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="contracts",
        verbose_name=_("Shift"),
    )
    work_type = models.ForeignKey(
        WorkType,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="contracts",
        verbose_name=_("Work Type"),
    )
    contract_document = models.FileField(upload_to="uploads/", null=True, blank=True)
    is_active = models.BooleanField(default=True)
    calculate_daily_leave_amount = models.BooleanField(
        default=True, verbose_name=_("Calculate Daily Leave Amount")
    )
    deduction_for_one_leave_amount = models.FloatField(
        null=True,
        blank=True,
        default=0,
        verbose_name=_("Deduction For One Leave Amount"),
    )
    deduct_leave_from_basic_pay = models.BooleanField(
        default=True, verbose_name=_("Deduct From Basic Pay")
    )

    note = models.TextField(null=True, blank=True)

    objects = HorillaCompanyManager("employee_id__employee_work_info__company_id")

    def __str__(self) -> str:
        return f"{self.contract_name} -{self.contract_start_date} - {self.contract_end_date}"

    def clean(self):
        if self.contract_end_date is not None:
            if self.contract_end_date < self.contract_start_date:
                raise ValidationError(
                    {"contract_end_date": _("End date must be greater than start date")}
                )
        if (
            self.contract_status == "active"
            and Contract.objects.filter(
                employee_id=self.employee_id, contract_status="active"
            )
            .exclude(id=self.id)
            .count()
            >= 1
        ):
            raise forms.ValidationError(
                _("An active contract already exists for this employee.")
            )
        if (
            self.contract_status == "draft"
            and Contract.objects.filter(
                employee_id=self.employee_id, contract_status="draft"
            )
            .exclude(id=self.id)
            .count()
            >= 1
        ):
            raise forms.ValidationError(
                _("A draft contract already exists for this employee.")
            )

        if self.wage_type in ["daily", "monthly"]:
            if not self.calculate_daily_leave_amount:
                if self.deduction_for_one_leave_amount is None:
                    raise ValidationError(
                        {"deduction_for_one_leave_amount": _("This field is required")}
                    )

    def save(self, *args, **kwargs):
        if EmployeeWorkInformation.objects.filter(
            employee_id=self.employee_id
        ).exists():
            if self.department is None:
                self.department = self.employee_id.employee_work_info.department_id

            if self.job_position is None:
                self.job_position = self.employee_id.employee_work_info.job_position_id

            if self.job_role is None:
                self.job_role = self.employee_id.employee_work_info.job_role_id

            if self.work_type is None:
                self.work_type = self.employee_id.employee_work_info.work_type_id

            if self.shift is None:
                self.shift = self.employee_id.employee_work_info.shift_id
        if self.contract_end_date is not None and self.contract_end_date < date.today():
            self.contract_status = "expired"
        if (
            self.contract_status == "active"
            and Contract.objects.filter(
                employee_id=self.employee_id, contract_status="active"
            )
            .exclude(id=self.id)
            .count()
            >= 1
        ):
            raise forms.ValidationError(
                _("An active contract already exists for this employee.")
            )

        if (
            self.contract_status == "draft"
            and Contract.objects.filter(
                employee_id=self.employee_id, contract_status="draft"
            )
            .exclude(id=self.id)
            .count()
            >= 1
        ):
            raise forms.ValidationError(
                _("A draft contract already exists for this employee.")
            )

        super().save(*args, **kwargs)
        return self

    class Meta:
        """
        Meta class to add additional options
        """

        unique_together = ["employee_id", "contract_start_date", "contract_end_date"]


class WorkRecord(models.Model):
    """
    WorkRecord Model
    """

    choices = [
        ("FDP", _("Present")),
        ("HDP", _("Half Day Present")),
        ("ABS", _("Absent")),
        ("HD", _("Holiday/Company Leave")),
        ("CONF", _("Conflict")),
        ("DFT", _("Draft")),
    ]

    record_name = models.CharField(max_length=250, null=True, blank=True)
    work_record_type = models.CharField(max_length=5, null=True, choices=choices)
    employee_id = models.ForeignKey(
        Employee, on_delete=models.PROTECT, verbose_name=_("Employee")
    )
    date = models.DateField(null=True, blank=True)
    at_work = models.CharField(
        null=True,
        blank=True,
        validators=[
            validate_time_format,
        ],
        default="00:00",
        max_length=5,
    )
    min_hour = models.CharField(
        null=True,
        blank=True,
        validators=[
            validate_time_format,
        ],
        default="00:00",
        max_length=5,
    )
    at_work_second = models.IntegerField(null=True, blank=True, default=0)
    min_hour_second = models.IntegerField(null=True, blank=True, default=0)
    note = models.TextField()
    color = models.CharField(
        max_length=10,
        null=True,
        blank=True,
    )
    message = models.CharField(max_length=30, null=True, blank=True)
    is_attendance_record = models.BooleanField(default=False)
    is_leave_record = models.BooleanField(default=False)
    day_percentage = models.FloatField(default=0)
    objects = HorillaCompanyManager("employee_id__employee_work_info__company_id")

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        if not 0.0 <= self.day_percentage <= 1.0:
            raise ValidationError(_("Day percentage must be between 0.0 and 1.0"))

    def __str__(self):
        return (
            self.record_name
            if self.record_name is not None
            else f"{self.work_record_type}-{self.date}"
        )


class OverrideAttendance(Attendance):
    """
    Class to override Attendance model save method
    """

    # Additional fields and methods specific to AnotherModel
    @receiver(pre_save, sender=Attendance)
    def attendance_pre_save(sender, instance, **_kwargs):
        """
        Overriding Attendance model save method
        """
        min_hour_second = strtime_seconds(instance.minimum_hour)
        at_work_second = strtime_seconds(instance.attendance_worked_hour)
        status = "FDP" if instance.at_work_second >= min_hour_second else "HDP"
        status = (
            "CONF"
            if WorkRecord.objects.filter(
                date=instance.attendance_date,
                is_attendance_record=False,
                employee_id=instance.employee_id,
            ).exists()
            or instance.attendance_validated is False
            else status
        )
        message = _("Validate the attendance") if status == "CONF" else _("Validated")
        message = (
            _("Incomplete minimum hour")
            if status == "HDP" and min_hour_second / 2 > at_work_second
            else message
        )
        work_record = (
            WorkRecord()
            if not WorkRecord.objects.filter(
                is_attendance_record=True,
                date=instance.attendance_date,
                employee_id=instance.employee_id,
            ).exists()
            else WorkRecord.objects.filter(
                is_attendance_record=True,
                date=instance.attendance_date,
                employee_id=instance.employee_id,
            ).first()
        )
        work_record.employee_id = instance.employee_id
        work_record.date = instance.attendance_date
        work_record.at_work = instance.attendance_worked_hour
        work_record.min_hour = instance.minimum_hour
        work_record.min_hour_second = min_hour_second
        work_record.at_work_second = at_work_second
        work_record.work_record_type = status
        work_record.message = message
        work_record.is_attendance_record = True
        if instance.attendance_validated:
            work_record.day_percentage = (
                1.00 if at_work_second > min_hour_second / 2 else 0.50
            )
        work_record.save()

    @receiver(pre_delete, sender=Attendance)
    def attendance_pre_delete(sender, instance, **_kwargs):
        """
        Overriding Attendance model delete method
        """
        # Perform any actions before deleting the instance
        # ...
        WorkRecord.objects.filter(
            employee_id=instance.employee_id,
            is_attendance_record=True,
            date=instance.attendance_date,
        ).delete()


class OverrideLeaveRequest(LeaveRequest):
    """
    Class to override Attendance model save method
    """

    # Additional fields and methods specific to AnotherModel
    @receiver(pre_save, sender=LeaveRequest)
    def leaverequest_pre_save(sender, instance, **_kwargs):
        """
        Overriding LeaveRequest model save method
        """
        if (
            instance.start_date == instance.end_date
            and instance.end_date_breakdown != instance.start_date_breakdown
        ):
            instance.end_date_breakdown = instance.start_date_breakdown
            super(LeaveRequest, instance).save()

        period_dates = get_date_range(instance.start_date, instance.end_date)
        if instance.status == "approved":
            for date in period_dates:
                try:
                    work_entry = (
                        WorkRecord.objects.filter(
                            is_leave_record=True,
                            date=date,
                            employee_id=instance.employee_id,
                        )
                        if WorkRecord.objects.filter(
                            is_leave_record=True,
                            date=date,
                            employee_id=instance.employee_id,
                        ).exists()
                        else WorkRecord()
                    )
                    work_entry.employee_id = instance.employee_id
                    work_entry.is_leave_record = True
                    work_entry.day_percentage = (
                        0.50
                        if instance.start_date == date
                        and instance.start_date_breakdown == "first_half"
                        or instance.end_date == date
                        and instance.end_date_breakdown == "second_half"
                        else 0.00
                    )
                    # scheduler task to validate the conflict entry for half day if they
                    # take half day leave is when they mark the attendance.
                    status = (
                        "CONF"
                        if instance.start_date == date
                        and instance.start_date_breakdown == "first_half"
                        or instance.end_date == date
                        and instance.end_date_breakdown == "second_half"
                        else "ABS"
                    )
                    work_entry.work_record_type = status
                    work_entry.date = date
                    work_entry.message = (
                        "Validated"
                        if status == "ABS"
                        else _("Half day need to validate")
                    )
                    work_entry.save()
                except:
                    pass

        else:
            for date in period_dates:
                WorkRecord.objects.filter(
                    is_leave_record=True, date=date, employee_id=instance.employee_id
                ).delete()


class OverrideWorkInfo(EmployeeWorkInformation):
    """
    This class is to override the Model default methods
    """

    @receiver(pre_save, sender=EmployeeWorkInformation)
    def employeeworkinformation_pre_save(sender, instance, **_kwargs):
        """
        This method is used to override the save method for EmployeeWorkInformation Model
        """
        active_employee = (
            instance.employee_id if instance.employee_id.is_active == True else None
        )
        if active_employee is not None:
            contract_exists = active_employee.contract_set.exists()
            if not contract_exists:
                contract = Contract()
                contract.contract_name = f"{active_employee}'s Contract"
                contract.employee_id = active_employee
                contract.contract_start_date = datetime.today()
                contract.wage = (
                    instance.basic_salary if instance.basic_salary is not None else 0
                )
                contract.save()


# Create your models here.
def rate_validator(value):
    """
    Percentage validator
    """
    if value < 0:
        raise ValidationError(_("Rate must be greater than 0"))
    if value > 100:
        raise ValidationError(_("Rate must be less than 100"))


def min_zero(value):
    """
    The minimum value zero validation method
    """
    if value < 0:
        raise ValidationError(_("Value must be greater than zero"))


CONDITION_CHOICE = [
    ("equal", _("Equal (==)")),
    ("notequal", _("Not Equal (!=)")),
    ("lt", _("Less Than (<)")),
    ("gt", _("Greater Than (>)")),
    ("le", _("Less Than or Equal To (<=)")),
    ("ge", _("Greater Than or Equal To (>=)")),
    ("icontains", _("Contains")),
]
IF_CONDITION_CHOICE = [
    ("equal", _("Equal (==)")),
    ("notequal", _("Not Equal (!=)")),
    ("lt", _("Less Than (<)")),
    ("gt", _("Greater Than (>)")),
    ("le", _("Less Than or Equal To (<=)")),
    ("ge", _("Greater Than or Equal To (>=)")),
]
FIELD_CHOICE = [
    ("children", _("Children")),
    ("marital_status", _("Marital Status")),
    ("experience", _("Experience")),
    ("employee_work_info__experience", _("Company Experience")),
    ("gender", _("Gender")),
    ("country", _("Country")),
    ("state", _("State")),
    ("contract_set__pay_frequency", _("Pay Frequency")),
    ("contract_set__wage_type", _("Wage Type")),
    ("contract_set__department__department", _("Department on Contract")),
]


class MultipleCondition(models.Model):
    """
    MultipleCondition Model
    """

    field = models.CharField(
        max_length=255,
    )
    condition = models.CharField(
        max_length=255, choices=CONDITION_CHOICE, null=True, blank=True
    )
    value = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text=_("The value must be like the data stored in the database"),
    )


class Allowance(models.Model):
    """
    Allowance model
    """

    exceed_choice = [
        ("ignore", _("Exclude the allowance")),
        ("max_amount", _("Provide max amount")),
    ]

    based_on_choice = [
        ("basic_pay", _("Basic Pay")),
        ("attendance", _("Attendance")),
        ("shift_id", _("Shift")),
        ("overtime", _("Overtime")),
        ("work_type_id", _("Work Type")),
    ]

    if_condition_choice = [
        ("basic_pay", _("Basic Pay")),
    ]
    title = models.CharField(
        max_length=255, null=False, blank=False, help_text=_("Title of the allowance")
    )
    one_time_date = models.DateField(
        null=True,
        blank=True,
        help_text=_(
            "The one-time allowance in which the allowance will apply to the payslips \
            if the date between the payslip period"
        ),
    )
    include_active_employees = models.BooleanField(
        default=False,
        verbose_name=_("Include all active employees"),
        help_text=_("Target allowance to all active employees in the company"),
    )
    specific_employees = models.ManyToManyField(
        Employee,
        verbose_name=_("Employees Specific"),
        blank=True,
        related_name="allowance_specific",
        help_text=_("Target allowance to the specific employees"),
    )
    exclude_employees = models.ManyToManyField(
        Employee,
        verbose_name=_("Exclude Employees"),
        related_name="allowance_excluded",
        blank=True,
        help_text=_(
            "To ignore the allowance to the employees when target them by all employees \
            or through condition-based"
        ),
    )
    is_taxable = models.BooleanField(
        default=True,
        help_text=_("This field is used to calculate the taxable allowances"),
    )
    is_condition_based = models.BooleanField(
        default=False,
        help_text=_(
            "This field is used to target allowance \
        to the specific employees when the condition satisfies with the employee's information"
        ),
    )
    # If condition based
    field = models.CharField(
        max_length=255,
        choices=FIELD_CHOICE,
        null=True,
        blank=True,
        help_text=_("The related field of the employees"),
    )
    condition = models.CharField(
        max_length=255, choices=CONDITION_CHOICE, null=True, blank=True
    )
    value = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text=_("The value must be like the data stored in the database"),
    )

    is_fixed = models.BooleanField(
        default=True, help_text=_("To specify, the allowance is fixed or not")
    )
    amount = models.FloatField(
        null=True,
        blank=True,
        validators=[min_zero],
        help_text=_("Fixed amount for this allowance"),
    )
    # If is fixed is false
    based_on = models.CharField(
        max_length=255,
        default="basic_pay",
        choices=based_on_choice,
        null=True,
        blank=True,
        help_text=_(
            "If the allowance is not fixed then specifies how the allowance provided"
        ),
    )
    rate = models.FloatField(
        null=True,
        blank=True,
        validators=[
            rate_validator,
        ],
        help_text=_("The percentage of based on"),
    )
    # If based on attendance
    per_attendance_fixed_amount = models.FloatField(
        null=True,
        blank=True,
        default=0.00,
        validators=[min_zero],
        help_text=_("The attendance fixed amount for one validated attendance"),
    )
    # If based on shift
    shift_id = models.ForeignKey(
        EmployeeShift,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        verbose_name=_("Shift"),
    )
    shift_per_attendance_amount = models.FloatField(
        null=True,
        default=0.00,
        blank=True,
        validators=[min_zero],
        help_text=_("The fixed amount for one validated attendance with that shift"),
    )
    amount_per_one_hr = models.FloatField(
        null=True,
        default=0.00,
        blank=True,
        validators=[min_zero],
        help_text=_(
            "The fixed amount for one hour overtime that are validated \
            and approved the overtime attendance"
        ),
    )
    work_type_id = models.ForeignKey(
        WorkType,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        verbose_name=_("Work Type"),
    )
    work_type_per_attendance_amount = models.FloatField(
        null=True,
        default=0.00,
        blank=True,
        validators=[min_zero],
        help_text=_(
            "The fixed amount for one validated attendance with that work type"
        ),
    )
    # for apply only
    has_max_limit = models.BooleanField(
        default=False,
        verbose_name=_("Has max limit for allowance"),
        help_text=_("Limit the allowance amount"),
    )
    maximum_amount = models.FloatField(
        null=True,
        blank=True,
        validators=[min_zero],
        help_text=_("The maximum amount for the allowance"),
    )
    maximum_unit = models.CharField(
        max_length=20,
        null=True,
        default="month_working_days",
        choices=[
            (
                "month_working_days",
                _("For working days on month"),
            ),
            # ("monthly_working_days", "For working days on month"),
        ],
        help_text="The maximum amount for ?",
    )
    if_choice = models.CharField(
        max_length=10,
        choices=if_condition_choice,
        default="basic_pay",
        help_text=_("The pay head for the if condition"),
    )
    if_condition = models.CharField(
        max_length=10,
        choices=IF_CONDITION_CHOICE,
        default="gt",
        help_text=_("Apply for those, if the pay-head conditions satisfy"),
    )
    if_amount = models.FloatField(
        default=0.00, help_text=_("The amount of the pay-head")
    )
    company_id = models.ForeignKey(
        Company, null=True, editable=False, on_delete=models.PROTECT
    )
    only_show_under_employee = models.BooleanField(default=False, editable=False)
    is_loan = models.BooleanField(default=False, editable=False)
    objects = HorillaCompanyManager()
    other_conditions = models.ManyToManyField(
        MultipleCondition, blank=True, editable=False
    )

    class Meta:
        """
        Meta class for additional options
        """

        unique_together = [
            "title",
            "is_taxable",
            "is_condition_based",
            "field",
            "condition",
            "value",
            "is_fixed",
            "amount",
            "based_on",
            "rate",
            "per_attendance_fixed_amount",
            "shift_id",
            "shift_per_attendance_amount",
            "amount_per_one_hr",
            "work_type_id",
            "work_type_per_attendance_amount",
        ]
        verbose_name = _("Allowance")

    def reset_based_on(self):
        """Reset the this fields when is_fixed attribute is true"""
        attributes_to_reset = [
            "based_on",
            "rate",
            "per_attendance_fixed_amount",
            "shift_id",
            "shift_per_attendance_amount",
            "amount_per_one_hr",
            "work_type_id",
            "work_type_per_attendance_amount",
            "maximum_amount",
        ]
        for attribute in attributes_to_reset:
            setattr(self, attribute, None)
        self.has_max_limit = False

    def clean(self):
        super().clean()
        self.clean_fixed_attributes()
        if not self.is_condition_based:
            self.field = None
            self.condition = None
            self.value = None
        if self.is_condition_based:
            if not self.field or not self.value or not self.condition:
                raise ValidationError(
                    _(
                        "If condition based, all fields (field, value, condition) must be filled."
                    )
                )
        if self.based_on == "attendance" and not self.per_attendance_fixed_amount:
            raise ValidationError(
                {
                    "based_on": _(
                        "If based on is attendance, \
                        then per attendance fixed amount must be filled."
                    )
                }
            )
        if self.based_on == "shift_id" and not self.shift_id:
            raise ValidationError(_("If based on is shift, then shift must be filled."))
        if self.based_on == "work_type_id" and not self.work_type_id:
            raise ValidationError(
                _("If based on is work type, then work type must be filled.")
            )

        if self.is_fixed and self.amount < 0:
            raise ValidationError({"amount": _("Amount should be greater than zero.")})

        if self.has_max_limit and self.maximum_amount is None:
            raise ValidationError({"maximum_amount": _("This field is required")})

        if not self.has_max_limit:
            self.maximum_amount = None

    def clean_fixed_attributes(self):
        """Clean the amount field and trigger the reset_based_on function based on the condition"""
        if not self.is_fixed:
            self.amount = None
        if self.is_fixed:
            if self.amount is None:
                raise ValidationError({"amount": _("This field is required")})
            self.reset_based_on()

    def __str__(self) -> str:
        return str(self.title)

    def save(self):
        super().save()
        if (
            not self.include_active_employees
            and not self.specific_employees.first()
            and not self.is_condition_based
        ):
            self.include_active_employees = True
            super().save()


class Deduction(models.Model):
    """
    Deduction model
    """

    if_condition_choice = [
        ("basic_pay", _("Basic Pay")),
        ("gross_pay", _("Gross Pay")),
    ]

    based_on_choice = [
        ("basic_pay", _("Basic Pay")),
        ("gross_pay", _("Gross Pay")),
        ("taxable_gross_pay", _("Taxable Gross Pay")),
        ("net_pay", _("Net Pay")),
    ]

    exceed_choice = [
        ("ignore", _("Exclude the deduction")),
        ("max_amount", _("Provide max amount")),
    ]

    title = models.CharField(max_length=255, help_text=_("Title of the deduction"))
    one_time_date = models.DateField(
        null=True,
        blank=True,
        help_text=_(
            "The one-time deduction in which the deduction will apply to the payslips \
            if the date between the payslip period"
        ),
    )
    include_active_employees = models.BooleanField(
        default=False,
        verbose_name=_("Include all active employees"),
        help_text=_("Target deduction to all active employees in the company"),
    )
    specific_employees = models.ManyToManyField(
        Employee,
        verbose_name=_("Employees Specific"),
        related_name="deduction_specific",
        help_text=_("Target deduction to the specific employees"),
        blank=True,
    )
    exclude_employees = models.ManyToManyField(
        Employee,
        verbose_name=_("Exclude Employees"),
        related_name="deduction_exclude",
        blank=True,
        help_text=_(
            "To ignore the deduction to the employees when target them by all employees \
            or through condition-based"
        ),
    )

    is_tax = models.BooleanField(
        default=False,
        help_text=_("To specify the deduction is tax or normal deduction"),
    )

    is_pretax = models.BooleanField(
        default=True,
        help_text=_(
            "To find taxable gross, \
            taxable_gross = (basic_pay + taxable_deduction)-pre_tax_deductions "
        ),
    )

    is_condition_based = models.BooleanField(
        default=False,
        help_text=_(
            "This field is used to target deduction \
        to the specific employees when the condition satisfies with the employee's information"
        ),
    )
    # If condition based then must fill field, value, and condition,
    field = models.CharField(
        max_length=255,
        choices=FIELD_CHOICE,
        null=True,
        blank=True,
        help_text=_("The related field of the employees"),
    )
    condition = models.CharField(
        max_length=255, choices=CONDITION_CHOICE, null=True, blank=True
    )
    value = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text=_("The value must be like the data stored in the database"),
    )
    update_compensation = models.CharField(
        null=True,
        blank=True,
        max_length=10,
        choices=[
            (
                "basic_pay",
                _("Basic pay"),
            ),
            ("gross_pay", _("Gross Pay")),
            ("net_pay", _("Net Pay")),
        ],
        help_text=_(
            "Update compensation is used to update \
                   pay-head before any other deduction calculation starts"
        ),
    )
    is_fixed = models.BooleanField(
        default=True,
        help_text=_("To specify, the deduction is fixed or not"),
    )
    # If fixed amount then fill amount
    amount = models.FloatField(
        null=True,
        blank=True,
        validators=[min_zero],
        help_text=_("Fixed amount for this deduction"),
    )
    based_on = models.CharField(
        max_length=255,
        choices=based_on_choice,
        null=True,
        blank=True,
        help_text=_(
            "If the deduction is not fixed then specifies how the deduction provided"
        ),
    )
    rate = models.FloatField(
        null=True,
        blank=True,
        default=0.00,
        validators=[
            rate_validator,
        ],
        verbose_name=_("Employee rate"),
        help_text=_("The percentage of based on"),
    )

    employer_rate = models.FloatField(
        default=0.00,
        validators=[
            rate_validator,
        ],
    )
    has_max_limit = models.BooleanField(
        default=False,
        verbose_name=_("Has max limit for deduction"),
        help_text=_("Limit the deduction"),
    )
    maximum_amount = models.FloatField(
        null=True,
        blank=True,
        validators=[min_zero],
        help_text=_("The maximum amount for the deduction"),
    )

    maximum_unit = models.CharField(
        max_length=20,
        null=True,
        default="month_working_days",
        choices=[
            ("month_working_days", _("For working days on month")),
            # ("monthly_working_days", "For working days on month"),
        ],
        help_text=_("The maximum amount for ?"),
    )
    if_choice = models.CharField(
        max_length=10,
        choices=if_condition_choice,
        default="basic_pay",
        help_text=_("The pay head for the if condition"),
    )
    if_condition = models.CharField(
        max_length=10,
        choices=IF_CONDITION_CHOICE,
        default="gt",
        help_text=_("Apply for those, if the pay-head conditions satisfy"),
    )
    if_amount = models.FloatField(
        default=0.00, help_text=_("The amount of the pay-head")
    )
    company_id = models.ForeignKey(
        Company, null=True, editable=False, on_delete=models.PROTECT
    )
    only_show_under_employee = models.BooleanField(default=False, editable=False)
    objects = HorillaCompanyManager()

    is_installment = models.BooleanField(default=False, editable=False)
    other_conditions = models.ManyToManyField(
        MultipleCondition, blank=True, editable=False
    )

    def installment_payslip(self):
        payslip = Payslip.objects.filter(installment_ids=self).first()
        return payslip

    def clean(self):
        super().clean()

        if self.is_tax:
            self.is_pretax = False
        if self.is_pretax and self.based_on in ["taxable_gross_pay"]:
            raise ValidationError(
                {
                    "based_on": _(
                        " Don't choose taxable gross pay when pretax is enabled."
                    )
                }
            )
        if self.is_pretax and self.based_on in ["net_pay"]:
            raise ValidationError(
                {"based_on": _(" Don't choose net pay when pretax is enabled.")}
            )
        if self.is_tax and self.based_on in ["net_pay"]:
            raise ValidationError(
                {"based_on": _(" Don't choose net pay when the tax is enabled.")}
            )
        if not self.is_fixed:
            self.amount = None
        else:
            self.based_on = None
            self.rate = None
        self.clean_condition_based_on()
        if self.has_max_limit:
            if self.maximum_amount is None:
                raise ValidationError({"maximum_amount": _("This fields required")})

        if self.is_condition_based:
            if not self.field or not self.value or not self.condition:
                raise ValidationError(
                    {
                        "is_condition_based": _(
                            "If condition based, all fields \
                            (field, value, condition) must be filled."
                        )
                    }
                )
        if self.update_compensation is None:
            if self.is_fixed:
                if self.amount is None:
                    raise ValidationError({"amount": _("This field is required")})

    def clean_condition_based_on(self):
        """
        Clean the field, condition, and value attributes when not condition-based.
        """
        if not self.is_condition_based:
            self.field = None
            self.condition = None
            self.value = None

    def __str__(self) -> str:
        return str(self.title)

    def save(self):
        super().save()
        if (
            not self.include_active_employees
            and not self.specific_employees.first()
            and not self.is_condition_based
        ):
            self.include_active_employees = True
            super().save()


class Payslip(models.Model):
    """
    Payslip model
    """

    status_choices = [
        ("draft", _("Draft")),
        ("review_ongoing", _("Review Ongoing")),
        ("confirmed", _("Confirmed")),
        ("paid", _("Paid")),
    ]
    group_name = models.CharField(max_length=50, null=True, blank=True)
    reference = models.CharField(max_length=255, unique=False)
    employee_id = models.ForeignKey(
        Employee, on_delete=models.PROTECT, verbose_name=_("Employee")
    )
    start_date = models.DateField()
    end_date = models.DateField()
    pay_head_data = models.JSONField()
    contract_wage = models.FloatField(null=True, default=0)
    basic_pay = models.FloatField(null=True, default=0)
    gross_pay = models.FloatField(null=True, default=0)
    deduction = models.FloatField(null=True, default=0)
    net_pay = models.FloatField(null=True, default=0)
    status = models.CharField(
        max_length=20, null=True, default="draft", choices=status_choices
    )
    sent_to_employee = models.BooleanField(null=True, default=False)
    objects = HorillaCompanyManager("employee_id__employee_work_info__company_id")
    installment_ids = models.ManyToManyField(Deduction, editable=False)

    def __str__(self) -> str:
        return f"Payslip for {self.employee_id} - Period: {self.start_date} to {self.end_date}"

    def clean(self):
        super().clean()
        today = date.today()
        if self.end_date < self.start_date:
            raise ValidationError(
                {
                    "end_date": _(
                        "The end date must be greater than or equal to the start date"
                    )
                }
            )
        if self.end_date > today:
            raise ValidationError(_("The end date cannot be in the future."))
        if self.start_date > today:
            raise ValidationError(_("The start date cannot be in the future."))

    def save(self, *args, **kwargs):
        if (
            Payslip.objects.filter(
                employee_id=self.employee_id,
                start_date=self.start_date,
                end_date=self.end_date,
            ).count()
            > 1
        ):
            raise ValidationError(_("Employee ,start and end date must be unique"))

        if not isinstance(self.pay_head_data, (QueryDict, dict)):
            raise ValidationError(_("The data must be in dictionary or querydict type"))

        super().save(*args, **kwargs)

    def get_name(self):
        """
        Method is used to get the full name of the owner
        """
        return self.employee_id.get_full_name()

    def get_company(self):
        """
        Method is used to get the full name of the owner
        """
        return getattr(
            getattr(
                getattr(getattr(self, "employee_id", None), "employee_work_info", None),
                "company_id",
                None,
            ),
            "company",
            None,
        )

    def get_payslip_title(self):
        if self.group_name:
            return self.group_name
        return (
            f"Payslip {self.start_date} to {self.end_date}"
            if self.start_date != self.end_date
            else f"Payslip for {self.start_date}"
        )

    class Meta:
        """
        Meta class for additional options
        """

        ordering = [
            "-end_date",
        ]


class LoanAccount(models.Model):
    """
    This modal is used to store the loan Account details
    """

    loan_type = [
        ("loan", "Loan"),
        ("advanced_salary", "Advanced Salary"),
        ("fine", "Penalty / Fine"),
    ]
    type = models.CharField(default="loan", choices=loan_type, max_length=15)
    title = models.CharField(max_length=20)
    employee_id = models.ForeignKey(
        Employee, on_delete=models.PROTECT, verbose_name=_("Employee")
    )
    loan_amount = models.FloatField(default=0)
    provided_date = models.DateField()
    allowance_id = models.ForeignKey(
        Allowance, on_delete=models.SET_NULL, editable=False, null=True
    )
    description = models.TextField(null=True)
    deduction_ids = models.ManyToManyField(Deduction, editable=False)
    is_fixed = models.BooleanField(default=True, editable=False)
    rate = models.FloatField(default=0, editable=False)
    installments = models.IntegerField(verbose_name=_("Total installments"))
    installment_start_date = models.DateField(
        help_text="From the start date deduction will apply"
    )
    apply_on = models.CharField(default="end_of_month", max_length=10, editable=False)
    settled = models.BooleanField(default=False)
    asset_id = models.ForeignKey(
        Asset, on_delete=models.PROTECT, null=True, editable=False
    )
    objects = HorillaCompanyManager("employee_id__employee_work_info__company_id")

    def get_installments(self):
        loan_amount = self.loan_amount
        total_installments = self.installments
        installment_amount = loan_amount / total_installments
        installment_start_date = self.installment_start_date

        installment_schedule = {}

        installment_date = installment_start_date
        installment_date_copy = installment_start_date
        installment_schedule = {}
        for _ in range(total_installments):
            installment_schedule[str(installment_date)] = installment_amount
            month = installment_date.month + 1
            year = installment_date.year
            if month > 12:
                month = 1
                year = year + 1
            day = installment_date_copy.day
            total_days_in_month = calendar.monthrange(year, month)[1]
            day = min(day, total_days_in_month)
            installment_date = date(day=day, month=month, year=year)

        return installment_schedule

    def delete(self, *args, **kwargs):
        self.deduction_ids.all().delete()
        if self.allowance_id is not None:
            self.allowance_id.delete()
        if not Payslip.objects.filter(
            installment_ids__in=list(self.deduction_ids.values_list("id", flat=True))
        ).exists():
            super().delete(*args, **kwargs)
        return

    def installment_ratio(self):
        total_installments = self.installments
        installment_paid = Payslip.objects.filter(
            installment_ids__in=self.deduction_ids.all()
        ).count()
        if not installment_paid:
            return 0
        return (installment_paid / total_installments) * 100


@receiver(post_save, sender=LoanAccount)
def create_installments(sender, instance, created, **kwargs):
    """
    Post save metod for loan account
    """
    installments = []
    if created and instance.asset_id is None and instance.type != "fine":
        loan = Allowance()
        loan.amount = instance.loan_amount
        loan.title = instance.title
        loan.include_active_employees = False
        loan.amount = instance.loan_amount
        loan.only_show_under_employee = True
        loan.is_fixed = True
        loan.one_time_date = instance.provided_date
        loan.is_loan = True
        loan.save()
        loan.include_active_employees = False
        loan.specific_employees.add(instance.employee_id)
        loan.save()
        instance.allowance_id = loan
        # Here create the instance...
        super(LoanAccount, instance).save()
    else:
        deductions = instance.deduction_ids.values_list("id", flat=True)
        # Re create deduction only when existing installment not exists in payslip
        if not Payslip.objects.filter(installment_ids__in=deductions).exists():
            Deduction.objects.filter(id__in=deductions).delete()

            # Installment deductions
            for (
                installment_date,
                installment_amount,
            ) in instance.get_installments().items():
                installment = Deduction()
                installment.title = instance.title
                installment.include_active_employees = False
                installment.amount = installment_amount
                installment.is_fixed = True
                installment.one_time_date = installment_date
                installment.only_show_under_employee = True
                installment.is_installment = True
                installment.save()
                installment.include_active_employees = False
                installment.specific_employees.add(instance.employee_id)
                installment.save()
                installments.append(installment)
            instance.deduction_ids.set(installments)


class ReimbursementMultipleAttachment(models.Model):
    """
    ReimbursementMultipleAttachement Model
    """

    attachment = models.FileField(upload_to="payroll/reimbursements")


class Reimbursement(models.Model):
    """
    Reimbursement Model
    """

    reimbursement_types = [
        ("reimbursement", "Reimbursement"),
        ("leave_encashment", "Leave Encashment"),
    ]
    status_types = [
        ("requested", "Requested"),
        ("approved", "Approved"),
        ("canceled", "Canceled"),
    ]
    title = models.CharField(max_length=50)
    type = models.CharField(
        choices=reimbursement_types, max_length=16, default="reimbursement"
    )
    employee_id = models.ForeignKey(
        Employee, on_delete=models.PROTECT, verbose_name="Employee"
    )
    allowance_on = models.DateField()
    attachment = models.FileField(upload_to="payroll/reimbursements", null=True)
    other_attachments = models.ManyToManyField(
        ReimbursementMultipleAttachment, blank=True, editable=False
    )
    leave_type_id = models.ForeignKey(
        LeaveType, on_delete=models.PROTECT, null=True, verbose_name="Leave type"
    )
    ad_to_encash = models.FloatField(
        default=0, help_text="Available Days to encash", verbose_name="Available days"
    )
    cfd_to_encash = models.FloatField(
        default=0,
        help_text="Carry Forward Days to encash",
        verbose_name="Carry forward days",
    )
    amount = models.FloatField(default=0)
    status = models.CharField(
        max_length=10, choices=status_types, default="requested", editable=False
    )
    approved_by = models.ForeignKey(
        Employee,
        on_delete=models.SET_NULL,
        null=True,
        related_name="approved_by",
        editable=False,
    )
    description = models.TextField(null=True)
    allowance_id = models.ForeignKey(
        Allowance, on_delete=models.SET_NULL, null=True, editable=False
    )
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True, editable=False)
    objects = HorillaCompanyManager("employee_id__employee_work_info__company_id")

    def save(self, *args, **kwargs) -> None:
        request = getattr(thread_local_middleware._thread_locals, "request", None)

        # Setting the created use if the used dont have the permission
        has_perm = request.user.has_perm("payroll.add_reimbursement")
        if not has_perm:
            self.employee_id = request.user.employee_get
        if self.type == "reimbursement" and self.attachment is None:
            raise ValidationError({"attachment": "This field is required"})
        elif self.type == "leave_encashment" and self.leave_type_id is None:
            raise ValidationError({"leave_type_id": "This field is required"})
        self.cfd_to_encash = max((round(self.cfd_to_encash * 2) / 2), 0)
        self.ad_to_encash = max((round(self.ad_to_encash * 2) / 2), 0)
        assigned_leave = self.leave_type_id.employee_available_leave.filter(
            employee_id=self.employee_id
        ).first()
        if self.status != "approved" or self.allowance_id is None:
            super().save(*args, **kwargs)
            if self.status == "approved" and self.allowance_id is None:
                if self.type == "reimbursement":
                    proceed = True
                else:
                    proceed = False
                    if assigned_leave:
                        available_days = assigned_leave.available_days
                        carryforward_days = assigned_leave.carryforward_days
                        if (
                            available_days >= self.ad_to_encash
                            and carryforward_days >= self.cfd_to_encash
                        ):
                            proceed = True
                            assigned_leave.available_days = (
                                available_days - self.ad_to_encash
                            )
                            assigned_leave.carryforward_days = (
                                carryforward_days - self.cfd_to_encash
                            )
                            assigned_leave.save()
                        else:
                            request = getattr(
                                thread_local_middleware._thread_locals, "request", None
                            )
                            if request:
                                messages.info(
                                    request,
                                    "The employee don't have that much leaves to encash in CFD / Available days",
                                )

                    # if self.ad

                if proceed:
                    reimbursement = Allowance()
                    reimbursement.one_time_date = self.allowance_on
                    reimbursement.title = self.title
                    reimbursement.only_show_under_employee = True
                    reimbursement.include_active_employees = False
                    reimbursement.amount = self.amount
                    reimbursement.save()
                    reimbursement.include_active_employees = False
                    reimbursement.specific_employees.add(self.employee_id)
                    reimbursement.save()
                    self.allowance_id = reimbursement
                    if request:
                        self.approved_by = request.user.employee_get
                else:
                    self.status = "requested"
                super().save(*args, **kwargs)
            elif self.status == "canceled" and self.allowance_id is not None:
                cfd_days = self.cfd_to_encash
                available_days = self.ad_to_encash
                if assigned_leave:
                    assigned_leave.available_days = (
                        assigned_leave.available_days + available_days
                    )
                    assigned_leave.carryforward_days = (
                        assigned_leave.carryforward_days + cfd_days
                    )
                    assigned_leave.save()
                self.allowance_id.delete()

    def delete(self, *args, **kwargs):
        if self.allowance_id:
            self.allowance_id.delete()
        return super().delete(*args, **kwargs)


class ReimbursementrequestComment(models.Model):
    """
    ReimbursementrequestComment Model
    """

    request_id = models.ForeignKey(Reimbursement, on_delete=models.CASCADE)
    employee_id = models.ForeignKey(Employee, on_delete=models.CASCADE)
    comment = models.TextField(null=True, verbose_name=_("Comment"))
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Created At"),
        null=True,
    )

    def __str__(self) -> str:
        return f"{self.comment}"
