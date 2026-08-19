from openupgradelib import openupgrade

# 18.0 eLearning training lines are display_type='course'; in 19.0 the
# categorization key is course_type='elearning' (hr_skills fills the new
# required column with its 'external' default, and channel_id's compute
# wipes the channel on any line whose course_type isn't 'elearning').


@openupgrade.migrate()
def migrate(env, version):
    if openupgrade.column_exists(
        env.cr, "hr_resume_line", "display_type"
    ) and openupgrade.column_exists(env.cr, "hr_resume_line", "course_type"):
        openupgrade.logged_query(
            env.cr,
            """
            UPDATE hr_resume_line
            SET course_type = 'elearning'
            WHERE display_type = 'course'
            """,
        )
