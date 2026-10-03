env = locals().get("env")

# pos.payment.method.type is computed in 19.0 and stored + required in 20.0, so
# the column starts empty and has to be derived. 19.0's own _compute_type reads
# the JOURNAL, not anything on the method, and falls through to pay_later when
# the journal is neither cash nor bank -- including when there is none. One
# method per branch.
company = env.company
journals = env["account.journal"]


def _journal(kind):
    found = journals.search(
        [("type", "=", kind), ("company_id", "=", company.id)], limit=1
    )
    return found or journals.create(
        {
            "name": f"ou19-{kind}",
            "code": f"OU{kind[:2].upper()}",
            "type": kind,
            "company_id": company.id,
        }
    )


method = env["pos.payment.method"]
method.create(
    {
        "name": "ou19-pm-cash",
        "journal_id": _journal("cash").id,
        "company_id": company.id,
    }
)
method.create(
    {
        "name": "ou19-pm-bank",
        "journal_id": _journal("bank").id,
        "company_id": company.id,
    }
)
# No journal at all: this is the branch is_cash_count cannot distinguish, since
# it is False here and False on a bank method alike.
method.create({"name": "ou19-pm-none", "company_id": company.id})

# --- the two journals that swap jobs -----------------------------------------
# 19.0: journal_id is the SESSION CLOSING journal, invoice_journal_id is the
# journal POS invoices are cut from. 20.0 reverses both. The two are planted
# DIFFERENT from each other, because a config whose journals already matched
# would come out right whether the swap ran or not.
pos_config = env["pos.config"].search([], order="id", limit=1)
assert pos_config, "the seed has no pos.config"
closing_journal = env["account.journal"].create(
    {
        "name": "ou19-pos-closing",
        "code": "OU19C",
        "type": "sale",
        "company_id": pos_config.company_id.id,
    }
)
invoice_journal = env["account.journal"].create(
    {
        "name": "ou19-pos-invoice",
        "code": "OU19I",
        "type": "sale",
        "company_id": pos_config.company_id.id,
    }
)
env.cr.execute(
    "UPDATE pos_config SET journal_id = %s, invoice_journal_id = %s WHERE id = %s",
    (closing_journal.id, invoice_journal.id, pos_config.id),
)
for record, name in (
    (pos_config, "ou19_pos_config"),
    (closing_journal, "ou19_pos_closing_journal"),
    (invoice_journal, "ou19_pos_invoice_journal"),
):
    env["ir.model.data"].create(
        {
            "module": "__ou19__",
            "name": name,
            "model": record._name,
            "res_id": record.id,
        }
    )

env.cr.commit()
