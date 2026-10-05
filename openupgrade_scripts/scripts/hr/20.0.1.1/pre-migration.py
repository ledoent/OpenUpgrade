# Copyright 2026 Don Kendall
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from openupgradelib import openupgrade

_renamed_models = [("hr.contract.type", "hr.employee.type")]
_renamed_tables = [("hr_contract_type", "hr_employee_type")]

# The field that points at it is renamed with it: same type, same
# groups="hr.group_hr_manager", and the comodel is the model above under its new
# name. 20.0 relabels it from "Contract Type" to "Employee Type", which is the
# only reason it does not read as a rename.
_renamed_fields = [
    ("hr.version", "hr_version", "contract_type_id", "employee_type_id"),
    ("hr.job", "hr_job", "contract_type_id", "employee_type_id"),
]


@openupgrade.migrate()
def migrate(env, version):
    # hr.contract.type became hr.employee.type. The existing xml_ids still name
    # the old model, so loading hr's data raises KeyError on a model the
    # registry no longer has. apriori.renamed_models documents the change; this
    # is what actually performs it.
    openupgrade.rename_models(env.cr, _renamed_models)
    openupgrade.rename_tables(env.cr, _renamed_tables)
    openupgrade.rename_fields(env, _renamed_fields)
    # 19.0's employee_type classified the person -- Worker, Student, Trainee,
    # Contractor, Freelancer -- where the field renamed above classifies the
    # contract. 20.0 keeps only the latter, so this one has nowhere to go and is
    # kept for post-migration to report on.
    if openupgrade.column_exists(env.cr, "hr_version", "employee_type"):
        openupgrade.rename_columns(env.cr, {"hr_version": [("employee_type", None)]})
