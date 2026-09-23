# Copyright 2026 Don Kendall
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from openupgradelib import openupgrade

# account.tax.is_withholding_tax_on_payment becomes is_withholding_tax.
#
# 20.0 broadened the wording rather than the meaning: 19.0 labelled it "Withhold
# On Payment" and helped "will not affect your accounts until the registration
# of payments", 20.0 labels it "Withhold" and helps "will not affect the amount
# due until applied via the Pay button". A tax that withheld on payment is a
# withholding tax, so the flag carries. Left undone, 188 taxes on the seed stop
# being withholding taxes at all, which is a silent change to what they compute.
_renamed_fields = [
    (
        "account.tax",
        "account_tax",
        "is_withholding_tax_on_payment",
        "is_withholding_tax",
    ),
]


@openupgrade.migrate()
def migrate(env, version):
    openupgrade.rename_fields(env, _renamed_fields)
