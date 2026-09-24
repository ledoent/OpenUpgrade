#!/usr/bin/env python3
"""Report a NEW column the upgrade filled with one value where the rows differ.

The rename gate next door needs a DEL/NEW pair. Four of the five defects found
in this campaign had no DEL sibling at all -- they were new fields whose default
the ORM wrote over every pre-existing row -- so that gate was silent for all of
them:

  * fleet.vehicle.log.services.date_from, where `default=fields.Date.context_today`
    put the day of the upgrade on all six of the seed's service logs;
  * pos_sale's pos.config.default_product_id, where a default naming a record
    pointed all six points of sale at one product;
  * pos_event's uuids, where `default=lambda self: str(uuid4())` gave 41 rows
    across two tables the SAME identity;
  * stock_account's product.value pair, which cannot be repaired at all.

A column default is evaluated ONCE when the ORM creates the column, not once per
row. So on a table that already has rows, a new column holding exactly one
distinct value is the fingerprint of that: the upgrade did not carry anything,
it stamped.

WHY ONLY TWO KINDS OF FIELD
---------------------------
Asking the question of every new field is useless. Measured over this series,
**178 new columns across 61 modules** came out uniform on a populated table, and
**152** of those hold a non-falsy value -- because a genuinely new setting is
uniform too, and that is correct rather than wrong. A gate needing 152 reviewed
reasons is a gate whose allowlist becomes boilerplate, which is the failure this
project spent a phase deleting.

Two slices are different, and both are checked here:

  RULE A -- a `date` or `datetime`. Real dates vary. One timestamp across a
            populated table means the upgrade wrote its own clock over history,
            and the value usually IS the moment the migration ran.
  RULE B -- a `many2one`. Every pre-existing row now points at one record. This
            is often legitimate -- a `uom_id` defaulting to Units -- which is
            what ACKNOWLEDGED is for; it is also exactly how pos_sale pointed
            every point of sale at one product.

WHAT THIS CANNOT SEE, SO ITS SILENCE IS NOT A VERDICT
-----------------------------------------------------
  * The other ~150 uniform new columns. They are triage, not a gate:
    .github/scripts/triage/classify_analysis_lines.py lists them.
  * pos_event's uuids, one of the defects listed above. They are `char`, and a
    new char column holding one value is overwhelmingly a legitimate default --
    'login', 'Confirm Order', a colour. Gating char would report dozens of
    correct columns to catch one wrong one, so that case stays with the triage
    tool. The rule that DID catch it is "a column whose default is a callable
    producing a unique value", which the analysis does not record.
  * A column the upgrade stamped where the rows happened to agree anyway -- one
    row, or a table whose every row really does share the value.
  * Anything on a table that was empty before the upgrade. There is no
    pre-existing row to be wrong about.

Usage:  check_defaulted_columns.py [--dsn DSN] [--all]

  --all   also list the candidates ACKNOWLEDGED clears, for triage.

The connection comes from --dsn, else from the standard libpq environment. It is
required: without the database this can only guess, and a check that quietly
degrades to guessing is worse than no check.
"""

import argparse
import glob
import re
import sys

FIELD = re.compile(
    r"^(?P<module>\S+)\s*/\s*(?P<model>[\w.]+)\s*/\s*(?P<field>\S+)\s*"
    r"\((?P<type>[^)]*)\)\s*:\s*(?P<what>.*)$"
)

RULE_A_TYPES = {"date", "datetime"}
RULE_B_TYPES = {"many2one"}

# "module:model.field" -> why one value on every row is right here.
# Keep each reason specific enough that a reader can check it. A reason that
# would fit any field is the boilerplate this gate exists to prevent.
ACKNOWLEDGED = {
    # --- the product_uom_id -> uom_id family -------------------------------
    # The rename DID happen: the 19.0 column is gone from every one of these
    # tables. What is uniform is the seed, not the migration -- the catalogue
    # holds 6 distinct uoms and 24 products that are not in Units, but ZERO
    # stock moves reference one of them, so every row here is legitimately
    # uom.product_uom_unit. A database trading in kg would discriminate; this
    # one cannot, which is a statement about the data.
    "stock:stock.move.uom_id": "no move in the seed is for a non-Units product",
    "stock:stock.move.line.uom_id": (
        "no move line in the seed is for a non-Units product"
    ),
    "mrp:mrp.bom.uom_id": "every seeded BoM is for a product in Units",
    "mrp:mrp.bom.line.uom_id": "every seeded BoM line is for a product in Units",
    "mrp:mrp.production.uom_id": "every seeded order is for a product in Units",
    "product:product.supplierinfo.uom_id": "every seeded supplier line is in Units",
    "repair:repair.order.uom_id": "every seeded repair is for a product in Units",
    "purchase_requisition:purchase.requisition.line.uom_id": (
        "the one seeded requisition line is for a product in Units"
    ),
    "sale_management:sale.order.template.line.section_uom_id": (
        "the one filled template line is for a product in Units"
    ),
    # --- one value because the module ships exactly one such record ---------
    # Each resolves through ir_model_data to a record its own module installs,
    # so every row pointing at it is the default doing its job rather than the
    # upgrade flattening a choice.
    "hr_holidays:hr.work.entry.type.allocation_notif_subtype_id": (
        "hr_holidays.mt_leave_allocation -- the module ships one allocation subtype"
    ),
    "hr_attendance:hr.attendance.work_entry_type_id": (
        "hr_work_entry.us_work_entry_type_attendance, the shipped attendance type"
    ),
    "pos_sale:pos.config.default_product_id": (
        "pos_sale.default_sol_product -- and this one is WRITTEN by pos_sale's "
        "post-migration, because the default only runs for rows created after "
        "the record exists"
    ),
    "resource:resource.calendar.reference_calendar_id": (
        "resource.resource_calendar_std, and the seed has one company"
    ),
    "website_sale:website.rating_email_template_id": (
        "website_sale.mail_template_sale_order_rating, the shipped template"
    ),
    "pos_self_order_sms:pos.preset.sms_receipt_template_id": (
        "the shipped receipt template; 2 of 3 presets, the third has none"
    ),
    # --- one value because the seed has one of the thing pointed at ---------
    "fleet:fleet.service.type.company_id": "the seed's service types are all company 1",
    "account:account.cash.rounding.company_id": "1 of 2 roundings is company-scoped",
    "website_sale:sale.order.assigned_website_id": "the seed has one website",
    "l10n_fr_hr_holidays:res.company.l10n_fr_reference_work_entry_type": (
        "1 of 117 companies is French, so only it gets a reference type"
    ),
    "point_of_sale:pos.config.closing_journal_id": (
        "all 6 points of sale are in the one company, which has one POS journal"
    ),
    "point_of_sale:pos.config.default_partner_id": (
        "all 6 points of sale are in the one company"
    ),
    # --- a timestamp with no 19.0 source, so the default is the only answer --
    "project:project.project.date_last_stage_update": (
        "19.0 had no equivalent -- last_update_id/last_update_status are a "
        "different thing -- so nothing can be carried. Every project does now "
        "read as last updated at the upgrade, which is not recoverable"
    ),
    "im_livechat:discuss.channel.livechat_looking_for_help_since_dt": (
        "marks a channel currently waiting for an operator, a live state rather "
        "than history; 2 of 34 channels, and 19.0 recorded no such moment"
    ),
    "website_profile:gamification.badge.published_date": (
        "1 of 38 badges; 19.0 recorded no publication date to carry"
    ),
}


def connect(dsn):
    try:
        import psycopg2
    except ImportError:
        print("::error::psycopg2 is needed to read the migrated database")
        return None
    try:
        return psycopg2.connect(dsn) if dsn else psycopg2.connect("")
    except Exception as exc:  # noqa: BLE001 - any failure here is fatal alike
        print(f"::error::cannot reach the migrated database: {exc}")
        return None


def candidates():
    """Every NEW date/datetime or many2one line the analysis reports."""
    found = []
    for path in sorted(
        glob.glob("openupgrade_scripts/scripts/*/20.0.*/upgrade_analysis.txt")
    ):
        for line in open(path):
            m = FIELD.match(line.rstrip("\n"))
            if not m or not m["what"].startswith("NEW"):
                continue
            if m["type"] in RULE_A_TYPES:
                found.append((m["module"], m["model"], m["field"], m["type"], "A"))
            elif m["type"] in RULE_B_TYPES:
                found.append((m["module"], m["model"], m["field"], m["type"], "B"))
    return found


def measure(cur, model, field):
    """(rows, filled, distinct, one value) or None when it cannot be measured."""
    table = model.replace(".", "_")
    cur.execute("SELECT to_regclass(%s)", (table,))
    if not cur.fetchone()[0]:
        return None
    cur.execute(
        """
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = %s AND column_name = %s
        """,
        (table, field),
    )
    if not cur.fetchone():
        return None
    cur.execute(
        f'SELECT count(*), count("{field}"), count(DISTINCT "{field}") FROM "{table}"'
    )
    rows, filled, distinct = cur.fetchone()
    if not rows or not filled or distinct != 1:
        return (rows, filled, distinct, None)
    cur.execute(
        f'SELECT "{field}"::text FROM "{table}" WHERE "{field}" IS NOT NULL LIMIT 1'
    )
    return (rows, filled, distinct, cur.fetchone()[0])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dsn", help="libpq connection string")
    parser.add_argument(
        "--all", action="store_true", help="also list acknowledged candidates"
    )
    opts = parser.parse_args()

    lines = candidates()
    if not lines:
        # Zero candidates and zero files look identical in the output, and the
        # files are found relative to the working directory, so running this
        # from the wrong place would otherwise congratulate you.
        print(
            "::error::no NEW date/datetime/many2one line found in any "
            "upgrade_analysis.txt -- run this from the root of an OpenUpgrade "
            "series clone"
        )
        return 2

    conn = connect(opts.dsn)
    if conn is None:
        return 2

    findings, cleared, checked = [], [], 0
    with conn, conn.cursor() as cur:
        for module, model, field, ftype, rule in lines:
            measured = measure(cur, model, field)
            if measured is None:
                continue  # no table or no column: nothing survived to be wrong
            rows, filled, distinct, value = measured
            checked += 1
            if value is None:
                continue  # empty, or more than one value: the rows differ
            label = f"{module}:{model}.{field} ({ftype})"
            why = ACKNOWLEDGED.get(f"{module}:{model}.{field}")
            if why:
                cleared.append((label, why, value))
                continue
            findings.append((label, rule, rows, filled, value))

    if opts.all:
        for label, why, value in cleared:
            print(f"acknowledged: {label} = {value!r}\n              -> {why}")

    if not findings:
        print(
            f"OK: {checked} new date/datetime/many2one column(s) checked, none "
            f"holding a single value across rows that differ."
        )
        return 0

    print()
    for label, rule, rows, filled, value in sorted(findings, key=lambda f: -f[3]):
        kind = (
            "a timestamp on every row -- usually the moment the upgrade ran"
            if rule == "A"
            else "every row pointing at one record"
        )
        print(
            f"::error::{label} holds {value!r} on all {filled} of {rows} row(s): {kind}"
        )
    print(
        f"\n{len(findings)} new column(s) the upgrade filled with ONE value on a "
        f"table that already had rows. A column default is evaluated once when "
        f"the column is created, so this is what stamping looks like rather than "
        f"carrying. Either carry the 19.0 answer in that module's migration, or "
        f"record in ACKNOWLEDGED why one value really is right for every row."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
