from openupgradelib import openupgrade

# Without this column-add the 19.0 account chart_template loader's
# `account.tax.mapped(...)` query references account_tax.l10n_no_standard_code
# before the l10n_no install step would have created the column, crashing
# the migration with UndefinedColumn. See upgrade_analysis.txt — the field
# is NEW in 19.0 and there is no upstream pre-migration script in stock
# OpenUpgrade as of 19.0.2.1.
_added_fields = [
    (
        "l10n_no_standard_code",
        "account.tax",
        "account_tax",
        "char",
        None,
        "l10n_no",
        None,
    ),
]


@openupgrade.migrate()
def migrate(env, version):
    openupgrade.add_fields(env, _added_fields)
