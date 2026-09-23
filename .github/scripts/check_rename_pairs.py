#!/usr/bin/env python3
"""Report fields that look renamed but were migrated as a drop plus a create.

The analysis reports a rename as two unrelated lines -- the old field under DEL
and the new one under NEW -- because nothing in the schema diff says they are
the same field. Read them separately and the natural annotation is
"# NOTHING TO DO: a new field, empty is the right value for existing records",
which is how `res.partner.bank.acc_number` became `account_number` with every
bank account in the database reading as having no number.

Pairing DEL with NEW on the same model and type finds the candidates, but a pair
is only a suspicion: two unrelated fields on one model change in one release all
the time. The database settles it. After a migration a real missed rename looks
exactly one way:

    the old column still holds values  AND  the new column is empty

That is evidence, not a guess, and it is the same shape as the constraint gate
next door: the analysis says where to look, the schema says what happened.

Pairs that have been looked at and are NOT renames go in ACKNOWLEDGED with the
reason. Pairs already handled -- by openupgrade.rename_fields, or by a script
that moves the data some other way -- are detected automatically and need no
entry.

Usage:  check_rename_pairs.py [--dsn DSN] [--all]

  --all   also list pairs the database clears, for triage. By default only the
          ones where data appears to have been left behind are reported.

The connection comes from --dsn, else from the standard libpq environment. It is
required: without the database this can only guess, and a check that quietly
degrades to guessing is worse than no check.
"""

import argparse
import collections
import glob
import re
import sys

FIELD = re.compile(
    r"^(?P<module>\S+)\s*/\s*(?P<model>[\w.]+)\s*/\s*(?P<field>\S+)\s*"
    r"\((?P<type>[^)]*)\)\s*:\s*(?P<what>.*)$"
)
# ("res.partner.bank", "res_partner_bank", "acc_number", "account_number")
DECLARED = re.compile(
    r'\(\s*"(?P<model>[\w.]+)"\s*,\s*"(?P<table>\w+)"\s*,\s*'
    r'"(?P<old>\w+)"\s*,\s*"(?P<new>\w+)"\s*,?\s*\)'
)
# _renamed_models = [("hr.contract.type", "hr.employee.type")]. Scoped to the
# declaration: a bare pair of dotted names also matches an xml_id rename, and
# "base.state_in_or" -> "base.state_in_od" is not a model.
MODEL_RENAME_BLOCK = re.compile(r"renamed_models\s*=\s*[\[{](.*?)[\]}]", re.S)
MODEL_RENAME = re.compile(r'"([\w.]+)"\s*[,:]\s*"([\w.]+)"')

# "module:model.old -> new (type)" -> why it is not a rename, for pairs that
# survive the automatic checks and have been looked at by hand.
ACKNOWLEDGED = {
    # --- the two sides are simply different fields ---
    "stock:stock.picking.type.show_operations -> auto_show_allocation_report "
    "(boolean)": (
        "19.0's show_operations controls the detailed operations view; 20.0's "
        "auto_show_allocation_report pops the allocation report on validation"
    ),
    "stock:stock.picking.type.show_operations -> wave_group_by_date (boolean)": (
        "wave_group_by_date is a wave-picking grouping option"
    ),
    "pos_restaurant:restaurant.table.shape -> parent_side (selection)": (
        "shape is the table's outline; parent_side is which edge a child table joins on"
    ),
    "pos_restaurant:pos.config.iface_splitbill -> use_course_allocation "
    "(boolean)": "bill splitting and course allocation are unrelated features",
    "pos_restaurant:pos.config.iface_splitbill -> "
    "use_show_items_on_course_ticket (boolean)": (
        "bill splitting and course tickets are unrelated features"
    ),
    "account:account.move.checked -> inventory_closing (boolean)": (
        "checked is 19.0's Reviewed flag; inventory_closing marks a closing entry"
    ),
    "hr:hr.version.is_flexible -> fixed_term (boolean)": (
        "is_flexible was computed from the schedule; fixed_term is related from "
        "the version and describes the contract's term"
    ),
    "hr:hr.version.is_fully_flexible -> fixed_term (boolean)": (
        "same as is_flexible: a computed schedule flag, not a contract term"
    ),
    "hr_holidays:hr.leave.request_unit_half -> is_time_rule_trimmed (boolean)": (
        "request_unit_half is the granularity of the request; "
        "is_time_rule_trimmed is about time rules"
    ),
    "hr_holidays:hr.leave.request_unit_hours -> is_time_rule_trimmed (boolean)": (
        "same as request_unit_half"
    ),
    "im_livechat:discuss.channel.rating_last_text -> livechat_rating (selection)": (
        "20.0 has no livechat_rating on discuss.channel; the NEW line is the "
        "kpi_livechat_rating family on a different model"
    ),
    "l10n_in:res.company.l10n_in_is_gst_registered -> "
    "l10n_in_disable_b2c_hsn_reporting (boolean)": (
        "registration status and a reporting opt-out are different settings"
    ),
    # --- the data is safe somewhere else ---
    "website_blog:blog.post.post_date -> publish_on (datetime)": (
        "post_date was a stored mirror of published_date, which 20.0 keeps and "
        "which is filled for every post; nothing was lost. publish_on is the "
        "mixin's 'Auto publish on', a future time, not a publication record"
    ),
    "website_slides:slide.slide.date_published -> publish_on (datetime)": (
        "the real rename is date_published -> published_date, handled in this "
        "module's pre-migration; publish_on is the mixin's 'Auto publish on'"
    ),
    "fleet:fleet.vehicle.log.services.date -> date_to (date)": (
        "19.0's single date became date_from, which is filled for every row; "
        "date_to is the new end of the range and has no 19.0 source"
    ),
    "l10n_ar_withholding:account.tax.l10n_ar_withholding_payment_type -> "
    "l10n_ar_withholding_tax_type (selection)": (
        "pairs with the same new field as l10n_ar_tax_type, which is the real "
        "rename; this one is the payment moment, not the tax type"
    ),
    # --- looked at, deliberately not carried ---
    "purchase_stock:purchase.order.line.location_final_id -> "
    "forecasted_location_id (many2one)": (
        "same comodel but a different purpose -- 'Location from procurement' "
        "against 'Location used in the computation of the forecast' -- and one "
        "row on the seed. Writing a procurement destination into a forecasting "
        "field would be a guess; revisit if a real database disagrees"
    ),
}


def relation_of(what):
    """The comodel an analysis line names, if any."""
    m = re.search(r"relation: ([\w.]+)", what or "")
    return m.group(1) if m else None


def renamed_models():
    """Models a pre-migration renames, as old name -> new name.

    Needed to compare comodels. A field whose comodel was renamed in the same
    release reads as pointing somewhere else entirely -- hr.version's
    contract_type_id (hr.contract.type) against employee_type_id
    (hr.employee.type) -- and gets dismissed as a model-level change, which is
    exactly the pair that most needs checking: the rename carries no data by
    itself and the 20 versions that had a contract type came out with none.
    """
    out = {}
    # apriori is the declaration the analyser itself pairs on; the pre-migrations
    # are what perform it. Read both, so a rename that only one of them knows
    # about still resolves.
    sources = ["openupgrade_scripts/apriori.py"] + glob.glob(
        "openupgrade_scripts/scripts/*/20.0.*/pre-migration.py"
    )
    for path in sources:
        try:
            text = open(path).read()
        except OSError:
            continue
        for block in MODEL_RENAME_BLOCK.findall(text):
            for old, new in MODEL_RENAME.findall(block):
                out[old] = new
    return out


def canonical(comodel, renames):
    """The comodel under the name it ends the migration with."""
    seen = set()
    while comodel in renames and comodel not in seen:
        seen.add(comodel)
        comodel = renames[comodel]
    return comodel


def declared_renames():
    """Renames a pre-migration already performs, keyed like the pairs."""
    out = set()
    for path in glob.glob("openupgrade_scripts/scripts/*/20.0.*/pre-migration.py"):
        module = path.split("/")[2]
        for m in DECLARED.finditer(open(path).read()):
            out.add((module, m["model"], m["old"], m["new"]))
    return out


def candidate_pairs():
    """Every DEL/NEW pair on one model and type, minus the declared renames.

    Capped at two on each side: past that the cross product says more about the
    module churning than about any one field, and the pairing is noise.
    """
    declared = declared_renames()
    pairs = []
    # Declared renames are checked too, not just subtracted. rename_fields moves
    # the column, so afterwards the old name should be gone; if it is still
    # there holding values while the new one is empty, the rename was declared
    # and did not happen -- which no other check would notice for a field the
    # new version does not also make required.
    for module, model, old_f, new_f in sorted(declared):
        pairs.append((module, model, old_f, new_f, "declared", None, None))
    for path in sorted(
        glob.glob("openupgrade_scripts/scripts/*/20.0.*/upgrade_analysis.txt")
    ):
        module = path.split("/")[2]
        dels = collections.defaultdict(list)
        news = collections.defaultdict(list)
        for line in open(path):
            m = FIELD.match(line.rstrip("\n"))
            if not m:
                continue
            key = (m["model"], m["type"])
            if m["what"].startswith("DEL"):
                dels[key].append((m["field"], m["what"]))
            elif m["what"].startswith("NEW"):
                news[key].append((m["field"], m["what"]))
        for key in set(dels) & set(news):
            if len(dels[key]) > 2 or len(news[key]) > 2:
                continue
            model, ftype = key
            for old, old_what in dels[key]:
                for new, new_what in news[key]:
                    if (module, model, old, new) in declared:
                        continue  # already queued above, with its own check
                    pairs.append(
                        (
                            module,
                            model,
                            old,
                            new,
                            ftype,
                            relation_of(old_what),
                            relation_of(new_what),
                        )
                    )
    return pairs


def connect(dsn):
    try:
        import psycopg2
    except ImportError:
        print("::error::psycopg2 is needed to check the migrated database")
        return None
    try:
        return psycopg2.connect(dsn) if dsn else psycopg2.connect("")
    except Exception as exc:  # noqa: BLE001 - any failure here is fatal alike
        print(f"::error::cannot reach the migrated database: {exc}")
        return None


def table_of(cur, model):
    cur.execute("SELECT 1 FROM ir_model WHERE model = %s", (model,))
    if not cur.fetchone():
        return None
    table = model.replace(".", "_")
    cur.execute("SELECT to_regclass(%s)", (table,))
    return table if cur.fetchone()[0] else None


def filled(cur, table, column):
    """Rows where the column is set, or None when there is no such column."""
    cur.execute(
        """
        SELECT 1 FROM information_schema.columns
        WHERE table_name = %s AND column_name = %s
        """,
        (table, column),
    )
    if not cur.fetchone():
        return None
    cur.execute(f'SELECT count(*) FROM "{table}" WHERE "{column}" IS NOT NULL')
    return cur.fetchone()[0]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dsn", help="libpq connection string")
    parser.add_argument(
        "--all", action="store_true", help="also list pairs the database clears"
    )
    opts = parser.parse_args()

    analyses = glob.glob("openupgrade_scripts/scripts/*/20.0.*/upgrade_analysis.txt")
    if not analyses:
        # Zero pairs and zero files look identical in the output, and the files
        # are found relative to the working directory, so run this from the
        # wrong place and it congratulates you.
        print(
            "::error::no upgrade_analysis.txt found -- run this from the root of "
            "an OpenUpgrade series clone"
        )
        return 2

    pairs = candidate_pairs()
    if not pairs:
        print(f"OK: {len(analyses)} analyses, no DEL/NEW field pair unaccounted for.")
        return 0

    conn = connect(opts.dsn)
    if conn is None:
        return 2

    model_renames = renamed_models()

    suspects, cleared, unreadable = [], [], []
    with conn, conn.cursor() as cur:
        for module, model, old, new, ftype, old_rel, new_rel in pairs:
            label = f"{module}:{model}.{old} -> {new} ({ftype})"
            if label in ACKNOWLEDGED:
                cleared.append((label, f"acknowledged: {ACKNOWLEDGED[label]}"))
                continue
            if (
                old_rel
                and new_rel
                and canonical(old_rel, model_renames)
                != canonical(new_rel, model_renames)
            ):
                # A field cannot be renamed into one that points at a different
                # model. Whatever happened is a model-level change, which is
                # apriori's business and not a rename this check can speak to.
                # Compared after the model renames, or a comodel that was itself
                # renamed makes the pair look unrelated.
                cleared.append((label, f"different comodel: {old_rel} vs {new_rel}"))
                continue
            table = table_of(cur, model)
            if not table:
                # The model is gone in 20.0, so this is a model-level change and
                # not a field rename; whatever happened is a different question.
                cleared.append((label, "the model itself does not exist in 20.0"))
                continue
            old_n, new_n = filled(cur, table, old), filled(cur, table, new)
            if old_n is None:
                cleared.append(
                    (
                        label,
                        f"{table}.{old} is gone"
                        + (
                            ", as the declared rename intends"
                            if ftype == "declared"
                            else ", so nothing was left"
                        ),
                    )
                )
            elif new_n is None:
                unreadable.append((label, f"{table}.{new} does not exist"))
            elif old_n and not new_n:
                suspects.append(
                    (label, f"{table}.{old} holds {old_n} value(s), {new} holds none")
                )
            else:
                cleared.append((label, f"{old}={old_n} filled, {new}={new_n} filled"))

    if opts.all:
        for label, why in cleared:
            print(f"cleared:  {label}\n          -> {why}")
    for label, why in unreadable:
        print(f"::warning::{label} -- {why}")

    if not suspects:
        print(
            f"\nOK: {len(pairs)} candidate pair(s), none left data behind"
            f"{'' if opts.all else ' (--all to list them)'}."
        )
        return 0

    print()
    for label, why in suspects:
        print(f"::error::{label} -- {why}")
    print(
        f"\n{len(suspects)} field(s) look renamed and were migrated as a drop plus a "
        f"create: the old column still holds values and the new one is empty. Either "
        f"add the rename to that module's pre-migration, or record in ACKNOWLEDGED "
        f"why the two are unrelated."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
