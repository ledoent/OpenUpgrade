from openupgradelib import openupgrade

_renamed_fields = [
    ("fleet.vehicle", "fleet_vehicle", "first_contract_date", "contract_date_start"),
]


@openupgrade.migrate()
def migrate(env, version):
    openupgrade.rename_fields(env, _renamed_fields)
