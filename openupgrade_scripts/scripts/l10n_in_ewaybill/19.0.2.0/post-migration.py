from openupgradelib import openupgrade

# Companion to pre-migration.py. The 18.0 ewaybill fields on account.move
# (l10n_in_distance, _mode, _transportation_doc_date, _transportation_doc_no,
# _transporter_id, _type_id, _vehicle_no, _vehicle_type) were preserved as
# openupgrade_legacy_19_0_* columns by the pre-migration. In 19.0 the same
# data lives on l10n.in.ewaybill rows linked via account_move_id.
#
# For each account.move with non-NULL legacy ewaybill data we INSERT one
# l10n.in.ewaybill row capturing the eight transport fields. The new row
# starts in state='pending' (the 19.0 default) since the 18.0 schema did
# not track ewaybill-API status separately from the account.move record
# itself — the operator can re-fetch from the e-Waybill API after
# migration if they need to reconcile with the gov portal.
#
# l10n.in.ewaybill.mode in 19.0 drops the '0' selection key from 18.0;
# we coerce any '0'-valued rows to NULL (operator marks them after the
# fact). Other selection keys ('1'/'2'/'3'/'4' and 'O'/'R') overlap
# cleanly between versions.


@openupgrade.migrate()
def migrate(env, version):
    # Discover the legacy column names that pre-migration.py created. If
    # the legacy columns are absent (e.g. on a fresh install or a re-run
    # where post already executed), exit cleanly.
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
            account_move_id, state,
            distance, mode,
            transportation_doc_date, transportation_doc_no,
            transporter_id, type_id,
            vehicle_no, vehicle_type,
            create_uid, create_date, write_uid, write_date
        )
        SELECT
            am.id,
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
