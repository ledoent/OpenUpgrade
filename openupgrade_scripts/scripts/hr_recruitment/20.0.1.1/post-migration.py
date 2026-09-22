# Copyright 2026 Don Kendall
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from openupgradelib import openupgrade


@openupgrade.migrate()
def migrate(env, version):
    openupgrade.load_data(env, "hr_recruitment", "20.0.1.1/noupdate_changes.xml")
    openupgrade.delete_record_translations(
        env.cr,
        "hr_recruitment",
        [
            "email_template_data_applicant_congratulations",
            "email_template_data_applicant_interest",
            "email_template_data_applicant_not_interested",
            "email_template_data_applicant_refuse",
        ],
        ["body_html"],
    )
    openupgrade.delete_record_translations(
        env.cr,
        "hr_recruitment",
        ["mt_applicant_new", "mt_job_new", "mt_talent_new"],
        ["description"],
    )
    openupgrade.delete_record_translations(
        env.cr,
        "hr_recruitment",
        ["degree_graduate"],
        ["name"],
    )
