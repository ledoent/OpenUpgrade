# Copyright 2026 Don Kendall
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo.exceptions import ValidationError

from openupgradelib import openupgrade

# 19.0 recorded a device as the PARSED result; 20.0 records the raw string and
# parses it back on read. These fragments are chosen so that 20.0's own parser
# returns the platform and browser 19.0 stored -- the mapping is verified at run
# time rather than trusted, see _synthesise_device_user_agent.
_PLATFORM_FRAGMENT = {
    "macos": "Macintosh; Intel Mac OS X",
    "iphone": "iPhone; CPU iPhone OS like Mac OS X",
    "ipad": "iPad; CPU OS like Mac OS X",
    "android": "Linux; Android",
    "windows": "Windows NT 10.0; Win64; x64",
    "linux": "X11; Linux x86_64",
    "chromeos": "X11; CrOS x86_64",
}
# Ordered: the parser checks chrome before safari, and a Chrome string also
# carries a Safari token, so "safari" must not simply append Safari/.
_BROWSER_FRAGMENT = {
    "chrome": "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/0.0.0.0 Safari/537.36",
    "crios": "AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/0.0.0.0 Safari/604.1",
    "safari": "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/0.0 Safari/605.1.15",
    "firefox": "Gecko/20100101 Firefox/0.0",
    "edge": (
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/0.0.0.0 Safari/537.36 "
        "Edg/0.0.0.0"
    ),
    "opera": (
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/0.0.0.0 Safari/537.36 "
        "OPR/0.0.0.0"
    ),
}
# Says plainly that this string was written by a migration, so nobody reading a
# security log mistakes it for something a browser actually sent.
_MARKER = "[migrated-19.0-ua-not-recorded]"


def _synthesise_device_user_agent(env):
    """20.0 requires the raw user agent 19.0 never stored.

    19.0's res.device.log kept the device as PARSED columns -- `platform`,
    `browser`, `device_type`. 20.0 drops all three as stored fields, stores the
    raw `user_agent` instead (**required**), and recomputes platform and browser
    from it on read::

        user_agent = fields.Char('User Agent', required=True)
        platform   = fields.Char(compute='_compute_device_info', readonly=True)
        browser    = fields.Char(compute='_compute_device_info', readonly=True)

    So the column arrives NULL on every carried row and the NOT NULL cannot be
    applied. The upgrade logs "Constraint not added" and carries on: nothing
    raises, the constraint is simply absent from the migrated database, and
    every device reads as platform "Unknown" in the UI.

    The raw string is genuinely unrecoverable -- parsing a user agent is
    one-way. What IS recoverable is what 19.0 recorded, and that is what this
    writes: a user agent chosen so that **20.0's own parser returns exactly the
    platform and browser the row already carried**. The round trip is asserted
    below rather than assumed, using the same parser the model uses; any pair
    that fails to round trip is left alone and reported, because a string that
    parses to the wrong platform would be worse than a NULL.

    Version `0.0.0.0` and the trailing marker keep it honest. 19.0 never stored
    a browser version, and this is a security audit log -- a reader must be able
    to tell a migrated placeholder from something a browser really sent.

    Rows whose platform or browser 19.0 also left empty get the marker alone,
    which is non-null, parses to "Unknown", and claims nothing.
    """
    if not openupgrade.table_exists(env.cr, "res_device_log"):
        return
    if not openupgrade.column_exists(env.cr, "res_device_log", "platform"):
        # 19.0's parsed columns are what this reads; without them there is
        # nothing to carry and the fabrication would be pure invention.
        return

    try:
        from odoo.tools._vendor.useragents import UserAgent

        parse = UserAgent._parser
    except Exception:  # noqa: BLE001 - no parser means no verifiable round trip
        parse = None

    env.cr.execute(
        """
        SELECT DISTINCT platform, browser FROM res_device_log
        WHERE user_agent IS NULL
        """
    )
    pairs = env.cr.fetchall()
    written, skipped = 0, []
    for platform, browser in pairs:
        agent = _compose(platform, browser)
        if parse and (platform or browser):
            got_platform, got_browser = parse(agent)[:2]
            if (platform and got_platform != platform) or (
                browser and got_browser != browser
            ):
                skipped.append((platform, browser, got_platform, got_browser))
                continue
        openupgrade.logged_query(
            env.cr,
            """
            UPDATE res_device_log SET user_agent = %s
            WHERE user_agent IS NULL
              AND platform IS NOT DISTINCT FROM %s
              AND browser IS NOT DISTINCT FROM %s
            """,
            (agent, platform, browser),
        )
        written += env.cr.rowcount

    for platform, browser, got_platform, got_browser in skipped:
        openupgrade.message(
            env.cr,
            "base",
            False,
            False,
            "res.device.log rows recorded platform=%s browser=%s in 19.0, but the "
            "user agent built for them parses back as platform=%s browser=%s, so "
            "they were left without one rather than given a wrong device",
            platform,
            browser,
            got_platform,
            got_browser,
        )


def _compose(platform, browser):
    """A user agent for a 19.0 platform/browser pair, always visibly migrated."""
    os_fragment = _PLATFORM_FRAGMENT.get((platform or "").lower())
    browser_fragment = _BROWSER_FRAGMENT.get((browser or "").lower())
    if browser_fragment is None and (browser or "").lower() == "safari":
        browser_fragment = _BROWSER_FRAGMENT["safari"]
    if not os_fragment and not browser_fragment:
        return _MARKER
    parts = ["Mozilla/5.0"]
    if os_fragment:
        parts.append(f"({os_fragment})")
    if browser_fragment:
        parts.append(browser_fragment)
    parts.append(_MARKER)
    return " ".join(parts)


def _translate_boolean_to_selection(env):
    """`ir.model.fields.translate` was a boolean before it was a selection.

    20.0 declares standard / html_translate / xml_translate. A row still holding
    the string 'true' predates that -- it is the boolean form, which meant
    exactly "translate this field as a whole", i.e. `standard`. Nothing raises,
    because a selection is enforced in Python rather than by the database; the
    row simply reads blank in the interface and matches neither branch of a
    domain over the field.

    Found on a real database rather than the test seed: one row, `date.range`'s
    type_name, left behind by a module whose own definitions would have been
    rewritten on reinstall anyway -- but a stale row is still a row the ORM will
    read.
    """
    openupgrade.logged_query(
        env.cr,
        """
        UPDATE ir_model_fields SET translate = 'standard'
        WHERE translate = 'true'
        """,
    )


def _carry_the_bank_record_onto_the_account(env):
    """res.bank is deleted and its address is inlined onto the account.

    19.0 kept the bank as its own record and the account pointed at it with
    bank_id. 20.0 deletes the model outright and adds the fields to
    res.partner.bank under a "# bank fields" block -- bank_name, bank_bic,
    street, street2, zip, city, state_id, country_id -- shown as "Bank Name" and
    "Bank Address" in the form (res_partner_bank_views.xml:38-47).

    Nothing carried the values. Every one of those columns is empty on all 19
    accounts of the seed while the orphaned res_bank table still holds them:
    Odoo drops neither the obsolete table nor the bank_id column, so the join is
    intact and this is recoverable -- but only until someone runs
    database_cleanup.

    country_id is the exception, and it is the reason this is not simply a
    copy. It is a stored precompute and its compute reads the PARTNER::

        if not account.country_id:
            account.country_id = (account.partner_id.country_id
                                  or account.company_id.country_id
                                  or account.env.company.country_id)

    so the upgrade already filled it, from the wrong record: the field sits in
    the bank-address block, and a bank abroad now reads as being in the
    account holder's country. Where res_bank named a country that is written
    over the computed value; where it named none the computed one stands, since
    a partner-derived guess beats an empty address.

    email, phone and active have no destination -- 20.0's res.partner.bank has
    no field for any of them -- so they stay in the orphaned table and are
    reported rather than forced somewhere they do not belong.
    """
    if not openupgrade.table_exists(env.cr, "res_bank"):
        return
    if not openupgrade.column_exists(env.cr, "res_partner_bank", "bank_id"):
        return
    openupgrade.logged_query(
        env.cr,
        """
        UPDATE res_partner_bank a
        SET bank_name = COALESCE(NULLIF(a.bank_name, ''), b.name),
            bank_bic = COALESCE(NULLIF(a.bank_bic, ''), b.bic),
            street = COALESCE(NULLIF(a.street, ''), b.street),
            street2 = COALESCE(NULLIF(a.street2, ''), b.street2),
            zip = COALESCE(NULLIF(a.zip, ''), b.zip),
            city = COALESCE(NULLIF(a.city, ''), b.city),
            state_id = COALESCE(a.state_id, b.state),
            country_id = COALESCE(b.country, a.country_id)
        FROM res_bank b
        WHERE b.id = a.bank_id
        """,
    )
    carried = env.cr.rowcount
    if carried:
        openupgrade.message(
            env.cr,
            "base",
            False,
            False,
            "res.partner.bank: inlined the bank record onto %s account(s) across "
            "the legacy bank_id; 20.0 deleted res.bank without carrying its name, "
            "BIC or address",
            carried,
        )
    env.cr.execute(
        """
        SELECT count(*) FROM res_partner_bank a JOIN res_bank b ON b.id = a.bank_id
        WHERE (b.email IS NOT NULL AND b.email != '')
           OR (b.phone IS NOT NULL AND b.phone != '')
        """
    )
    contactable = env.cr.fetchone()[0]
    if contactable:
        openupgrade.message(
            env.cr,
            "base",
            False,
            False,
            "res.bank: %s account(s) reference a bank that recorded an email or "
            "phone number. 20.0's res.partner.bank has no field for either, so "
            "they were left in the orphaned res_bank table; read them there "
            "before running database_cleanup",
            contactable,
        )


def _carry_the_company_registry_into_additional_identifiers(env):
    """company_registry is dropped for the additional_identifiers Json.

    19.0's field was plain user input -- its compute was the no-op
    `company.company_registry = company.company_registry`, stored and
    readonly=False. 20.0 removes it and keeps company identification in a Json
    keyed by identifier type, whose generic 'OTHER' entry is labelled
    "Company ID" for every country (tools/partner_identifiers.py:952-957),
    which is 19.0's own label.

    WHICH KEY, AND WHY NOT JUST 'OTHER'

    'OTHER' alone would be lossless and invisible.
    _compute_available_additional_identifiers_metadata pops it whenever the
    country offers any other EN-category identifier, and the pop is
    unconditional -- being already stored on the record does not save it
    (res_partner.py:1647-1649). 38 of the 39 EN keys are country-scoped, so for
    a partner in Belgium, France, Germany and 35 other countries the value would
    sit in the Json and appear nowhere in the form.

    So the country's own key is preferred -- but only when the value actually
    fits it. `@api.constrains('additional_identifiers')` revalidates every key
    in the Json with validation='error' (res_partner.py:1378-1385), so a legacy
    free-text registry written under, say, FR_SIREN would make the partner
    unsavable for good. Each candidate is therefore probed first with
    `_validate_identifier(key, value, validation=False)`, which returns
    {valid, value} rather than raising, and the normalised value it returns is
    what gets written.

    A value that fits no candidate falls back to 'OTHER', which has no
    validator, and is reported: hidden beats unsavable, and beats dropped.
    Two countries offer two keys each (FR_SIREN/FR_SIRET, NL_KVK/NL_OIN) and the
    validators discriminate by length, so declaration order settles them.

    Empty on all 840 partners of the prod copy, so the migration test is what
    exercises this.
    """
    if not openupgrade.column_exists(env.cr, "res_partner", "company_registry"):
        return
    env.cr.execute(
        """
        SELECT p.id, p.company_registry, c.code
        FROM res_partner p
        LEFT JOIN res_country c ON c.id = p.country_id
        WHERE p.company_registry IS NOT NULL AND p.company_registry != ''
        """
    )
    rows = env.cr.fetchall()
    if not rows:
        return
    partner_model = env["res.partner"]
    metadata = partner_model._get_all_additional_identifiers_metadata()
    structured = hidden = refused = 0
    for partner_id, registry, country_code in rows:
        candidates = [
            key
            for key, meta in metadata.items()
            if key != "OTHER"
            and meta.get("category") == "EN"
            and country_code
            and country_code in (meta.get("countries") or [])
        ]
        destination, value = "OTHER", registry
        for key in candidates:
            check = partner_model._validate_identifier(key, registry, validation=False)
            if check["valid"]:
                destination, value = key, check["value"]
                break
        partner = partner_model.browse(partner_id)
        try:
            partner.additional_identifiers = {
                **(partner.additional_identifiers or {}),
                destination: value,
            }
        except ValidationError:
            # Something already in the Json fails its own validator, and the
            # constraint checks every key on write. Reported rather than raised:
            # one unparseable legacy identifier must not abort the upgrade.
            refused += 1
            continue
        if destination == "OTHER":
            if candidates:
                hidden += 1
        else:
            structured += 1
    if structured:
        openupgrade.message(
            env.cr,
            "base",
            False,
            False,
            "res.partner: wrote company_registry into additional_identifiers "
            "under the country's own identifier key for %s partner(s)",
            structured,
        )
    if hidden:
        openupgrade.message(
            env.cr,
            "base",
            False,
            False,
            "res.partner: %s partner(s) had a company_registry that fits none of "
            "their country's identifier formats, so it was kept under the generic "
            "'OTHER' key. 20.0 hides that key for any country with an identifier "
            "of its own, so the value is stored but will not show on the form "
            "until someone files it under the right type",
            hidden,
        )
    if refused:
        openupgrade.message(
            env.cr,
            "base",
            False,
            False,
            "res.partner: %s partner(s) already carried an identifier that fails "
            "validation, and the constraint checks the whole Json on write, so "
            "their company_registry could not be added; it remains in the legacy "
            "column",
            refused,
        )


def _apply_the_remembered_table_style(env):
    """Write the table style pre-migration resolved into report_tables_id.

    19.0 hardcoded one table class per report layout and 20.0 lifts it into a
    field of its own, so the documents of every company that did not print with
    the standard layout are restyled by the new field's 'light' default.

    The value comes from the legacy column rather than from
    external_report_layout_id, which by now may be NULL: 20.0 does not ship the
    striped, boxed or bold layouts and web's data load deletes those views. See
    pre-migration for the mapping and its sources.

    The guard is a comparison, not a NULL check. report_tables_id declares a
    default, so adding the column stamped every row -- the same shape as
    hr.version.tz and hr.job.recruiter_id, where guarding on emptiness means
    doing nothing at all.
    """
    legacy = openupgrade.get_legacy_name("report_tables_id")
    if not openupgrade.column_exists(env.cr, "res_company", legacy):
        return
    openupgrade.logged_query(
        env.cr,
        f"""
        UPDATE res_company SET report_tables_id = {legacy}
        WHERE {legacy} IS NOT NULL
          AND report_tables_id IS DISTINCT FROM {legacy}
        """,
    )
    if env.cr.rowcount:
        openupgrade.message(
            env.cr,
            "base",
            False,
            False,
            "res.company: restored the table style of %s company(ies) from the "
            "report layout they printed with in 19.0; 20.0 moved the style into "
            "report_tables_id, whose default would have restyled their documents",
            env.cr.rowcount,
        )


@openupgrade.migrate()
def migrate(env, version):
    openupgrade.load_data(env, "base", "20.0.1.3/noupdate_changes.xml")
    openupgrade.delete_record_translations(
        env.cr,
        "base",
        ["br", "ci", "hk", "id", "kr", "ph", "us"],
        ["vat_label"],
    )
    _synthesise_device_user_agent(env)
    _translate_boolean_to_selection(env)
    _carry_the_bank_record_onto_the_account(env)
    _carry_the_company_registry_into_additional_identifiers(env)
    _apply_the_remembered_table_style(env)
