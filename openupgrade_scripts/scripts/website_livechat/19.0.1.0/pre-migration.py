from openupgradelib import openupgrade

# Obsolete noupdate record rule removed in 19.0; noupdate records aren't swept by
# the standard module update, so delete it by xml_id (record + ir_model_data).
_obsolete_rule_xmlids = ["website_livechat.im_livechat_channel_rule_public"]


@openupgrade.migrate()
def migrate(env, version):
    openupgrade.delete_records_safely_by_xml_id(env, _obsolete_rule_xmlids)
