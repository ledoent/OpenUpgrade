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


@openupgrade.migrate()
def migrate(env, version):
    openupgrade.load_data(env, "hr", "20.0.1.1/noupdate_changes.xml")
    _report_lost_employee_types(env)
    openupgrade.delete_record_translations(
        env.cr,
        "hr",
        ["contract_type_seasonal"],
        ["name"],
    )
