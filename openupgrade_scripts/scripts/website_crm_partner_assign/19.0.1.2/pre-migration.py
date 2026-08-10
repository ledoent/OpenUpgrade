from openupgradelib import openupgrade

# Obsolete website_membership noupdate record rules removed in 19.0 (their
# ir_model_data already moved here by the apriori merge in base); noupdate
# records aren't swept by the standard module update, so delete them by xml_id
# (record + ir_model_data) to drop the stale public membership access.
_obsolete_rule_xmlids = [
    "website_crm_partner_assign.membership_membership_line_public",
    "website_crm_partner_assign.membership_product_product_public",
]


@openupgrade.migrate()
def migrate(env, version):
    openupgrade.delete_records_safely_by_xml_id(env, _obsolete_rule_xmlids)
