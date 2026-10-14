# Copyright 2026 Don Kendall
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from openupgradelib import openupgrade

_renamed_models = [
    ("l10n_tr_nilvera_einvoice_extended.tax.office", "l10n_tr.tax.office"),
]
_renamed_tables = [
    ("l10n_tr_nilvera_einvoice_extended_tax_office", "l10n_tr_tax_office"),
]


@openupgrade.migrate()
def migrate(env, version):
    # The tax office list moved out of l10n_tr_nilvera_einvoice_extended into
    # l10n_tr. res.partner.l10n_tr_tax_office_id comes along, and its foreign
    # key is rebuilt against l10n_tr_tax_office -- which fails on the existing
    # partner rows unless the table comes with it.
    openupgrade.rename_models(env.cr, _renamed_models)
    openupgrade.rename_tables(env.cr, _renamed_tables)
