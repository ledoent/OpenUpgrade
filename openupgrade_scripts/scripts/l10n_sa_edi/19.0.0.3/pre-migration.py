# Copyright 2026 Odoo Community Association (OCA)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from openupgradelib import openupgrade

_renamed_fields = [
    (
        "res.partner",
        "res_partner",
        "l10n_sa_additional_identification_number",
        "l10n_sa_edi_additional_identification_number",
    ),
    (
        "res.partner",
        "res_partner",
        "l10n_sa_additional_identification_scheme",
        "l10n_sa_edi_additional_identification_scheme",
    ),
]


@openupgrade.migrate()
def migrate(env, version):
    openupgrade.rename_fields(env, _renamed_fields)
