from openupgradelib import openupgrade


@openupgrade.migrate()
def migrate(env, version):
    """Clear the stale ``lang`` expression before the 19.0 data reload.

    The 18.0 ``mail_template_gift_card`` / ``mail_template_loyalty_card``
    stored ``lang`` as ``{{ object._get_mail_partner().lang }}``. The helper
    was removed in 19.0 and the 19.0 XML does not reset the field, so the
    load-time template-syntax check renders the stale expression and raises
    AttributeError, aborting at loyalty/data/mail_template_data.xml. That
    check runs during the data load, before post-migration, so the reset has
    to happen here. post-migration.py re-applies the reset via the ORM.
    """
    openupgrade.logged_query(
        env.cr,
        """
        UPDATE mail_template mt
        SET lang = NULL
        FROM ir_model_data imd
        WHERE imd.model = 'mail.template'
          AND imd.module = 'loyalty'
          AND imd.name IN ('mail_template_gift_card', 'mail_template_loyalty_card')
          AND mt.id = imd.res_id
        """,
    )
