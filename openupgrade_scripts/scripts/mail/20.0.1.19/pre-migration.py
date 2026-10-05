# Copyright 2026 Don Kendall
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from openupgradelib import openupgrade


def _claim_admin_channel_membership(env):
    """Give the administrator's membership of the admin channel its new xml_id.

    20.0 ships discuss.channel.member records for memberships that 19.0 created
    implicitly through autosubscribe, so the data load tries to insert a row
    that is already there and trips discuss_channel_member_partner_unique.
    Claiming the existing row turns that insert into an update.
    """
    env.cr.execute(
        """
        SELECT m.id
        FROM discuss_channel_member m
        JOIN ir_model_data channel
          ON channel.model = 'discuss.channel'
         AND channel.module = 'mail'
         AND channel.name = 'channel_admin'
         AND channel.res_id = m.channel_id
        JOIN ir_model_data partner
          ON partner.model = 'res.partner'
         AND partner.module = 'base'
         AND partner.name = 'partner_admin'
         AND partner.res_id = m.partner_id
        """
    )
    row = env.cr.fetchone()
    if row:
        openupgrade.add_xmlid(
            env.cr,
            "mail",
            "channel_member_channel_admin_partner_admin",
            "discuss.channel.member",
            row[0],
            noupdate=True,
        )


@openupgrade.migrate()
def migrate(env, version):
    _claim_admin_channel_membership(env)
