# Copyright 2026 ledoent
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from openupgradelib import openupgrade


def reset_stale_loyalty_mail_template_lang(env):
    """
    18.0 set mail.template.lang on the loyalty gift-card and loyalty-card
    templates to '{{ object._get_mail_partner().lang }}'. The helper was
    removed from loyalty.card in 19.0, but the 19.0 mail_template_data.xml
    does not touch the lang field — so on mode=update load, ORM
    template-syntax validation evaluates the stale value and raises
    AttributeError, aborting migration at
    addons/loyalty/data/mail_template_data.xml:3.

    Clear lang only on records whose value still contains the broken
    reference, so any customer customisation is preserved.

    Other 18.0 stale references (mail.template.partner_to and body_html
    both also called _get_mail_partner) are not handled here because the
    19.0 XML overwrites them: partner_to via <field eval="False"/> and
    body_html via a full rewrite. The 19.0 design replaces explicit
    per-template lang/partner_to with use_default_to=True, which delegates
    recipient + language resolution to the model at send time.
    """
    env.cr.execute(
        """
        UPDATE mail_template
        SET lang = ''
        WHERE id IN (
            SELECT res_id FROM ir_model_data
            WHERE module = 'loyalty'
              AND name IN ('mail_template_gift_card', 'mail_template_loyalty_card')
        )
        AND lang LIKE '%_get_mail_partner%'
        """
    )


@openupgrade.migrate()
def migrate(env, version):
    reset_stale_loyalty_mail_template_lang(env)
