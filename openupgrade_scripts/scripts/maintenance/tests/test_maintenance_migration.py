from odoo.tests import TransactionCase

from odoo.addons.openupgrade_framework import openupgrade_test


@openupgrade_test
class TestMaintenanceMigration(TransactionCase):
    """Assertions on completion and assignment surviving the 19.0 model change.

    Every method opens by resolving its fixture. The data snippet runs in a
    separate process through the 19.0 shell, and if its commit were lost it
    would exit 0 having written nothing -- an assertion whose empty case is a
    pass would then report success for a migration that never happened.
    """

    def _request(self, name):
        record = self.env.ref(f"__ou19__.{name}", raise_if_not_found=False)
        self.assertTrue(
            record, f"{name} is missing: the 19.0 fixture never reached the database"
        )
        return record

    def _stage_is_done(self, request):
        """Read maintenance_stage.done from the column, not through the ORM.

        20.0 drops the field. The column survives the upgrade -- Odoo leaves a
        removed field's column in place -- which is how the migration reads it
        too, but `stage.done` through the ORM is an AttributeError.
        """
        self.env.cr.execute(
            "SELECT done FROM maintenance_stage WHERE id = %s", (request.stage_id.id,)
        )
        row = self.env.cr.fetchone()
        self.assertTrue(row, "the fixture's stage is gone")
        return row[0]

    def test_a_request_finished_in_19_0_reads_as_done(self):
        """19.0 said so through its stage; 20.0 has to say it on the request."""
        request = self._request("ou19_request_finished")
        self.assertTrue(
            self._stage_is_done(request),
            "the fixture is no longer on a stage marked done",
        )
        self.assertEqual(
            request.state,
            "done",
            "a completed maintenance request came out reading as In Progress, so "
            "it is counted as open and its equipment's MTBF ignores it",
        )

    def test_a_request_still_open_is_left_where_the_default_puts_it(self):
        """The half that says the carry is targeted rather than blanket."""
        request = self._request("ou19_request_open")
        self.assertFalse(self._stage_is_done(request))
        self.assertEqual(
            request.state, "normal", "an unfinished request was marked done"
        )

    def test_the_seed_agrees_stage_by_stage(self):
        """Not just the fixture: every request on a done stage must read done.

        The fixture proves the rule fires; this proves it fired everywhere,
        which is what a missed row would look like.
        """
        self.env.cr.execute(
            """
            SELECT count(*) FROM maintenance_request r
            JOIN maintenance_stage s ON s.id = r.stage_id
            WHERE s.done AND r.state != 'done'
            """
        )
        self.assertEqual(
            self.env.cr.fetchone()[0],
            0,
            "a request on a done stage is still not marked done",
        )

    def test_an_assignee_who_is_not_the_equipment_technician_survives(self):
        """The row the seed does not contain, and the only one that can fail.

        Every request in the seed is assigned to exactly its equipment's
        technician, so _compute_user_ids reproduces the assignment by itself and
        an assertion over those rows passes whether anything carried it or not.
        """
        request = self._request("ou19_request_reassigned")
        self.env.cr.execute(
            "SELECT user_id FROM maintenance_request WHERE id = %s", (request.id,)
        )
        assignee = self.env.cr.fetchone()[0]
        self.assertTrue(assignee, "the fixture lost its 19.0 user_id")
        self.assertNotEqual(
            assignee,
            request.equipment_id.technician_user_id.id,
            "the fixture no longer distinguishes the assignee from the "
            "equipment's technician, so it can no longer fail",
        )
        self.assertIn(
            assignee,
            request.user_ids.ids,
            "the 19.0 assignee is not among the technicians, so the request "
            "came out assigned to whoever the equipment names instead",
        )

    def test_a_blocked_request_was_not_given_an_invented_state(self):
        """20.0 offers no value that certainly means 19.0's 'blocked'."""
        request = self._request("ou19_request_blocked")
        self.env.cr.execute(
            "SELECT kanban_state FROM maintenance_request WHERE id = %s", (request.id,)
        )
        self.assertEqual(
            self.env.cr.fetchone()[0],
            "blocked",
            "the 19.0 answer is gone, so an administrator cannot act on it",
        )
        self.assertEqual(
            request.state,
            "normal",
            "a request blocked on something outside a review was given a "
            "review state it never had",
        )
