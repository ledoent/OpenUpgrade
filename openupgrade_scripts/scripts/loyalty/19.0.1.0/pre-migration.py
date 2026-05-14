from openupgradelib import openupgrade


def fix_template_lang(env):
    """Reset "lang" field for these records, as they were set in previous
    version in XML, but not in this one, and Odoo doesn't reset non present
    fields.
    The templates are not marked as noupdate, so this change is not caught by
    upgrade_analysis

    Only reset rows whose value still references the removed
    ``_get_mail_partner`` helper, so a customised lang is not clobbered.
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
        and mail_template.lang like '%_get_mail_partner%'
        """
    )


@openupgrade.migrate()
def migrate(env, version):
    fix_template_lang(env)
