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
    related='employee_id.tz')` on hr.version (hr_version.py:153) and nothing was
    stored there: hr.employee.tz is resource.mixin's related to
    resource_id.tz, so the value lived in resource_resource.tz. 20.0 makes
    hr_version.tz stored and REQUIRED with `default=lambda self:
    self.env.context.get('tz') or self.env.user.tz or 'UTC'`
    (hr_version.py:162), and turns hr.employee.tz into
    related="version_id.tz" (hr_employee.py:309) -- the employee now reads from
    the version rather than the other way round.

    So the upgrade had to materialise the value and instead took the default.
    Measured on the sanitised prod copy 2026-10-02: both versions came out
    'UTC' while the resources behind their employees hold 'America/New_York'.

    Nothing re-derives it afterwards -- _get_tz() returns `self.tz or ...`
    first (hr_version.py:715-717) -- so the wrong zone reaches
    _get_resources_per_tz and every working-hours and attendance calculation
    downstream, a four or five hour shift that no error reports.

    Only rows still sitting on the bare 'UTC' default are touched, and only
    where the resource actually names a zone, so a deliberate UTC that came
    from a UTC resource is written back identically and a version whose
    resource says nothing is left alone and reported.
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
          AND v.tz = 'UTC'
          AND r.tz != 'UTC'
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
            "resource, which 19.0 read through a related field that 20.0 "
            "stores instead; they would otherwise have kept the 'UTC' default",
            carried,
        )
    env.cr.execute(
        """
        SELECT count(*)
        FROM hr_version v
        JOIN hr_employee e ON e.id = v.employee_id
        LEFT JOIN resource_resource r ON r.id = e.resource_id
        WHERE v.tz = 'UTC' AND (r.tz IS NULL OR r.tz = '')
        """
    )
    unsourced = env.cr.fetchone()[0]
    if unsourced:
        openupgrade.message(
            env.cr,
            "hr",
            False,
            False,
            "hr.version: %s version(s) are on the 'UTC' default and their "
            "resource names no timezone, so there was nothing to carry; check "
            "them if the company does not actually run on UTC",
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
