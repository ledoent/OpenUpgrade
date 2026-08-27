import json
import logging
from datetime import datetime

from openupgradelib import openupgrade

_logger = logging.getLogger(__name__)

# Companion to pre-migration.py: the 18.0 account.move ewaybill data becomes
# one l10n.in.ewaybill row per move, linked via account_move_id. A move
# carries data when a transport field is meaningfully set (Integer distance
# is ORM-written as 0, never NULL; mode '0' means managed-by-transporter) or
# when an in_ewaybill_1_03 EDI document exists: 18.0 generated real e-waybills
# through account_edi, so those rows get state generated/cancel and their NIC
# number + dates from the EDI response attachment instead of looking
# never-generated (which would invite duplicate re-generation against NIC).

_NIC_DATE_FORMATS = ("%d/%m/%Y %I:%M:%S %p", "%d/%m/%Y %H:%M:%S", "%d/%m/%Y")


def _nic_date(value):
    for fmt in _NIC_DATE_FORMATS:
        try:
            return datetime.strptime(str(value), fmt).date()
        except (TypeError, ValueError):
            continue
    return None


def _insert_ewaybills(env, legacy):
    data_preds = [
        f"COALESCE(am.{legacy['distance']}, 0) <> 0",
        f"COALESCE(am.{legacy['mode']}, '0') <> '0'",
    ] + [
        f"am.{legacy[c]} IS NOT NULL"
        for c in (
            "transportation_doc_date",
            "transportation_doc_no",
            "transporter_id",
            "type_id",
            "vehicle_no",
            "vehicle_type",
        )
    ]
    any_data = " OR ".join(data_preds)
    if openupgrade.table_exists(env.cr, "account_edi_document"):
        any_data += """
            OR am.id IN (
                SELECT d.move_id
                FROM account_edi_document d
                JOIN account_edi_format f ON f.id = d.edi_format_id
                WHERE f.code = 'in_ewaybill_1_03'
                  AND d.state IN ('sent', 'to_cancel', 'cancelled')
            )"""

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
        WHERE {any_data}
        """,
    )


def _mark_generated_from_edi(env):
    """E-waybills 18.0 actually generated: state + NIC number/dates from the
    EDI response JSON (the attachment stores the response's data object)."""
    if not openupgrade.table_exists(env.cr, "account_edi_document"):
        return
    env.cr.execute(
        """
        SELECT d.move_id, d.state, d.attachment_id
        FROM account_edi_document d
        JOIN account_edi_format f ON f.id = d.edi_format_id
        WHERE f.code = 'in_ewaybill_1_03'
          AND d.state IN ('sent', 'to_cancel', 'cancelled')
        """
    )
    Ewaybill = env["l10n.in.ewaybill"].with_context(tracking_disable=True)
    for move_id, edi_state, att_id in env.cr.fetchall():
        ewaybill = Ewaybill.search([("account_move_id", "=", move_id)], limit=1)
        if not ewaybill:
            continue
        vals = {"state": "cancel" if edi_state == "cancelled" else "generated"}
        response = {}
        if att_id:
            raw = env["ir.attachment"].browse(att_id).raw
            try:
                response = json.loads(raw.decode("utf-8"))
            except (ValueError, UnicodeDecodeError, AttributeError):
                _logger.info("unparsable ewaybill response for move %s", move_id)
        if response.get("ewayBillNo"):
            vals["name"] = str(response["ewayBillNo"])
        ewaybill_date = _nic_date(response.get("ewayBillDate"))
        if ewaybill_date:
            vals["ewaybill_date"] = ewaybill_date
        expiry = _nic_date(response.get("validUpto"))
        if expiry:
            vals["ewaybill_expiry_date"] = expiry
        ewaybill.write(vals)


def _backfill_computed_and_feature(env):
    ewaybills = env["l10n.in.ewaybill"].search([("account_move_id", "!=", False)])
    for fname in (
        "partner_bill_from_id",
        "partner_bill_to_id",
        "partner_ship_from_id",
        "partner_ship_to_id",
    ):
        env.add_to_compute(ewaybills._fields[fname], ewaybills)
    ewaybills.env.flush_all()
    # the UI gate: enable for companies that own migrated e-waybills
    openupgrade.logged_query(
        env.cr,
        """
        UPDATE res_company c
        SET l10n_in_ewaybill_feature = TRUE
        WHERE EXISTS (
            SELECT 1 FROM l10n_in_ewaybill e WHERE e.company_id = c.id
        )
        """,
    )


@openupgrade.migrate()
def migrate(env, version):
    legacy_distance = openupgrade.get_legacy_name("l10n_in_distance")
    if not openupgrade.column_exists(env.cr, "account_move", legacy_distance):
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
    _insert_ewaybills(env, legacy)
    _mark_generated_from_edi(env)
    _backfill_computed_and_feature(env)
