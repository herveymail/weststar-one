from apps.core.registry import Module, register

from .models import Employee, TimeclockEntry, TimeOffRequest

register(Module("employees", Employee, "H/R Admin", "Employee", "hr", "Employees. SSN and bank details are encrypted and every reveal is logged.",
                ["name", "title", "office", "status", "hire_date"], ["name", "title"], "status", primary_action="Add employee", hidden=True))
register(Module("pto", TimeOffRequest, "Time off", "Time-off request", "hr", "Time-off requests. H/R approves.",
                ["user", "kind", "starts_on", "ends_on", "hours", "status"], ["reason"], "status", owner_scoped=True, owner_initial_status="Pending",
                primary_action="Request time off", hidden=True, ordering=["-starts_on", "-id"]))
register(Module("timeclock", TimeclockEntry, "Timeclock", "Time entry", "hr", "Clock-in and clock-out records.",
                ["user", "clock_in", "clock_out", "status"], [], "status", owner_scoped=True, owner_initial_status="Open", hidden=True, ordering=["-clock_in", "-id"]))
