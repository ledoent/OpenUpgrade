# Copyright 2026 Don Kendall
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from openupgradelib import openupgrade

# pylint: disable=odoo-addons-relative-import
from odoo.addons.openupgrade_scripts.apriori import merged_modules, renamed_modules

_renamed_xmlids = [
    # Odisha: the id was spelled after the old "Orissa" name
    ("base.state_in_or", "base.state_in_od"),
    # Ladakh moved from the localization into base
    ("l10n_in.state_in_la", "base.state_in_la"),
]

# Keeps the source ir.rule id on the rows we derive from it, so the xml_ids can
# be re-pointed afterwards.
_legacy_rule_id = openupgrade.get_legacy_name("ir_rule_id")


def _operation_sql(table):
    """Build ir.access.operation out of the four legacy permission booleans.

    The selection keys are the crud letters in that order, so 'cr', 'ru',
    'crud' and friends fall out of simple concatenation.
    """
    return (
        f"CASE WHEN {table}.perm_create THEN 'c' ELSE '' END || "
        f"CASE WHEN {table}.perm_read THEN 'r' ELSE '' END || "
        f"CASE WHEN {table}.perm_write THEN 'u' ELSE '' END || "
        f"CASE WHEN {table}.perm_unlink THEN 'd' ELSE '' END"
    )


def _convert_model_access(env):
    """ir.model.access becomes ir.access.

    The two tables are column-compatible apart from the permissions, so the
    records are carried over by renaming rather than copying. That keeps the
    ids, and with them every xml_id, which is what lets base's own
    security/ir.access.csv match its records instead of trying to create them a
    second time.
    """
    # rename_models re-points ir_model_data.model itself: it walks the
    # many2one references, and on a 19.0 schema get_many2one_references falls
    # back to a static list whose first entry is ("ir.model.data", "res_id",
    # "model", ""). No separate update is needed, and hr and l10n_tr rename
    # their own models without one for the same reason.
    openupgrade.rename_models(env.cr, [("ir.model.access", "ir.access")])
    openupgrade.rename_tables(env.cr, [("ir_model_access", "ir_access")])
    openupgrade.logged_query(
        env.cr,
        f"""
        ALTER TABLE ir_access
            ADD COLUMN IF NOT EXISTS operation varchar,
            ADD COLUMN IF NOT EXISTS domain varchar,
            ADD COLUMN IF NOT EXISTS note text,
            ADD COLUMN IF NOT EXISTS {_legacy_rule_id} integer
        """,
    )
    openupgrade.logged_query(
        env.cr,
        f"UPDATE ir_access SET operation = {_operation_sql('ir_access')}",
    )
    # An access line granting none of the four permissions has no equivalent in
    # 20.0, where operation is required. It granted nothing before either, so
    # dropping it leaves the effective rights unchanged.
    env.cr.execute("SELECT count(*) FROM ir_access WHERE operation = ''")
    empty_count = env.cr.fetchone()[0]
    if empty_count:
        # Their xml_ids go too, otherwise ir_model_data is left pointing at
        # rows that no longer exist.
        openupgrade.logged_query(
            env.cr,
            """
            DELETE FROM ir_model_data
            WHERE model = 'ir.access'
              AND res_id IN (SELECT id FROM ir_access WHERE operation = '')
            """,
        )
        openupgrade.logged_query(env.cr, "DELETE FROM ir_access WHERE operation = ''")
        openupgrade.message(
            env.cr,
            "base",
            False,
            False,
            "Removed %s access lines that granted no permission at all, as "
            "ir.access has no representation for them",
            empty_count,
        )


def _convert_rules(env):
    """Fold ir.rule into ir.access.

    20.0 stores one row per group, where a rule held a groups m2m, so a rule
    covering three groups becomes three rows. Only one of them can carry the
    original xml_id; the remaining rows are left unnamed, which is what a
    record created by a user rather than by a module looks like anyway.
    Rules without groups keep an empty group_id, matching how core writes its
    own global access lines. ir.rule.name is optional where ir.access.name is
    required, so an unnamed rule is labelled with its model.
    """
    openupgrade.logged_query(
        env.cr,
        f"""
        INSERT INTO ir_access (
            name, model_id, group_id, operation, domain, active,
            create_uid, create_date, write_uid, write_date, {_legacy_rule_id}
        )
        SELECT
            COALESCE(r.name, m.model), r.model_id, rel.group_id,
            {_operation_sql("r")},
            r.domain_force, r.active,
            r.create_uid, r.create_date, r.write_uid, r.write_date, r.id
        FROM ir_rule r
        JOIN ir_model m ON m.id = r.model_id
        LEFT JOIN rule_group_rel rel ON rel.rule_group_id = r.id
        WHERE ({_operation_sql("r")}) != ''
        """,
    )
    openupgrade.logged_query(
        env.cr,
        f"""
        UPDATE ir_model_data imd
        SET model = 'ir.access', res_id = mapped.access_id
        FROM (
            SELECT {_legacy_rule_id} AS rule_id, min(id) AS access_id
            FROM ir_access
            WHERE {_legacy_rule_id} IS NOT NULL
            GROUP BY {_legacy_rule_id}
        ) mapped
        WHERE imd.model = 'ir.rule' AND imd.res_id = mapped.rule_id
        """,
    )


def _convert_field_index_to_selection(env):
    """ir.model.fields.index was a boolean in 19.0 and is a selection in 20.0.

    Left alone, the boolean column is widened to varchar by the ORM and the
    values arrive as the strings "true"/"false", which are not members of
    FIELD_INDEX_TYPES. Registry.check_indexes asserts on exactly that set, so
    the upgrade stops with a bare AssertionError. A plain b-tree is what an
    indexed field meant in 19.0.
    """
    env.cr.execute(
        """
        SELECT data_type FROM information_schema.columns
        WHERE table_name = 'ir_model_fields' AND column_name = 'index'
        """
    )
    row = env.cr.fetchone()
    if not row or row[0] != "boolean":
        return
    openupgrade.logged_query(
        env.cr,
        """
        ALTER TABLE ir_model_fields
        ALTER COLUMN "index" DROP DEFAULT,
        ALTER COLUMN "index" TYPE varchar
        USING CASE WHEN "index" THEN 'btree' ELSE NULL END
        """,
    )


@openupgrade.migrate()
def migrate(env, version):
    # Stale transient rows are recomputed during init_models, and a leftover
    # mail.compose.message renders its template against a model that may not be
    # loaded yet, which ends the upgrade with a KeyError.
    openupgrade.clean_transient_models(env.cr)
    _convert_field_index_to_selection(env)
    # merged_modules and renamed_modules are only documentation until this
    # runs: it re-points every ir_model_data row at the module that owns the
    # record in 20.0. Without it each absorbed module's data collides on
    # load -- hr_org_chart's org chart action against hr's copy of it, and so
    # on for every entry in apriori.
    openupgrade.update_module_names(
        env.cr, renamed_modules.items(), environment_namespec=True
    )
    openupgrade.update_module_names(
        env.cr, merged_modules.items(), merge_modules=True, environment_namespec=True
    )
    openupgrade.rename_xmlids(env.cr, _renamed_xmlids)
    _convert_model_access(env)
    _convert_rules(env)
