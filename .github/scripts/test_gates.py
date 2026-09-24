#!/usr/bin/env python3
"""The gates' own verdict logic, over constructed facts and no database.

Every other check in this directory needs a migrated database, which means the
only exercise their logic ever got was the run they were written for. That is
backwards: a gate whose predicate inverts does not fail loudly, it reports the
WRONG VERDICT for every migration proven afterwards, and the whole "prove it red
before trusting it green" discipline quietly becomes a ritual.

These cases need nothing but the source files, so CI runs them on every push --
unlike the gates themselves, which need a 20-minute upgrade first.

    python3 .github/scripts/test_gates.py        # or: make gates-selftest
"""

import importlib.util
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))


def _load(name):
    spec = importlib.util.spec_from_file_location(name, HERE / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


gatelib = _load("_gatelib")
defaulted = _load("check_defaulted_columns")
renames = _load("check_rename_pairs")


class TestAnalysisLineParsing(unittest.TestCase):
    """FIELD is shared by three gates; if it drifts they all read less."""

    def test_it_reads_a_field_line(self):
        line = (
            "fleet        / fleet.vehicle.log.services / date_from (date)"
            "              : NEW hasdefault: default"
        )
        m = gatelib.FIELD.match(line)
        self.assertIsNotNone(m, "the analysis' own field-line shape stopped parsing")
        self.assertEqual(m["module"], "fleet")
        self.assertEqual(m["model"], "fleet.vehicle.log.services")
        self.assertEqual(m["field"], "date_from")
        self.assertEqual(m["type"], "date")
        self.assertTrue(m["what"].startswith("NEW"))

    def test_it_reads_a_type_holding_a_space(self):
        """'False' and 'many2one' are not the only things in the brackets."""
        m = gatelib.FIELD.match("mail / mail.tracking.value / field_id (many2one): DEL")
        self.assertIsNotNone(m)
        self.assertEqual(m["type"], "many2one")
        self.assertTrue(m["what"].startswith("DEL"))

    def test_it_ignores_a_line_that_is_not_a_field(self):
        for line in (
            "---XML records in module 'stock'---",
            "NEW ir.access: stock_account.access_product_value_stock_manager",
            "# NOTHING TO DO: the column is left in place for database_cleanup",
            "",
        ):
            self.assertIsNone(
                gatelib.FIELD.match(line), f"{line!r} was parsed as a field line"
            )


class TestStampedPredicate(unittest.TestCase):
    """check_defaulted_columns' whole rule, stated as (rows, filled, distinct)."""

    def test_one_value_across_a_populated_table_is_a_stamp(self):
        self.assertTrue(defaulted.is_stamped(rows=6, filled=6, distinct=1))

    def test_a_partly_filled_column_still_counts_when_the_filled_rows_agree(self):
        # pos_self_order_sms: 2 of 3 presets carry the shipped template.
        self.assertTrue(defaulted.is_stamped(rows=3, filled=2, distinct=1))

    def test_rows_that_differ_are_not_a_stamp(self):
        self.assertFalse(defaulted.is_stamped(rows=6, filled=6, distinct=6))

    def test_an_empty_column_is_the_other_gate_s_business(self):
        # Old column full, new column empty is check_rename_pairs' rule 1.
        self.assertFalse(defaulted.is_stamped(rows=6, filled=0, distinct=0))

    def test_an_empty_table_has_no_pre_existing_row_to_be_wrong_about(self):
        self.assertFalse(defaulted.is_stamped(rows=0, filled=0, distinct=0))


class TestNameStemPairing(unittest.TestCase):
    """The narrowness IS the rule: pairing any two differing types is noise."""

    def test_it_pairs_the_one_to_many_shapes(self):
        for old, new in (
            ("user_id", "user_ids"),  # maintenance, the real one
            ("lot_id", "lot_ids"),
            ("mailing_filter_id", "mailing_filter_ids"),
            ("tag", "tags"),
        ):
            self.assertTrue(renames._same_stem(old, new), f"{old} -> {new}")
            self.assertTrue(renames._same_stem(new, old), f"{new} -> {old}")

    def test_it_does_not_pair_two_unrelated_names(self):
        for old, new in (
            ("iface_splitbill", "use_course_allocation"),
            ("position_h", "floor_plan_layout"),
            ("user_id", "partner_ids"),
            ("date", "date_from"),
        ):
            self.assertFalse(renames._same_stem(old, new), f"{old} -> {new}")


class TestAcknowledgedListsAreHonest(unittest.TestCase):
    """An allowlist entry with no reason is an entry nobody reviewed."""

    def test_every_entry_carries_a_reason(self):
        for gate, table in (
            ("check_defaulted_columns", defaulted.ACKNOWLEDGED),
            ("check_rename_pairs", renames.ACKNOWLEDGED),
        ):
            for key, why in table.items():
                self.assertTrue(
                    why and len(why.strip()) > 20,
                    f"{gate}: {key!r} is acknowledged without a usable reason",
                )

    def test_the_keys_look_like_what_the_gate_builds(self):
        for key in defaulted.ACKNOWLEDGED:
            self.assertRegex(
                key,
                r"^[\w.]+:[\w.]+\.\w+$",
                "a defaulted-columns key must be module:model.field or it can "
                "never match, and an entry that never matches reads as reviewed "
                "while doing nothing",
            )


class TestEveryGateCompiles(unittest.TestCase):
    """The repo's pre-commit config excludes ^.github/, so nothing else looks.

    Without this a syntax error in a gate surfaces only after CI has spent
    twenty minutes on the upgrade that gate was supposed to check.
    """

    def test_they_all_compile(self):
        import py_compile

        scripts = sorted(HERE.glob("*.py")) + sorted(HERE.glob("triage/*.py"))
        self.assertGreater(len(scripts), 4, "the gates moved; this found almost none")
        for script in scripts:
            with self.subTest(script=script.name):
                try:
                    py_compile.compile(str(script), doraise=True, cfile=None)
                except py_compile.PyCompileError as exc:
                    self.fail(f"{script.name} does not compile: {exc}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
