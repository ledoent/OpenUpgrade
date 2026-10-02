# Copyright 2026 Don Kendall
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import csv
import os

from openupgradelib import openupgrade

from odoo.modules.module import get_module_path

# pylint: disable=odoo-addons-relative-import
from odoo.addons.openupgrade_scripts.apriori import merged_modules, renamed_modules

_renamed_xmlids = [
    # Odisha: the id was spelled after the old "Orissa" name
    ("base.state_in_or", "base.state_in_od"),
    # Ladakh moved from the localization into base
    ("l10n_in.state_in_la", "base.state_in_la"),
]

# res.partner.bank spells its account number out in 20.0. Both halves are pure
# renames -- the sanitized one is a stored compute in 19.0 and in 20.0 alike --
# so renaming the columns carries the values over and leaves
# unique(sanitized_account_number, partner_id) meaningful. Left undone, the new
# columns are created empty: every bank account in the database reads as having
# no number, and the upgrade says so in one line it does not fail on,
# "Constraint not added: column account_number of relation res_partner_bank
# contains null values".
_renamed_fields = [
    (
        "res.partner.bank",
        "res_partner_bank",
        "acc_number",
        "account_number",
    ),
    (
        "res.partner.bank",
        "res_partner_bank",
        "sanitized_acc_number",
        "sanitized_account_number",
    ),
    # The third of the same family, and the one that does damage if it is left
    # out. 20.0's holder_name is a stored compute, _compute_account_holder_name,
    # whose body is `if not account.holder_name: account.holder_name =
    # account.partner_id.name` (res_partner_bank.py:167-170). It does not
    # overwrite a value -- it fills an EMPTY column, which is exactly what an
    # unrenamed holder_name is. So the account ends up displaying the partner's
    # name as its holder, which is plausible enough that nothing looks wrong,
    # while the real holder sits unread in the legacy column.
    #
    # Measured on the sanitised prod copy 2026-10-02, before this rename: 13 of
    # 19 accounts carried an acc_holder_name and 4 of them disagreed with what
    # the compute wrote -- "Ledo Enterprises LLC" showed as "Ledo Enterprises",
    # and the joint holder "Don Kendall and Aimee Kendall" showed as "Kendall
    # Family Budget" on two accounts.
    #
    # Renaming is the whole fix: the value arrives in holder_name, and the
    # compute's own guard then leaves those rows alone.
    (
        "res.partner.bank",
        "res_partner_bank",
        "acc_holder_name",
        "holder_name",
    ),
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


def _release_noupdate_on_csv_access(env):
    """Let 20.0's security data reassert itself over the converted rows.

    19.0 declared most of its ir.rule records inside <data noupdate="1">, so
    their ir_model_data rows carry noupdate. 20.0 ships the same xml_ids as
    rows of security/ir.access.csv, and a CSV loads updatable. _convert_rules
    re-points the existing ir_model_data row rather than letting the new CSV
    create one, so the flag is inherited and the loader then declines to write
    the 20.0 definition over it: every such rule keeps enforcing its 19.0
    domain. Measured on a production copy: 271 rows flagged noupdate that 20.0
    ships updatable, 22 of them with a domain that no longer matches core.

    That is not only drift. project.project_task_rule_portal is the clear case:
    19.0 filtered collaborators on project.collaborator.limited_access, a field
    20.0 replaced with access_mode, and 20.0's CSV rewrote the domain to suit.
    Keeping the 19.0 text leaves a rule naming a field that does not exist, so
    reading project.task as a portal user raises
    "Invalid field project.collaborator.limited_access in condition" -- project
    sharing is simply broken for portal users, and nothing in the upgrade says
    so. The other twenty-one are silent: they enforce 19.0's access logic on a
    20.0 database, which for hr.hr_employee_comp_rule,
    calendar.calendar_event_rule_private and sale.sale_order_line_rule_portal
    decides who may read what.

    So the flag is cleared only where the module that owns the xml_id ships it
    in an ir.access.csv -- i.e. where 20.0 has itself declared the record
    updatable. A rule 20.0 still declares noupdate, or one a user created, is
    left alone. Clearing it here in base, before any other module's data is
    loaded, is what makes the subsequent load pick the records up.
    """
    env.cr.execute(
        """
        SELECT DISTINCT module FROM ir_model_data
        WHERE model = 'ir.access' AND noupdate IS TRUE
        """
    )
    xmlids = []
    for (module,) in env.cr.fetchall():
        path = get_module_path(module, display_warning=False)
        if not path:
            continue
        csv_path = os.path.join(path, "security", "ir.access.csv")
        if not os.path.isfile(csv_path):
            continue
        with open(csv_path, encoding="utf-8") as fobj:
            for row in csv.DictReader(fobj):
                # An id with a dot already names another module's record.
                if row.get("id"):
                    xmlids.append(f"{module}.{row['id']}")
    if not xmlids:
        return
    openupgrade.logged_query(
        env.cr,
        """
        UPDATE ir_model_data SET noupdate = false
        WHERE model = 'ir.access' AND noupdate IS TRUE
          AND module || '.' || name IN %s
        """,
        (tuple(xmlids),),
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
    # rename_fields warns against using it in base because it needs the
    # environment, which is not loaded yet. It does not: every statement in it
    # and in rename_field_references goes through env.cr, and its own no_deep
    # flag is declared but never read.
    openupgrade.rename_fields(env, _renamed_fields)
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
    # Must follow _convert_rules: it operates on the xml_ids that function
    # re-points, and must run before any other module loads its security data.
    _release_noupdate_on_csv_access(env)
