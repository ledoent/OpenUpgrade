from openupgradelib import openupgrade

_renamed_models = [
    ("hr.candidate.skill", "hr.applicant.skill"),
]

_renamed_tables = [
    ("hr_candidate_skill", "hr_applicant_skill"),
]


def _remap_candidate_skill_to_applicant(env):
    """Re-point the skill rows from their candidate to its application(s).

    hr.candidate is merged into hr.applicant (apriori.merged_models), 1 candidate :
    N applicants via hr_applicant.candidate_id. The skill records carried candidate_id,
    so the parent link cannot be a plain rename: the stored integers are candidate ids,
    not applicant ids. Replicate a candidate's skills onto every application of that
    candidate (a recruiter on any application should see the person's skills); drop
    skills whose candidate produced no application. The skill_ids m2m is a stored
    compute on applicant_skill_ids, rebuilt by the -u, so only this o2m parent link
    needs migrating here.
    """
    cr = env.cr
    openupgrade.logged_query(
        cr, "ALTER TABLE hr_applicant_skill ADD COLUMN applicant_id integer"
    )
    cr.execute(
        """
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'hr_applicant_skill'
          AND column_name NOT IN ('id', 'applicant_id', 'candidate_id')
        """
    )
    carried = [row[0] for row in cr.fetchall()]
    cols = ", ".join(carried)
    src = ", ".join(f"s.{col}" for col in carried)
    openupgrade.logged_query(
        cr,
        f"""
        INSERT INTO hr_applicant_skill (applicant_id, {cols})
        SELECT a.id, {src}
        FROM hr_applicant_skill s
        JOIN hr_applicant a ON a.candidate_id = s.candidate_id
        WHERE a.id <> (
            SELECT min(a2.id) FROM hr_applicant a2
            WHERE a2.candidate_id = s.candidate_id
        )
        """,
    )
    openupgrade.logged_query(
        cr,
        """
        UPDATE hr_applicant_skill s
        SET applicant_id = (
            SELECT min(a.id) FROM hr_applicant a
            WHERE a.candidate_id = s.candidate_id
        )
        WHERE s.applicant_id IS NULL
        """,
    )
    openupgrade.logged_query(
        cr, "DELETE FROM hr_applicant_skill WHERE applicant_id IS NULL"
    )
    openupgrade.drop_columns(cr, [("hr_applicant_skill", "candidate_id")])


@openupgrade.migrate()
def migrate(env, version):
    openupgrade.rename_models(env.cr, _renamed_models)
    openupgrade.rename_tables(env.cr, _renamed_tables)
    _remap_candidate_skill_to_applicant(env)
