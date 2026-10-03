# Copyright 2026 Don Kendall
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from openupgradelib import openupgrade


@openupgrade.migrate()
def migrate(env, version):
    openupgrade.load_data(env, "hr_work_entry", "20.0.1.0/noupdate_changes.xml")
    openupgrade.delete_record_translations(
        env.cr,
        "hr_work_entry",
        ["l10n_be_work_entry_type_european"],
        ["display_code"],
    )
    openupgrade.delete_record_translations(
        env.cr,
        "hr_work_entry",
        [
            "l10n_be_work_entry_type_bank_holiday",
            "l10n_be_work_entry_type_breast_feeding",
            "l10n_be_work_entry_type_credit_time",
            "l10n_be_work_entry_type_economic_unemployment",
            "l10n_be_work_entry_type_extra_legal",
            "l10n_be_work_entry_type_flemish_training_time_off",
            "l10n_be_work_entry_type_long_sick",
            "l10n_be_work_entry_type_maternity",
            "l10n_be_work_entry_type_medical_assistance",
            "l10n_be_work_entry_type_parental_time_off",
            "l10n_be_work_entry_type_partial_incapacity",
            "l10n_be_work_entry_type_paternity_company",
            "l10n_be_work_entry_type_paternity_legal",
            "l10n_be_work_entry_type_phc",
            "l10n_be_work_entry_type_recovery_additional",
            "l10n_be_work_entry_type_small_unemployment",
            "l10n_be_work_entry_type_solicitation_time_off",
            "l10n_be_work_entry_type_strike",
            "l10n_be_work_entry_type_training",
            "l10n_be_work_entry_type_training_time_off",
            "l10n_be_work_entry_type_unjustified_reason",
            "l10n_be_work_entry_type_unpredictable",
            "l10n_be_work_entry_type_youth_time_off",
            "l10n_sa_work_entry_type_sick_leave_0",
            "l10n_sa_work_entry_type_sick_leave_75",
        ],
        ["display_code", "name"],
    )
    openupgrade.delete_record_translations(
        env.cr,
        "hr_work_entry",
        [
            "l10n_au_work_entry_type_overtime_pto",
            "l10n_au_work_entry_type_overtime_regular",
            "l10n_au_work_entry_type_overtime_saturday_pto",
            "l10n_au_work_entry_type_overtime_sunday_pto",
            "l10n_ch_work_entry_type_bank_holiday",
            "l10n_hk_work_entry_type_public_holiday",
            "l10n_id_work_entry_type_public_holiday",
            "l10n_us_work_entry_type_double",
            "l10n_us_work_entry_type_overtime",
            "uae_public_holiday_entry_type",
        ],
        ["name"],
    )
