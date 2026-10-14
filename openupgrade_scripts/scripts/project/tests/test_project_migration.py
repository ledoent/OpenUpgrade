from odoo.tests import TransactionCase

from odoo.addons.openupgrade_framework import openupgrade_test


@openupgrade_test
class TestProjectMigration(TransactionCase):
    """Assertions on project.collaborator.limited_access becoming access_mode.

    Every method opens by asserting the record exists. The data snippet runs in
    a separate process through the 19.0 shell, and if its commit were lost it
    would exit 0 having written nothing -- an assertion whose empty case is a
    pass would then report success for a migration that never happened.
    """

    def test_every_collaborator_matches_its_19_value(self):
        """False and True map to different keys, so one value cannot serve both.

        20.0's access_mode is required and defaults to 'view', which would
        demote every collaborator to a reader. The mapping comes from the same
        method in both versions: 19.0's `_add_collaborators(..., limited_access
        =False)` is 20.0's `_add_collaborators(..., access_mode='advanced_edit')`.

        Asserted row by row rather than against a count. The seed carries a
        collaborator of its own besides the fixture's two, so counting them
        tests the seed rather than the migration -- and checking each row
        against its own legacy boolean covers that third one too.
        """
        self.env.cr.execute(
            """
            SELECT count(*) FILTER (WHERE limited_access AND access_mode <> 'edit'),
                   count(*) FILTER (WHERE NOT limited_access AND access_mode <> 'advanced_edit'),
                   count(*) FILTER (WHERE limited_access),
                   count(*) FILTER (WHERE NOT limited_access)
            FROM project_collaborator
            """
        )
        wrong_limited, wrong_full, limited, full = self.env.cr.fetchone()
        self.assertEqual(wrong_limited, 0, "a limited collaborator is not on 'edit'")
        self.assertEqual(
            wrong_full, 0, "an unlimited collaborator is not on 'advanced_edit'"
        )
        # Both branches have to be reachable, or one mapping is untested.
        self.assertTrue(limited, "the fixture's limited collaborator is gone")
        self.assertTrue(full, "the fixture's unlimited collaborator is gone")

    def test_nobody_was_left_as_a_viewer(self):
        """'view' is 20.0's read-only share, which 19.0 did not record here.

        A collaborator row existed only because a project was shared for
        editing, so a collaborator reading 'view' after the upgrade is one whose
        granted rights were dropped.
        """
        self.env.cr.execute(
            """
            SELECT count(*) FROM project_collaborator
            WHERE access_mode = 'view' AND limited_access IS NOT NULL
            """
        )
        self.assertEqual(
            self.env.cr.fetchone()[0],
            0,
            "a collaborator shared for editing came out able to change nothing",
        )
