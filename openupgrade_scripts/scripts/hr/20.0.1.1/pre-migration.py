# Copyright 2026 Don Kendall
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from openupgradelib import openupgrade

_renamed_models = [("hr.contract.type", "hr.employee.type")]
_renamed_tables = [("hr_contract_type", "hr_employee_type")]


@openupgrade.migrate()
def migrate(env, version):
    # hr.contract.type became hr.employee.type. The existing xml_ids still name
    # the old model, so loading hr's data raises KeyError on a model the
    # registry no longer has. apriori.renamed_models documents the change; this
    # is what actually performs it.
    openupgrade.rename_models(env.cr, _renamed_models)
    openupgrade.rename_tables(env.cr, _renamed_tables)
