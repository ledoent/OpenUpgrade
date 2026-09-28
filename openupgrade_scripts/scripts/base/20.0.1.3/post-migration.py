# Copyright 2026 Don Kendall
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

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
