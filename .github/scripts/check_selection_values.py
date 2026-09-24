#!/usr/bin/env python3
"""Fail when a stored selection holds a value the new version no longer declares.

A selection column keeps whatever it held. When the new version drops a key --
renames it, folds it into another, or replaces it with the empty value -- the
rows carrying the old key survive the upgrade unchanged. Nothing raises: the
constraint is a Python-level selection, not a database one, so the upgrade exits
0 and the value only shows up later as a blank in the interface and as a row
that matches neither branch of a domain over the field.

The 19->20 run found 600 attendances still marked as a lunch break, a period
20.0 has no concept of, and 184 products still tracked 'none' where 20.0 spells
that as the empty value.

WHY THIS READS THE REGISTRY, NOT THE ANALYSIS
---------------------------------------------
The obvious test -- take the keys upgrade_analysis.txt reports as removed and
look for them -- over-reports badly. A key one module removes another may add
straight back through selection_add, so the analysis shows a removal for a value
that is still perfectly valid. Against the same database that test flagged 28
fields where this one flags 6. `ir_model_fields_selection` is what the ORM
itself will validate against, so it is the only honest source.

Three kinds of column are skipped, each for a reason rather than for
convenience:

  * company-dependent fields store a jsonb map keyed by company id, so the
    column never holds a bare selection key;
  * a column whose type is not text is not plain selection storage;
  * a field the registry declares no values for cannot be checked at all.

Usage:  check_selection_values.py [--dsn DSN] [--allow model.field=value,...]

The connection comes from --dsn, else from the standard libpq environment. It is
required: a run that cannot reach the database fails rather than reporting a
clean sweep it never performed.
"""

import argparse
import sys

# model.field -> {value: why it is acceptable}. Keep this empty if at all
# possible; a stale entry here hides a real regression.
ALLOWED = {
    # Odoo's own product_supplierinfo.py declares `index=1` -- the integer,
    # not True or 'btree' -- so the ORM writes a value its own selection does
    # not carry. A fresh 20.0 install has the same row; there is nothing for a
    # migration script to repair.
    "ir.model.fields.index": {
        "1": "odoo/odoo declares index=1 on product.supplierinfo.company_id"
    },
    # 19.0 did not declare 'inside' either -- the value is already in the 19.0
    # seed, carried from further back. A 19->20 script is the wrong place to
    # repair data that was invalid before this upgrade started.
    "product.document.attached_on_sale": {
        "inside": "already invalid in 19.0; predates this migration"
    },
    # 19.0's hr_fleet added a fleet_manager responsible; 20.0's hr_fleet does
    # not extend the field at all. Every remaining value names a different
    # person -- manager, employee, a specific user -- so picking one decides who
    # gets the activity, which is a configuration question and not a rename.
    "mail.activity.plan.template.responsible_type": {
        "fleet_manager": "20.0 dropped it and offers no equivalent; who should "
        "be responsible instead is a decision for the administrator"
    },
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


def stored_selections(cur):
    """(model, field, table, allowed values) for every checkable selection.

    The values come back as an array rather than a joined string: selection
    keys can themselves contain commas -- res.lang.grouping holds '[3,2,0]' --
    and splitting a joined list on commas turns one valid key into three
    invalid ones, which reports the field as broken when it is not.
    """
    cur.execute(
        """
        SELECT f.model, f.name, array_agg(s.value)
        FROM ir_model_fields f
        JOIN ir_model_fields_selection s ON s.field_id = f.id
        JOIN information_schema.columns c
          ON c.table_schema = 'public'
         AND c.table_name = replace(f.model, '.', '_')
         AND c.column_name = f.name
        WHERE f.store
          AND f.ttype = 'selection'
          AND NOT coalesce(f.company_dependent, false)
          AND c.data_type IN ('character varying', 'text')
        GROUP BY f.model, f.name
        """
    )
    return [(m, f, m.replace(".", "_"), vals) for m, f, vals in cur.fetchall()]


def offenders(cur, table, field, allowed):
    cur.execute(
        f'SELECT "{field}"::text, count(*) FROM "{table}" '
        f'WHERE "{field}" IS NOT NULL AND NOT ("{field}"::text = ANY(%s)) '
        f"GROUP BY 1 ORDER BY 2 DESC",
        (allowed,),
    )
    return cur.fetchall()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dsn", help="libpq connection string; defaults to PG* env")
    opts = parser.parse_args()

    conn = connect(opts.dsn)
    if conn is None:
        return 2

    checked, findings = 0, []
    with conn, conn.cursor() as cur:
        fields = stored_selections(cur)
        if not fields:
            print(
                "::error::no stored selection fields found — this is not a "
                "migrated Odoo database, and a clean sweep would mean nothing"
            )
            return 2
        for model, field, table, allowed in fields:
            checked += 1
            for value, count in offenders(cur, table, field, allowed):
                why = ALLOWED.get(f"{model}.{field}", {}).get(value)
                if why:
                    print(
                        f"known: {model}.{field} = {value!r} "
                        f"({count} rows)\n       -> {why}"
                    )
                    continue
                findings.append((model, field, value, count, allowed))

    if not findings:
        print(
            f"OK: {checked} stored selection fields, none holding an undeclared value."
        )
        return 0

    print()
    for model, field, value, count, allowed in sorted(findings, key=lambda x: -x[3]):
        print(
            f"::error::{model}.{field} holds {value!r} on {count} row(s); "
            f"20.0 declares {sorted(allowed)}"
        )
    print(
        f"\n{len(findings)} stored selection value(s) the new version does not "
        f"declare. "
        f"Each is a row the interface shows blank and a domain over the field misses. "
        f"Map it to the new key in a migration script, or add an ALLOWED entry saying "
        f"why the database is correct as it stands."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
