from openupgradelib import openupgrade


def fix_template_lang(env):
    """Reset "lang" field for these records, as they were set in previous
    version in XML, but not in this one, and Odoo doesn't reset non present
    fields.
    The templates are not marked as noupdate, so this change is not caught by
    upgrade_analysis
    """
    env.cr.execute(
        """
        UPDATE mail_template
        SET lang=NULL
        FROM
        ir_model_data imd
        WHERE
        imd.module='loyalty' and imd.name in (
            'mail_template_gift_card',
            'mail_template_loyalty_card'
        )
        and mail_template.id=imd.res_id
        """
    )


def rewrite_get_mail_partner(env):
    """19.0 removed loyalty.card's ``_get_mail_partner`` helper (which returned
    ``partner_id``, the recipient). Customized mail.templates still referencing
    it abort the noupdate data-load render, and ``_get_mail_author`` would swap
    in the company/internal user instead — the wrong partner. Rewrite the
    stored references to their 18.0 equivalent ``object.partner_id``."""
    for column in ("lang", "partner_to", "email_to", "body_html"):
        if not openupgrade.column_exists(env.cr, "mail_template", column):
            continue
        env.cr.execute(
            """
            SELECT data_type FROM information_schema.columns
             WHERE table_name = 'mail_template' AND column_name = %s
            """,
            (column,),
        )
        # translated columns (body_html) are jsonb; cast the rewrite back
        cast = "::jsonb" if env.cr.fetchone()[0] == "jsonb" else ""
        openupgrade.logged_query(
            env.cr,
            f"""
            UPDATE mail_template
               SET {column} = REPLACE(
                   {column}::text,
                   'object._get_mail_partner()',
                   'object.partner_id'
               ){cast}
             WHERE model = 'loyalty.card'
               AND {column}::text LIKE '%%_get_mail_partner%%'
            """,
        )


@openupgrade.migrate()
def migrate(env, version):
    fix_template_lang(env)
    rewrite_get_mail_partner(env)
