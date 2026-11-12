# Repoint the multi-company ir.rule to the renamed Coretax document model.
from openupgradelib import openupgrade


@openupgrade.migrate()
def migrate(env, version):
    openupgrade.load_data(
        env,
        "l10n_id_efaktur_coretax",
        "19.0.1.0/noupdate_changes.xml",
    )
