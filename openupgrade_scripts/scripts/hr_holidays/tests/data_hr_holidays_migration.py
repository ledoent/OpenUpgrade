env = locals().get("env")

# hr.leave.type is folded into hr.work.entry.type in 20.0. Both models exist
# here in 19.0, which is what makes it a merge rather than a rename, and the
# three cases below are the three the merge has to tell apart.
#
# The fixtures are filed under a module that does not exist. _process_end
# removes data rows belonging to modules it has just loaded, so an id claiming
# to be hr_holidays' would be deleted at the end of the run.
wet_model = env["hr.work.entry.type"]
leave_model = env["hr.leave.type"]

# A work entry type of its own: this pairing is unambiguous and must survive.
wet_solo = wet_model.create(
    {
        "name": "ou19-wet-solo",
        "code": "OU19SOLO",
    }
)

# One work entry type, two leave types. 20.0 has a single record where 19.0
# had two, so they cannot both keep it: the older one keeps the link and the
# younger gets a record of its own.
wet_shared = wet_model.create(
    {
        "name": "ou19-wet-shared",
        "code": "OU19SHARED",
    }
)

# 1. Unique link. Its leave settings have to land on the work entry type,
#    which carries none of them yet.
leave_solo = leave_model.create(
    {
        "name": "ou19-leave-solo",
        "work_entry_type_id": wet_solo.id,
        "time_type": "leave",
        "request_unit": "day",
        "requires_allocation": True,
        "allocation_validation_type": "hr",
        "support_document": True,
    }
)

# 2. Shared link, created first, so this is the one that keeps it.
leave_shared_first = leave_model.create(
    {
        "name": "ou19-leave-shared-first",
        "work_entry_type_id": wet_shared.id,
        "time_type": "leave",
        "request_unit": "hour",
    }
)

# 3. Shared link, created second: gets its own record, and takes the paired
#    work entry type's payroll code because that is the code its time off was
#    actually paid under.
leave_shared_second = leave_model.create(
    {
        "name": "ou19-leave-shared-second",
        "work_entry_type_id": wet_shared.id,
        "time_type": "leave",
        "request_unit": "half_day",
    }
)

# 4. No link at all. Nothing to take a code from, so it gets a placeholder,
#    and time_type 'other' must map to count_as 'working_time' rather than the
#    'absence' every other case produces.
leave_unlinked = leave_model.create(
    {
        "name": "ou19-leave-unlinked",
        "time_type": "other",
        "request_unit": "hour",
    }
)

for record, name in (
    (leave_solo, "ou19_leave_solo"),
    (leave_shared_first, "ou19_leave_shared_first"),
    (leave_shared_second, "ou19_leave_shared_second"),
    (leave_unlinked, "ou19_leave_unlinked"),
):
    env["ir.model.data"].create(
        {
            "module": "__ou19__",
            "name": name,
            "model": "hr.leave.type",
            "res_id": record.id,
        }
    )

# An allocation against the unlinked type, so the reference re-pointing is
# exercised on a type whose stand-in did not exist before the migration ran.
# Allocations are used rather than leaves: a leave needs an employee with a
# calendar and a date range that validates, and none of that is what is under
# test here.
employee = env["hr.employee"].search([], limit=1)
env["hr.leave.allocation"].create(
    {
        "name": "ou19-allocation",
        "holiday_status_id": leave_unlinked.id,
        "employee_id": employee.id,
        "number_of_days": 1,
    }
)

env.cr.commit()
