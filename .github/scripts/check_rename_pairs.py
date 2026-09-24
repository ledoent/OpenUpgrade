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
one of two ways:

    (1) the old column still holds values  AND  the new column is EMPTY
    (2) the old column still holds several values  AND  the new column holds
        exactly ONE on every row -- its default

That is evidence, not a guess, and it is the same shape as the constraint gate
next door: the analysis says where to look, the schema says what happened.

RULE 2 EXISTS BECAUSE RULE 1 CANNOT SEE A DEFAULT
-------------------------------------------------
A NEW field declared `required` with a `default` is never empty: the ORM fills
every pre-existing row as it creates the column. Rule 1 can therefore never fire
for one, and most new fields have a default. Three real defects sat behind that
blind spot in the 19->20 run, each of which rule 1 cleared as "both filled":

  * fleet.vehicle.log.services.date -> date_from, where date_from carries 19.0's
    help text unchanged AND `default=today`, so all six of the seed's service
    logs came out on the day the upgrade ran rather than empty;
  * sale's product.template.expense_policy -> reinvoice_policy, where all 197
    templates came out on the default while the old column sat beside them;
  * maintenance.request, where completion had lived on maintenance.stage.done
    and the new state defaulted every request to "In Progress".

The uniformity is the signal. A genuinely new setting is also uniform, which is
why rule 2 additionally requires the paired OLD column to still hold more than
one value: the information exists, and the new column is not reading it.

Pairs that have been looked at and are NOT renames go in ACKNOWLEDGED with the
reason. Pairs already handled -- by openupgrade.rename_fields, or by a script
that moves the data some other way -- are detected automatically and need no
entry.

WHAT THIS STILL CANNOT SEE, SO ITS SILENCE IS NOT A VERDICT
-----------------------------------------------------------
  * A succession ACROSS models. maintenance.request.state took over from
    maintenance.stage.done -- a column on a different table -- and no DEL/NEW
    pairing on one model can reach that.
  * A pair whose OLD column does not vary in THIS database. maintenance's own
    kanban_state -> state pair is reported cleared for exactly that reason: all
    five seed requests are on 'normal', so the data cannot tell a carried value
    from a defaulted one. That is a statement about the seed, not the code.
  * A pair where BOTH columns are filled and varied. Neither rule can fire, and
    the database genuinely cannot settle it: res.partner.peppol_eas ->
    routing_scheme is filled 73/44 distinct against 72/33, because BOTH versions
    declare it a stored compute with readonly=False. Whether the gap is 20.0
    deriving differently or a hand-entered override being lost is not a question
    any column can answer -- it needs a person. See ACKNOWLEDGED.

  * A cross-MODULE pair is proposed and works (peppol above is one, DEL and NEW
    both declared by account_edi_ubl_cii). Pairing across DIFFERENT modules is
    deliberately not done: measured over this corpus it adds 732 pairs, of which
    the first is iface_splitbill against seven unrelated pos.config booleans.

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
    # --- looked at, and declined on purpose ---------------------------------
    # 19 of 73 partners differ: 16 have an EAS and no routing scheme, 3 carry a
    # different one. It is NOT carried, decided by the maintainer. Both versions
    # declare the field a stored compute with readonly=False, so most of the gap
    # is 20.0's own _compute_routing_scheme_endpoint deriving differently, and
    # nothing in the database distinguishes a hand-entered override -- the only
    # thing that would be real data -- from a value the compute produced.
    "account_edi_ubl_cii:res.partner.peppol_eas -> routing_scheme (selection)": (
        "both sides are stored computes; the difference is 20.0 re-deriving, "
        "and an override cannot be told from a computed value"
    ),
    "account_edi_ubl_cii:res.partner.peppol_endpoint -> routing_endpoint (char)": (
        "same pair, same reason: routing_endpoint is computed alongside routing_scheme"
    ),
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
        pairs.extend(stem_pairs(module, dels, news, declared))
    return pairs


def stem_pairs(module, dels, news, declared):
    """DEL/NEW on one model whose TYPES differ but whose names are the same stem.

    The pass above groups by (model, type), so a field that changes type is
    never proposed -- and one that does is a succession like any other.
    maintenance.request.user_id (many2one) became user_ids (many2many), which is
    a real one this check missed until it was found by hand.

    Only the one-to-many shape is paired: `x` against `x_ids`, or `x_id` against
    `x_ids`, in either direction. That is deliberately narrow. Across the whole
    19->20 corpus it proposes SIX pairs, where pairing on differing types alone
    would propose hundreds -- and six is a triage list rather than noise.
    """
    by_model = collections.defaultdict(lambda: ([], []))
    for (model, ftype), fields in dels.items():
        for field, what in fields:
            by_model[model][0].append((field, ftype, what))
    for (model, ftype), fields in news.items():
        for field, what in fields:
            by_model[model][1].append((field, ftype, what))

    out = []
    for model, (old_fields, new_fields) in by_model.items():
        for old, old_type, old_what in old_fields:
            for new, new_type, new_what in new_fields:
                if old_type == new_type:
                    continue  # the pass above already had this one
                if not _same_stem(old, new):
                    continue
                if (module, model, old, new) in declared:
                    continue
                out.append(
                    (
                        module,
                        model,
                        old,
                        new,
                        f"{old_type}->{new_type}",
                        relation_of(old_what),
                        relation_of(new_what),
                    )
                )
    return out


def _same_stem(a, b):
    """True when one name is the plural many2many form of the other."""
    for one, other in ((a, b), (b, a)):
        if other in (f"{one}_ids", f"{one}s") or (
            one.endswith("_id") and other == f"{one[: -len('_id')]}_ids"
        ):
            return True
    return False


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


def filled_m2m(cur, model, field):
    """Rows in a many2many's relation table, or None when there is no such field.

    A many2many has no column on its own model's table, so `filled` answers None
    for one and the pair reads as unmeasurable -- which is exactly the shape the
    name-stem rule proposes (user_id -> user_ids). The relation table is not
    guessed from the names: 20.0 records it on ir_model_fields.relation_table,
    so this reads the same answer the ORM uses.
    """
    cur.execute(
        """
        SELECT relation_table FROM ir_model_fields
        WHERE model = %s AND name = %s AND ttype = 'many2many'
        """,
        (model, field),
    )
    row = cur.fetchone()
    if not row or not row[0]:
        return None
    cur.execute("SELECT to_regclass(%s)", (row[0],))
    if not cur.fetchone()[0]:
        return None
    cur.execute(f'SELECT count(*) FROM "{row[0]}"')
    return cur.fetchone()[0]


def spread(cur, table, column):
    """Distinct non-null values in the column, or None when they cannot be counted.

    `json` has no equality operator in Postgres, so DISTINCT over one raises
    rather than answering. That is reported as unreadable instead of being
    swallowed: a column this cannot measure must not be counted as cleared.
    """
    try:
        cur.execute(f'SELECT count(DISTINCT "{column}") FROM "{table}"')
        return cur.fetchone()[0]
    except Exception:  # noqa: BLE001 - any failure here means "cannot measure"
        cur.connection.rollback()
        return None


def classify(cur, pair, model_renames):
    """One pair's verdict: ("suspect" | "cleared" | "unreadable", label, why).

    Split out of main so each rule reads on its own -- and so the tool stays
    under the complexity limit it is itself linted against.
    """
    module, model, old, new, ftype, old_rel, new_rel = pair
    label = f"{module}:{model}.{old} -> {new} ({ftype})"
    if label in ACKNOWLEDGED:
        return "cleared", label, f"acknowledged: {ACKNOWLEDGED[label]}"
    if (
        old_rel
        and new_rel
        and canonical(old_rel, model_renames) != canonical(new_rel, model_renames)
    ):
        # A field cannot be renamed into one that points at a different model.
        # Whatever happened is a model-level change, which is apriori's business
        # and not a rename this check can speak to. Compared after the model
        # renames, or a comodel that was itself renamed looks unrelated.
        return "cleared", label, f"different comodel: {old_rel} vs {new_rel}"
    table = table_of(cur, model)
    if not table:
        # The model is gone in 20.0, so this is a model-level change and not a
        # field rename; whatever happened is a different question.
        return "cleared", label, "the model itself does not exist in 20.0"

    old_n, new_n = filled(cur, table, old), filled(cur, table, new)
    if old_n is None:
        tail = (
            ", as the declared rename intends"
            if ftype == "declared"
            else ", so nothing was left"
        )
        return "cleared", label, f"{table}.{old} is gone{tail}"
    if new_n is None:
        # A many2many keeps its data in a relation table rather than a column,
        # which is the shape the name-stem rule proposes. Read that instead of
        # reporting the pair unmeasurable.
        new_n = filled_m2m(cur, model, new)
        if new_n is None:
            return "unreadable", label, f"{table}.{new} does not exist"
        if old_n and not new_n:
            return (
                "suspect",
                label,
                f"{table}.{old} holds {old_n} value(s) and the {new} relation "
                f"table is empty",
            )
        return (
            "cleared",
            label,
            f"{old}={old_n} filled, {new} relation table holds {new_n} row(s)",
        )
    if old_n and not new_n:
        # Rule 1.
        return (
            "suspect",
            label,
            f"{table}.{old} holds {old_n} value(s), {new} holds none",
        )
    if not (old_n and new_n):
        return "cleared", label, f"{old}={old_n} filled, {new}={new_n} filled"

    # Rule 2. Both columns are full, which is what a default does to a new
    # column, so rule 1 is silent here by construction.
    old_spread = spread(cur, table, old)
    new_spread = spread(cur, table, new)
    if old_spread is None or new_spread is None:
        return "unreadable", label, f"{table}.{old} or {new} cannot be counted DISTINCT"
    if new_spread == 1 and old_spread > 1:
        return (
            "suspect",
            label,
            f"{table}.{new} holds ONE value on all {new_n} row(s) -- what a "
            f"default does -- while {old} still holds {old_spread}",
        )
    return (
        "cleared",
        label,
        f"{old}={old_n} filled/{old_spread} distinct, "
        f"{new}={new_n} filled/{new_spread} distinct",
    )


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
    buckets = {"suspect": suspects, "cleared": cleared, "unreadable": unreadable}
    with conn, conn.cursor() as cur:
        for pair in pairs:
            kind, label, why = classify(cur, pair, model_renames)
            buckets[kind].append((label, why))

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
        f"create: either the old column still holds values and the new one is empty, "
        f"or the new one holds a single value on every row -- its default -- while "
        f"the old one still holds several. Either add the rename to that module's "
        f"pre-migration, or record in ACKNOWLEDGED why the two are unrelated."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
