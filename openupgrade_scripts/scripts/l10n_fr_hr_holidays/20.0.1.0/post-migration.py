# Copyright 2026 Don Kendall
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from openupgradelib import openupgrade

# hr_holidays leaves the source hr.leave.type id on the work entry type standing
# in for it, which is what makes this lookup possible at all.
_legacy_leave_type_id = openupgrade.get_legacy_name("hr_leave_type_id")


@openupgrade.migrate()
def migrate(env, version):
    """Point the French reference leave type at its 20.0 stand-in.

    res.company.l10n_fr_reference_leave_type referenced hr.leave.type, which
    20.0 folds into hr.work.entry.type; the replacement is
    l10n_fr_reference_work_entry_type.

    This lives here rather than with the rest of that fold in hr_holidays
    because of load order: hr_holidays runs at module 234 of 563 and
    l10n_fr_hr_holidays at 361, so when hr_holidays' post-migration runs the new
    column does not exist yet. Its column_exists guard skipped the update
    silently -- no error, no value, and the company's reference type quietly
    lost. Doing it from the module that owns the column removes the ordering
    question entirely.
    """
    if not openupgrade.column_exists(
        env.cr, "res_company", "l10n_fr_reference_leave_type"
    ):
        return
    openupgrade.logged_query(
        env.cr,
        f"""
        UPDATE res_company c
        SET l10n_fr_reference_work_entry_type = wet.id
        FROM hr_work_entry_type wet
        WHERE wet.{_legacy_leave_type_id} = c.l10n_fr_reference_leave_type
          AND c.l10n_fr_reference_work_entry_type IS NULL
        """,
    )
