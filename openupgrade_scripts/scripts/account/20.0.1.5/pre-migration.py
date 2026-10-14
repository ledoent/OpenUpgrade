# Copyright 2026 Don Kendall
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from openupgradelib import openupgrade

_renamed_xmlids = [
    # the stock valuation report moved from stock_account into account
    (
        "stock_account.action_report_stock_valuation",
        "account.action_report_stock_valuation",
    ),
]


@openupgrade.migrate()
def migrate(env, version):
    # The client action keeps its path, which is unique, so account's copy of
    # the record has to land on the existing row instead of inserting a second
    # one and tripping ir_act_client_path_unique.
    openupgrade.rename_xmlids(env.cr, _renamed_xmlids)
