from openupgradelib import openupgrade

# These records move from website_crm_partner_assign (which now depends on
# partnership) — relocate the xml_ids so partnership's data load updates the
# existing rows instead of creating duplicate grades/menu/action/ACLs next
# to the preserved wcpa-owned ones.
_renamed_xmlids = [
    (
        "website_crm_partner_assign.res_partner_grade_action",
        "partnership.res_partner_grade_action",
    ),
    (
        "website_crm_partner_assign.access_res_partner_grade",
        "partnership.access_res_partner_grade",
    ),
    (
        "website_crm_partner_assign.access_res_partner_grade_manager",
        "partnership.access_res_partner_grade_manager",
    ),
    (
        "website_crm_partner_assign.menu_res_partner_grade_action",
        "partnership.menu_res_partner_grade_action",
    ),
    (
        "website_crm_partner_assign.res_partner_grade_data_bronze",
        "partnership.res_partner_grade_data_bronze",
    ),
    (
        "website_crm_partner_assign.res_partner_grade_data_gold",
        "partnership.res_partner_grade_data_gold",
    ),
    (
        "website_crm_partner_assign.res_partner_grade_data_silver",
        "partnership.res_partner_grade_data_silver",
    ),
]


@openupgrade.migrate()
def migrate(env, version):
    openupgrade.rename_xmlids(env.cr, _renamed_xmlids)
