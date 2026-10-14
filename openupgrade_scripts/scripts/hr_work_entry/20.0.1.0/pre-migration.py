# Copyright 2026 Don Kendall
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from openupgradelib import openupgrade

# 20.0 prefixes the country-neutral work entry types with "generic_" to tell
# them apart from the localisation ones that share a code.
_renamed_xmlids = [
    (f"hr_work_entry.{old}", f"hr_work_entry.generic_{old}")
    for old in (
        "work_entry_type_attendance",
        "work_entry_type_overtime",
        "hr_work_entry_type_out_of_contract",
        "work_entry_type_leave",
        "work_entry_type_compensatory",
        "work_entry_type_home_working",
        "work_entry_type_unpaid_leave",
        "work_entry_type_sick_leave",
        "work_entry_type_legal_leave",
    )
]


@openupgrade.migrate()
def migrate(env, version):
    # Without this the data load inserts a second country-less record for each
    # code and _check_code_unicity rejects it: "Time type ... of code LEAVE100,
    # with no country assigned, already exists".
    openupgrade.rename_xmlids(env.cr, _renamed_xmlids)
