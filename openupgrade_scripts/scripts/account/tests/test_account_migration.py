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

    def test_deductibility_is_rescaled_from_percent_to_fraction(self):
        """19.0's 0-100 deductible_amount becomes 20.0's 0-1 fraction.

        19.0 stored a percentage and divided at the point of use, `percentage =
        1 - line.deductible_amount / 100` (19.0 account_move.py:1731). 20.0
        renamed the idea to deductible_percentage and made it a fraction,
        default 1.0, constrained `< 0 or > 1` (account_move_line.py:480,
        :1973). The analysis reports a DEL/NEW pair rather than a rename, so
        without this carry the new column keeps its default and the 19.0 figure
        stays behind in its own.

        That failure is invisible on ordinary data: deductible_amount is 100 on
        all 16648 lines of the prod copy and deductible_percentage 1.0 on all
        16648, the two defaults agreeing by coincidence. The fixture plants the
        50 that makes the two scales disagree.
        """
        line = self.env.ref("__ou19__.ou19_line_half_deductible")
        self.assertEqual(line.deductible_percentage, 0.5)

    def test_a_fully_deductible_line_was_not_rescaled_to_nothing(self):
        """100 is 19.0's default and maps to 20.0's, so those rows stay at 1.0.

        Guards the obvious way to get this wrong -- dividing every row, which
        would turn every ordinary line into 1% deductible.
        """
        self.env.cr.execute(
            """
            SELECT count(*)
            FROM account_move_line
            WHERE deductible_amount = 100 AND deductible_percentage != 1
            """
        )
        self.assertEqual(self.env.cr.fetchone()[0], 0)

    def test_no_line_holds_a_fraction_outside_what_20_allows(self):
        """Nothing was written that 20.0's own constraint would reject."""
        self.env.cr.execute(
            """
            SELECT count(*) FROM account_move_line
            WHERE deductible_percentage < 0 OR deductible_percentage > 1
            """
        )
        self.assertEqual(self.env.cr.fetchone()[0], 0)
