# Copyright 2026 Don Kendall
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from openupgradelib import openupgrade

# 20.0 ships these withholding tax tags as records with external ids. In 19.0
# they were created implicitly by the tax template csv, which names tags but
# does not give them ids, so the rows exist with no ir_model_data entry and the
# new records collide on account_account_tag_name_uniq.
_TAGS = [
    ("tag_th_pnd3", "PND3"),
    ("tag_th_income_pnd3", "Income PND3"),
    ("tag_th_pnd53", "PND53"),
    ("tag_th_income_pnd53", "Income PND53"),
]


@openupgrade.migrate()
def migrate(env, version):
    for xmlid, name in _TAGS:
        env.cr.execute(
            """
            SELECT tag.id
            FROM account_account_tag tag
            JOIN res_country country ON country.id = tag.country_id
            WHERE tag.name ->> 'en_US' = %s
              AND tag.applicability = 'taxes'
              AND country.code = 'TH'
              AND NOT EXISTS (
                  SELECT 1 FROM ir_model_data imd
                  WHERE imd.model = 'account.account.tag' AND imd.res_id = tag.id
              )
            """,
            (name,),
        )
        row = env.cr.fetchone()
        if row:
            openupgrade.add_xmlid(
                env.cr, "l10n_th", xmlid, "account.account.tag", row[0], noupdate=True
            )
