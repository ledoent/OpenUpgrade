# Copyright 2026 Don Kendall
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from openupgradelib import openupgrade

# Keeps the source hr.leave.type id on the work entry type standing in for it,
# so references can be re-pointed and merge_models has something to map on.
_legacy_leave_type_id = openupgrade.get_legacy_name("hr_leave_type_id")

# Every reference to a leave type that outlives 19.0, as
# (table, 19.0 column, 20.0 column).
#
# The old column is read and left alone rather than re-aimed: it still carries
# its foreign key to hr_leave_type, so writing a work entry type id into it
# fails, and OpenUpgrade keeps it as the record of where the value came from.
#
# Two references are deliberately absent. The *_generate_multi_wizard tables are
# transient. And hr_leave_type_res_users_rel, 19.0's "Notify HR", has no
# counterpart at all: hr.work.entry.type declares no res.users m2m, so 20.0
# drops the feature and there is nothing to carry over.
_references = [
    ("hr_leave", "holiday_status_id", "work_entry_type_id"),
    ("hr_leave_allocation", "holiday_status_id", "work_entry_type_id"),
    ("hr_leave_accrual_plan", "time_off_type_id", "work_entry_type_id"),
    (
        "res_company",
        "l10n_fr_reference_leave_type",
        "l10n_fr_reference_work_entry_type",
    ),
]


def _shared_columns(env):
    """Columns a leave type and a work entry type have in common.

    Read from the database rather than listed, because which of them exist
    depends on the installed localisations -- l10n_in alone contributes two.
    id and the audit columns are excluded; they are set explicitly.
    """
    env.cr.execute(
        """
        SELECT a.column_name
        FROM information_schema.columns a
        JOIN information_schema.columns b
          ON b.table_name = 'hr_work_entry_type' AND b.column_name = a.column_name
        WHERE a.table_name = 'hr_leave_type'
          AND a.column_name NOT IN (
            'id', 'create_uid', 'create_date', 'write_uid', 'write_date'
          )
        ORDER BY a.column_name
        """
    )
    return [row[0] for row in env.cr.fetchall()]


def _pick_targets(env):
    """Decide which work entry type stands in for each leave type.

    19.0's hr.leave.type already carried a work_entry_type_id, which is the
    pairing the administrator configured, so it is honoured wherever it is
    unambiguous. It is not always: on the seed 46 leave types link to a work
    entry type of their own, 12 share one with another leave type, and 18 have
    no link at all.

    20.0 has one record where 19.0 had two, so two leave types sharing a work
    entry type cannot both keep it -- whatever differs between them would have
    to be discarded. The oldest keeps the link and the others get a record of
    their own, which gives up the pairing rather than the leave type. Anything
    unlinked gets a record of its own too.
    """
    env.cr.execute(
        f"""
        ALTER TABLE hr_work_entry_type
        ADD COLUMN IF NOT EXISTS {_legacy_leave_type_id} integer
        """
    )
    # The unambiguous links, honoured as they stand.
    openupgrade.logged_query(
        env.cr,
        f"""
        UPDATE hr_work_entry_type wet
        SET {_legacy_leave_type_id} = keeper.id
        FROM (
            SELECT DISTINCT ON (work_entry_type_id) id, work_entry_type_id
            FROM hr_leave_type
            WHERE work_entry_type_id IS NOT NULL
            ORDER BY work_entry_type_id, id
        ) keeper
        WHERE wet.id = keeper.work_entry_type_id
        """,
    )
    columns = _shared_columns(env)
    quoted = ", ".join(f'"{c}"' for c in columns)
    selected = ", ".join(f'lt."{c}"' for c in columns)
    # Everything else needs a work entry type of its own, carrying the leave
    # type's settings.
    #
    # code is the payroll reference, required on a work entry type and with no
    # counterpart on a leave type. A leave type that shared a work entry type
    # with another takes that one's code, because it is the code its time off
    # was actually paid under. One that had no work entry type at all has no
    # such code to take, and gets a traceable placeholder instead -- the field
    # is not unique, so this cannot collide, and _report_synthesised_codes says
    # how many need an administrator's attention.
    # count_as and unit_of_measure are required on a work entry type and named
    # differently on a leave type, so they are mapped rather than copied:
    #
    #   time_type    'leave' -> count_as 'absence'        (both labelled Absence)
    #                'other' ->          'working_time'   (Worked Time)
    #   request_unit 'hour'  -> unit_of_measure 'hour'
    #                'day', 'half_day' ->         'day'   (20.0 has no half day
    #                                                      for allocation)
    #
    # They are only set on the records created here. A reused work entry type
    # already carries both from its work entry side, where they drive payroll,
    # and overwriting them would change how its existing work entries are paid.
    openupgrade.logged_query(
        env.cr,
        f"""
        INSERT INTO hr_work_entry_type (
            {quoted}, code, count_as, unit_of_measure,
            {_legacy_leave_type_id}, create_uid, create_date,
            write_uid, write_date
        )
        SELECT {selected},
               coalesce(paired.code, 'LEAVE' || lt.id),
               CASE WHEN lt.time_type = 'other' THEN 'working_time'
                    ELSE 'absence' END,
               CASE WHEN lt.request_unit = 'hour' THEN 'hour' ELSE 'day' END,
               lt.id,
               lt.create_uid, lt.create_date, lt.write_uid, lt.write_date
        FROM hr_leave_type lt
        LEFT JOIN hr_work_entry_type paired ON paired.id = lt.work_entry_type_id
        WHERE NOT EXISTS (
            SELECT 1 FROM hr_work_entry_type wet
            WHERE wet.{_legacy_leave_type_id} = lt.id
        )
        """,
    )
    # A reused work entry type has none of the leave settings on it yet: they
    # only ever existed on the leave type it is standing in for. Its own name is
    # left alone, being what the work entry side is known by.
    assignments = ", ".join(f'"{c}" = lt."{c}"' for c in columns if c != "name")
    openupgrade.logged_query(
        env.cr,
        f"""
        UPDATE hr_work_entry_type wet
        SET {assignments}
        FROM hr_leave_type lt
        WHERE wet.{_legacy_leave_type_id} = lt.id
          AND lt.work_entry_type_id = wet.id
        """,
    )
    # 20.0 decides from this flag what may be picked when requesting time off,
    # so a record derived from a leave type has to carry it.
    #
    # Not is_leave alongside it: that was 19.0's field on hr.work.entry.type
    # and 20.0 drops it. OpenUpgrade keeps the column, so SQL will happily
    # write to it for ever while no model reads it -- the migration test is
    # what noticed, with 'hr.work.entry.type' object has no attribute
    # 'is_leave'.
    openupgrade.logged_query(
        env.cr,
        f"""
        UPDATE hr_work_entry_type
        SET time_off_selectable = TRUE
        WHERE {_legacy_leave_type_id} IS NOT NULL
        """,
    )


def _repoint_references(env):
    """Point every surviving reference at the stand-in for its leave type."""
    for table, old_column, new_column in _references:
        if not openupgrade.column_exists(
            env.cr, table, old_column
        ) or not openupgrade.column_exists(env.cr, table, new_column):
            continue
        openupgrade.logged_query(
            env.cr,
            f"""
            UPDATE {table} t
            SET {new_column} = wet.id
            FROM hr_work_entry_type wet
            WHERE wet.{_legacy_leave_type_id} = t.{old_column}
              AND t.{new_column} IS NULL
            """,
        )


def _report_synthesised_codes(env):
    """Say how many payroll codes were invented, because nothing else will."""
    env.cr.execute(
        f"""
        SELECT count(*) FROM hr_work_entry_type
        WHERE {_legacy_leave_type_id} IS NOT NULL
          AND code = 'LEAVE' || {_legacy_leave_type_id}
        """
    )
    count = env.cr.fetchone()[0]
    if count:
        openupgrade.message(
            env.cr,
            "hr_holidays",
            False,
            False,
            "%s time off types had no work entry type in 19.0 and so no payroll "
            "code; they were given a placeholder code of the form LEAVE<id> and "
            "need one assigning",
            count,
        )


@openupgrade.migrate()
def migrate(env, version):
    openupgrade.load_data(env, "hr_holidays", "20.0.1.6/noupdate_changes.xml")
    openupgrade.delete_record_translations(
        env.cr,
        "hr_holidays",
        [
            "hr_work_entry.l10n_be_work_entry_type_phc",
            "hr_work_entry.l10n_eg_work_entry_type_death",
            "hr_work_entry.l10n_eg_work_entry_type_hajj",
            "hr_work_entry.l10n_eg_work_entry_type_marriage",
            "hr_work_entry.l10n_eg_work_entry_type_maternity",
            "hr_work_entry.l10n_kw_work_entry_type_annual_leave",
            "hr_work_entry.l10n_kw_work_entry_type_compassionate_leave",
            "hr_work_entry.l10n_kw_work_entry_type_hajj_leave",
            "hr_work_entry.l10n_kw_work_entry_type_maternity_leave",
            "hr_work_entry.l10n_kw_work_entry_type_sick_leave",
            "hr_work_entry.l10n_kw_work_entry_type_study_leave",
            "hr_work_entry.l10n_om_work_entry_type_fdrcl",
            "hr_work_entry.l10n_om_work_entry_type_hajj",
            "hr_work_entry.l10n_om_work_entry_type_iddah",
            "hr_work_entry.l10n_om_work_entry_type_maternity",
            "hr_work_entry.l10n_om_work_entry_type_paternity",
            "hr_work_entry.l10n_om_work_entry_type_sdrcl",
            "hr_work_entry.l10n_om_work_entry_type_sick_leave_0",
            "hr_work_entry.l10n_om_work_entry_type_sick_leave_100",
            "hr_work_entry.l10n_om_work_entry_type_sick_leave_35",
            "hr_work_entry.l10n_om_work_entry_type_sick_leave_50",
            "hr_work_entry.l10n_om_work_entry_type_sick_leave_75",
            "hr_work_entry.l10n_sa_work_entry_type_hajj",
            "hr_work_entry.l10n_sa_work_entry_type_iddah",
            "hr_work_entry.l10n_sa_work_entry_type_marriage",
            "hr_work_entry.l10n_sa_work_entry_type_paternity",
            "hr_work_entry.l10n_sa_work_entry_type_study",
        ],
        ["name"],
    )
    # hr.leave.type is gone in 20.0: hr_holidays now _inherit's
    # hr.work.entry.type and declares the leave settings on it. Both models
    # existed in 19.0, so this is a merge and not a rename -- it must not go in
    # apriori.renamed_models, which would have the analysis report the two as
    # one record.
    if not openupgrade.table_exists(env.cr, "hr_leave_type"):
        return
    _pick_targets(env)
    _repoint_references(env)
    _report_synthesised_codes(env)
    # Not openupgrade.merge_models. It re-points what refers to a model by name
    # -- ir_model_data, mail messages and followers, filters, attachments -- and
    # by the time this runs there is nothing left to re-point: hr.leave.type is
    # absent from the 20.0 registry, so Odoo has already removed its ir_model
    # row and everything keyed on it. Measured on the seed, all nine of those
    # tables hold zero rows naming hr.leave.type.
    #
    # Calling it anyway fails rather than doing nothing, because it looks the old
    # model up in ir_model and subscripts the result without checking.
    #
    # What the upgrade does not clean up is the hr_leave_type rows themselves,
    # orphaned with their references still pointing at them. That is what the
    # work above is for.
