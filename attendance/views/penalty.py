"""
attendance/views/penalty.py

This module is used to write late come early out penatly methods
"""
from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.contrib import messages
from attendance.forms import PenaltyAccountForm
from attendance.filters import PenaltyFilter
from attendance.models import AttendanceLateComeEarlyOut, PenaltyAccount
from leave.models import AvailableLeave
from employee.models import Employee
from horilla.decorators import login_required, manager_can_enter


@login_required
@manager_can_enter("leave.change_availableleave")
def cut_available_leave(request, instance_id):
    """
    This method is used to create the penalties
    """
    instance = AttendanceLateComeEarlyOut.objects.get(id=instance_id)
    form = PenaltyAccountForm()
    available = AvailableLeave.objects.filter(employee_id=instance.employee_id)
    if request.method == "POST":
        form = PenaltyAccountForm(request.POST)
        if form.is_valid():
            penalty_instance = form.instance
            penalty = PenaltyAccount()
            # late come early out id
            penalty.late_early_id = instance
            penalty.deduct_from_carry_forward = penalty_instance.deduct_from_carry_forward
            penalty.employee_id = instance.employee_id
            penalty.leave_type_id = penalty_instance.leave_type_id
            penalty.minus_leaves = penalty_instance.minus_leaves
            penalty.penalty_amount = penalty_instance.penalty_amount
            penalty.save()
            messages.success(request, "Penalty/Fine added")
            return HttpResponse("<script>window.location.reload()</script>")
    return render(
        request,
        "attendance/penalty/form.html",
        {"available": available, "form": form, "instance": instance},
    )


@login_required
def view_penalties(request):
    """
    This method is used to filter or view the penalties
    """
    records = PenaltyFilter(request.GET).qs
    return render(request, "attendance/penalty/penalty_view.html", {"records": records})
