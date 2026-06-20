from openupgradelib import openupgrade


@openupgrade.migrate()
def migrate(env, version):
    openupgrade.m2o_to_x2m(
        env.cr,
        env["event.question"],
        "event_question",
        "event_ids",
        "event_id",
    )
    openupgrade.m2o_to_x2m(
        env.cr,
        env["event.question"],
        "event_question",
        "event_type_ids",
        "event_type_id",
    )
    openupgrade.load_data(env, "event", "19.0.1.9/noupdate_changes_work.xml")
    # The reloaded event_registration_mail_template_badge carries a changed
    # body_html; drop stale 18.0 per-language translations so non-English users
    # see the 19.0 source instead of a shadowing old translation.
    openupgrade.delete_record_translations(
        env.cr, "event", ["event_registration_mail_template_badge"], ["body_html"]
    )
