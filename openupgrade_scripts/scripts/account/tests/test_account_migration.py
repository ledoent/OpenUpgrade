from odoo.tests import TransactionCase

from odoo.addons.openupgrade_framework import openupgrade_test


@openupgrade_test
class TestAccountMigration(TransactionCase):
    """Assertions on 19.0's Reviewed flag reaching 20.0's review queue.

    Every method opens by resolving its fixture. The data snippet runs in a
    separate process through the 19.0 shell, and if its commit were lost it
    would exit 0 having written nothing -- an assertion whose empty case is a
    pass would then report success for a migration that never happened.
    """

    def _move(self, name):
        record = self.env.ref(f"__ou19__.{name}", raise_if_not_found=False)
        self.assertTrue(
            record, f"{name} is missing: the 19.0 fixture never reached the database"
        )
        return record

    def test_a_move_unreviewed_by_hand_lands_in_the_review_queue(self):
        """The branch the seed cannot reach on its own.

        19.0's compute sets checked True for a posted move, so a posted move
        carrying False was unticked by somebody. 20.0 calls that 'todo'.
        """
        move = self._move("ou19_move_unreviewed_by_hand")
        self.env.cr.execute(
            "SELECT checked, state FROM account_move WHERE id = %s", (move.id,)
        )
        checked, state = self.env.cr.fetchone()
        self.assertFalse(checked, "the fixture's 19.0 answer did not survive")
        self.assertEqual(state, "posted")
        self.assertEqual(
            move.review_state,
            "todo",
            "a move somebody had marked as not reviewed came out indistinguishable "
            "from one nobody ever looked at",
        )

    def test_a_move_that_only_carried_the_computed_default_is_left_alone(self):
        """The half that says the rule discriminates.

        Mapping checked=True to 'reviewed' would assert a review of every posted
        invoice in the database on the strength of a value that is really just
        "posted", so nothing is written for those.
        """
        move = self._move("ou19_move_left_alone")
        self.env.cr.execute(
            "SELECT checked FROM account_move WHERE id = %s", (move.id,)
        )
        self.assertTrue(self.env.cr.fetchone()[0], "the fixture is no longer checked")
        self.assertEqual(
            move.review_state,
            "no_review",
            "a posted entry was put into the review queue on the strength of the "
            "computed default",
        )

    def test_no_posted_move_was_swept_into_the_queue_wholesale(self):
        """3206 of the seed's moves are posted; one of them is the fixture."""
        self.env.cr.execute(
            "SELECT count(*) FROM account_move WHERE review_state = 'todo'"
        )
        in_queue = self.env.cr.fetchone()[0]
        self.env.cr.execute(
            "SELECT count(*) FROM account_move WHERE state = 'posted' AND NOT checked"
        )
        self.assertEqual(
            in_queue,
            self.env.cr.fetchone()[0],
            "the review queue holds more than the posted moves that were "
            "explicitly unticked in 19.0",
        )
