from openupgradelib import openupgrade

# Companion to pre-migration.py: the 18.0 account.move ewaybill transport
# fields (preserved as openupgrade_legacy_19_0_* columns) become one
# l10n.in.ewaybill row per move in 19.0, linked via account_move_id. Rows
# enter state='pending' (the 19.0 default) -- 18.0 tracked only transport
# details on the move, never an e-Waybill number, so nothing was generated.
# company_id is a stored computed field (compute from account_move_id); set
# it explicitly from the move so the row isn't left NULL until a recompute.


@openupgrade.migrate()
def migrate(env, version):
    legacy_distance = openupgrade.get_legacy_name("l10n_in_distance")
    env.cr.execute(
        """
        SELECT column_name FROM information_schema.columns
         WHERE table_name = 'account_move' AND column_name = %s
        """,
        (legacy_distance,),
    )
    if not env.cr.fetchone():
        return

    legacy = {
        new_name: openupgrade.get_legacy_name(old_name)
        for new_name, old_name in (
            ("distance", "l10n_in_distance"),
            ("mode", "l10n_in_mode"),
            ("transportation_doc_date", "l10n_in_transportation_doc_date"),
            ("transportation_doc_no", "l10n_in_transportation_doc_no"),
            ("transporter_id", "l10n_in_transporter_id"),
            ("type_id", "l10n_in_type_id"),
            ("vehicle_no", "l10n_in_vehicle_no"),
            ("vehicle_type", "l10n_in_vehicle_type"),
        )
    }
    any_nonnull = " OR ".join(f"am.{c} IS NOT NULL" for c in legacy.values())

    openupgrade.logged_query(
        env.cr,
        f"""
        INSERT INTO l10n_in_ewaybill (
            account_move_id, company_id, state,
            distance, mode,
            transportation_doc_date, transportation_doc_no,
            transporter_id, type_id,
            vehicle_no, vehicle_type,
            create_uid, create_date, write_uid, write_date
        )
        SELECT
            am.id,
            am.company_id,
            'pending'::varchar,
            am.{legacy["distance"]},
            CASE WHEN am.{legacy["mode"]} = '0' THEN NULL ELSE am.{legacy["mode"]} END,
            am.{legacy["transportation_doc_date"]},
            am.{legacy["transportation_doc_no"]},
            am.{legacy["transporter_id"]},
            am.{legacy["type_id"]},
            am.{legacy["vehicle_no"]},
            am.{legacy["vehicle_type"]},
            COALESCE(am.write_uid, am.create_uid, 1),
            COALESCE(am.write_date, am.create_date, NOW() AT TIME ZONE 'UTC'),
            COALESCE(am.write_uid, am.create_uid, 1),
            COALESCE(am.write_date, am.create_date, NOW() AT TIME ZONE 'UTC')
        FROM account_move am
        WHERE {any_nonnull}
        """,
    )
