# Copyright 2026 Don Kendall
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from openupgradelib import openupgrade

_legacy_employee_type = openupgrade.get_legacy_name("employee_type")


def _report_lost_employee_types(env):
    """Say which versions classified the person in a way 20.0 cannot hold.

    19.0 had two fields: contract_type_id, which pre-migration renames to
    employee_type_id because that is what 20.0 kept, and employee_type, a
    required selection of Employee, Worker, Student, Trainee, Contractor and
    Freelancer with Employee as its default.

    The selection is not mapped onto an hr.employee.type. They classify
    different things -- what the person is against what the contract is -- and
    the records to map onto are 19.0's own contract types, so writing Student
    into a version that never had a contract type would invent configuration
    rather than carry it. Only the values someone chose are worth a line: the
    default says nothing, and every version on the seed is on it.
    """
    if not openupgrade.column_exists(env.cr, "hr_version", _legacy_employee_type):
        return
    env.cr.execute(
        f"""
        SELECT {_legacy_employee_type}, count(*)
        FROM hr_version
        WHERE {_legacy_employee_type} IS NOT NULL
          AND {_legacy_employee_type} != 'employee'
        GROUP BY 1 ORDER BY 2 DESC
        """
    )
    for value, count in env.cr.fetchall():
        openupgrade.message(
            env.cr,
            "hr",
            False,
            False,
            "%s employee versions were of type '%s', which 20.0 has no field "
            "for; employee_type_id now describes the contract instead",
            count,
            value,
        )


def _carry_the_timezone_the_relation_stopped_deriving(env):
    """Fill hr_version.tz from the resource, which is where 19.0 kept it.

    The relation inverted. 19.0 declared `tz = fields.Selection(
    related='employee_id.tz')` on hr.version with no store, so there was no
    column: hr.employee.tz is resource.mixin's related to resource_id.tz and the
    value lived in resource_resource.tz. 20.0 makes hr_version.tz a stored,
    REQUIRED column and turns hr.employee.tz into related="version_id.tz"
    (hr_employee.py:309) -- the employee now reads from the version.

    Nothing materialised the value, so the new column took its default::

        default=lambda self: (self.env.context.get('tz')
                              or self.env.user.tz or 'UTC')   # hr_version.py:154

    which is the timezone of **whoever ran the upgrade**, written to every
    employee. Measured: the sanitised prod copy came out 'UTC' on both versions
    (admin has no tz) against resources holding 'America/New_York'; the 19.0 seed
    came out 'Europe/Brussels' on all 31. Same defect, and the difference is only
    which account started the migration.

    Nothing re-derives it afterwards -- _get_tz() returns `self.tz` first
    (hr_version.py:715-717) -- so the wrong zone reaches every working-hours and
    attendance calculation downstream, with no error.

    The write is unconditional wherever the resource names a zone, because no
    19.0 value exists to protect: a non-stored related field left no column, so
    every tz now in the table was invented seconds ago by that default. An
    earlier version of this guarded on `tz = 'UTC'` and silently did nothing on
    any database whose admin had a timezone set.
    """
    openupgrade.logged_query(
        env.cr,
        """
        UPDATE hr_version v
        SET tz = r.tz
        FROM hr_employee e, resource_resource r
        WHERE e.id = v.employee_id
          AND r.id = e.resource_id
          AND r.tz IS NOT NULL AND r.tz != ''
          AND v.tz != r.tz
        """,
    )
    carried = env.cr.rowcount
    if carried:
        openupgrade.message(
            env.cr,
            "hr",
            False,
            False,
            "hr.version: carried the timezone of %s version(s) from their "
            "resource, which 19.0 read through a related field that 20.0 stores "
            "instead; they would otherwise have kept the timezone of the user "
            "who ran the upgrade",
            carried,
        )
    env.cr.execute(
        """
        SELECT count(*)
        FROM hr_version v
        JOIN hr_employee e ON e.id = v.employee_id
        LEFT JOIN resource_resource r ON r.id = e.resource_id
        WHERE r.tz IS NULL OR r.tz = ''
        """
    )
    unsourced = env.cr.fetchone()[0]
    if unsourced:
        openupgrade.message(
            env.cr,
            "hr",
            False,
            False,
            "hr.version: %s version(s) have a resource that names no timezone, "
            "so there was nothing to carry and they keep the timezone of the "
            "user who ran the upgrade; check them",
            unsourced,
        )


def _retype_the_recruiter_from_a_user_to_an_employee(env):
    """hr.job.recruiter_id is the old user_id retyped, not a new field.

    Both are labelled "Recruiter" and carry the same help text word for word;
    only the comodel changed, res.users -> hr.employee. The analysis reports it
    as a DEL and a NEW, so nothing was carried and the 19.0 column is orphaned
    in hr_job.

    The new column is not empty, though, and that is the trap. recruiter_id
    declares `default=lambda self: self.env.user.employee_id`, so adding the
    column stamped every job with the employee record of whoever ran the
    upgrade -- the same shape as hr.version.tz. Guarding on "is it still NULL"
    would therefore do nothing on any database whose admin has an employee, so
    the mapping is written wherever it can be resolved.

    The target must satisfy recruiter_id's check_company=True, so the employee
    is matched within the job's own company; the lowest active employee id wins
    where a user has several. A recruiter with no employee record in that
    company cannot be expressed in 20.0 at all and is reported.

    hr_job holds 0 rows on the prod copy, so the migration test is what
    exercises this.
    """
    if "user_id" in env["hr.job"]._fields:
        # 20.0 would be using the column for something live; leave it alone.
        return
    if not openupgrade.column_exists(env.cr, "hr_job", "user_id"):
        return
    openupgrade.logged_query(
        env.cr,
        """
        UPDATE hr_job j
        SET recruiter_id = m.employee_id
        FROM (
            SELECT DISTINCT ON (j2.id) j2.id AS job_id, e.id AS employee_id
            FROM hr_job j2
            JOIN hr_employee e ON e.user_id = j2.user_id
            WHERE j2.user_id IS NOT NULL
              AND (e.company_id = j2.company_id OR j2.company_id IS NULL)
            ORDER BY j2.id, e.active DESC, e.id
        ) m
        WHERE m.job_id = j.id
          AND j.recruiter_id IS DISTINCT FROM m.employee_id
        """,
    )
    retyped = env.cr.rowcount
    if retyped:
        openupgrade.message(
            env.cr,
            "hr",
            False,
            False,
            "hr.job: resolved the 19.0 recruiter of %s job(s) to an hr.employee; "
            "20.0 retyped the field from res.users and the column had been "
            "stamped with the employee of the user running the upgrade",
            retyped,
        )
    env.cr.execute(
        """
        SELECT count(*)
        FROM hr_job j
        WHERE j.user_id IS NOT NULL
          AND NOT EXISTS (
              SELECT 1 FROM hr_employee e
              WHERE e.user_id = j.user_id
                AND (e.company_id = j.company_id OR j.company_id IS NULL)
          )
        """
    )
    unresolvable = env.cr.fetchone()[0]
    if unresolvable:
        openupgrade.message(
            env.cr,
            "hr",
            False,
            False,
            "hr.job: %s job(s) named a recruiter who has no employee record in "
            "the job's company. 20.0's recruiter_id takes an employee and checks "
            "the company, so the value could not be carried; the user is still in "
            "the legacy hr_job.user_id column",
            unresolvable,
        )


def _build_the_departure_record_the_version_now_reads_through(env):
    """19.0's three departure columns move onto a new hr.employee.departure.

    19.0 stored departure_reason_id, departure_description and departure_date on
    hr_version. 20.0 keeps them on hr.employee.departure and makes hr.version's
    three related through departure_id, so the surviving hr_version columns go
    invisible to the ORM while hr_employee_departure holds no rows.

    WHY THIS IS SQL AND NOT create()

    hr.employee.departure.create() does two things a migration must not. It
    rewrites the employee's contract: `vals['contract_date_end'] =
    departure.departure_date` on the matching version
    (hr_employee_departure.py:124-131), overwriting whatever 19.0 recorded. And
    it leaves apply_date NULL, which arms the daily cron: _cron_apply_departure
    selects `apply_date = False` with a departure_date in the past and calls
    action_register(), which archives the employee AND their res.users
    (hr_employee_departure.py:134-142). Every historical departure carried would
    therefore archive a user account within a day of the upgrade.

    So the rows are inserted directly, with apply_date set to the departure date
    -- these departures were applied years ago, by 19.0's own wizard -- which is
    what tells the cron there is nothing left to do.

    Only versions carrying a departure_date are carried, because 20.0 requires
    both dismissal_date and departure_reason_id and a date cannot be invented
    for a record that is meant to say when somebody left. A version holding a
    reason or a description but no date is reported instead: its values stay in
    the orphaned columns rather than being anchored to a date that never
    existed. A version with no reason takes the first one in the model's order,
    since the column is NOT NULL.

    All three are NULL on both copies, so the migration test is what exercises
    this.
    """
    for column in ("departure_date", "departure_reason_id", "departure_description"):
        if not openupgrade.column_exists(env.cr, "hr_version", column):
            return
    # The first reason in the model's own order. Not
    # _get_default_departure_reason(), which filters by the record's country and
    # is called here with no record to read one from.
    default_reason = env["hr.departure.reason"].search([], limit=1)
    env.cr.execute(
        """
        SELECT id, employee_id, departure_reason_id, departure_description,
               departure_date, contract_date_end
        FROM hr_version
        WHERE departure_date IS NOT NULL
          AND employee_id IS NOT NULL
          AND departure_id IS NULL
          AND (departure_reason_id IS NOT NULL OR %s)
        ORDER BY id
        """,
        (bool(default_reason),),
    )
    rows = env.cr.fetchall()
    for (
        version_id,
        employee_id,
        reason_id,
        description,
        departure_date,
        contract_date_end,
    ) in rows:
        env.cr.execute(
            """
            INSERT INTO hr_employee_departure (
                employee_id, departure_reason_id, departure_description,
                dismissal_date, departure_date, action_date, apply_date,
                last_contract_date_end,
                create_uid, create_date, write_uid, write_date)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 1, now(), 1, now())
            RETURNING id
            """,
            (
                employee_id,
                reason_id or default_reason.id,
                description,
                departure_date,
                departure_date,
                departure_date,
                departure_date,
                contract_date_end,
            ),
        )
        env.cr.execute(
            "UPDATE hr_version SET departure_id = %s WHERE id = %s",
            (env.cr.fetchone()[0], version_id),
        )
    if rows:
        openupgrade.message(
            env.cr,
            "hr",
            False,
            False,
            "hr.version: built %s hr.employee.departure record(s) from the "
            "departure columns 20.0 reads through departure_id, and marked them "
            "already applied so the daily cron does not archive the employees "
            "and their user accounts a second time",
            len(rows),
        )
    env.cr.execute(
        """
        SELECT count(*)
        FROM hr_version
        WHERE departure_date IS NULL
          AND (departure_reason_id IS NOT NULL
               OR (departure_description IS NOT NULL AND departure_description != ''))
        """
    )
    undatable = env.cr.fetchone()[0]
    if undatable:
        openupgrade.message(
            env.cr,
            "hr",
            False,
            False,
            "hr.version: %s version(s) record a departure reason or note but no "
            "departure date. 20.0 requires a date on hr.employee.departure, so "
            "no record was built rather than inventing one; the values remain in "
            "the legacy hr_version columns",
            undatable,
        )


@openupgrade.migrate()
def migrate(env, version):
    openupgrade.load_data(env, "hr", "20.0.1.1/noupdate_changes.xml")
    _report_lost_employee_types(env)
    _carry_the_timezone_the_relation_stopped_deriving(env)
    _retype_the_recruiter_from_a_user_to_an_employee(env)
    _build_the_departure_record_the_version_now_reads_through(env)
    openupgrade.delete_record_translations(
        env.cr,
        "hr",
        ["contract_type_seasonal"],
        ["name"],
    )
