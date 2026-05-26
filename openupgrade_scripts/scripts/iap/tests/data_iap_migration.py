env = locals().get("env")

# Recreate the upgrade-scarred shape (preserved legacy column + unlinked row)
# so the post-migration backfill has rows to move on the fresh CI seed.
env.cr.execute(
    "ALTER TABLE iap_account "
    "ADD COLUMN IF NOT EXISTS openupgrade_legacy_18_0_service_name varchar"
)
env.cr.execute("ALTER TABLE iap_account ALTER COLUMN service_id DROP NOT NULL")
env.cr.execute(
    """
    INSERT INTO iap_account (openupgrade_legacy_18_0_service_name)
    SELECT s.technical_name FROM iap_service s
    WHERE NOT EXISTS (
        SELECT 1 FROM iap_account
        WHERE openupgrade_legacy_18_0_service_name IS NOT NULL)
    LIMIT 1
    """
)
env.cr.commit()
