# Copyright 2026 Don Kendall
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from openupgradelib import openupgrade

# 20.0 replaces the industry list wholesale -- 23 entries become 83 and the
# external ids are renumbered. Matching the two csv files by name, "Real
# Estate" is the only one carried over, and it is the only one that collides:
# crm_iap_lead_industry_name_uniq rejects the new row while the old one is
# still there under its old id. The other 22 are left to the usual removal of
# data records a module no longer declares.
_renamed_xmlids = [
    (
        "crm_iap_mine.crm_iap_mine_industry_114",
        "crm_iap_mine.crm_iap_mine_industry_65",
    ),
]


@openupgrade.migrate()
def migrate(env, version):
    openupgrade.rename_xmlids(env.cr, _renamed_xmlids)
