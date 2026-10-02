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


@openupgrade.migrate()
def migrate(env, version):
    openupgrade.load_data(env, "hr", "20.0.1.1/noupdate_changes.xml")
    _report_lost_employee_types(env)
    _carry_the_timezone_the_relation_stopped_deriving(env)
    openupgrade.delete_record_translations(
        env.cr,
        "hr",
        ["contract_type_seasonal"],
        ["name"],
    )
