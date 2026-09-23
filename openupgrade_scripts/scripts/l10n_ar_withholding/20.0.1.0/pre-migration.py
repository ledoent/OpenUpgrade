# Copyright 2026 Don Kendall
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from openupgradelib import openupgrade

# account.tax.l10n_ar_tax_type is spelled l10n_ar_withholding_tax_type in 20.0.
# The selection is unchanged -- earnings, earnings_scale, iibb_untaxed and the
# rest -- so this is a rename and the values carry straight over. 178 taxes on
# the seed would otherwise come out with no withholding type at all.
#
# The analysis also pairs l10n_ar_withholding_payment_type with the same new
# field, because both old fields are selections on account.tax. That one is the
# payment moment, not the tax type, and is left alone.
_renamed_fields = [
    (
        "account.tax",
        "account_tax",
        "l10n_ar_tax_type",
        "l10n_ar_withholding_tax_type",
    ),
]


@openupgrade.migrate()
def migrate(env, version):
    openupgrade.rename_fields(env, _renamed_fields)
