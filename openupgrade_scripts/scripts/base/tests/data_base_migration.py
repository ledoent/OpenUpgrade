env = locals().get("env")
# server action with multiple children
parent_action1 = env["ir.actions.server"].create(
    {
        "name": "test server action 1",
        "state": "multi",
        "model_id": env.ref("base.model_ir_module_module").id,
        "child_ids": [
            (
                0,
                0,
                {
                    "name": "child action 1",
                    "model_id": env.ref("base.model_ir_module_module").id,
                },
            ),
            (
                0,
                0,
                {
                    "name": "child action 2",
                    "model_id": env.ref("base.model_ir_module_module").id,
                },
            ),
        ],
    }
)
parent_action1.copy(
    {
        "name": "test server action 2",
        "child_ids": [
            (6, 0, parent_action1.child_ids.ids),
            (
                0,
                0,
                {
                    "name": "child action 3",
                    "model_id": env.ref("base.model_ir_module_module").id,
                },
            ),
        ],
    }
)

# Search-view fixtures for the 19.0 RNG attribute strip helper.
# `expand=` on <group>/<field> and `string="Group By"` on <group>
# were valid in 18.0 but rejected by 19.0's stricter RelaxNG schema.
env["ir.ui.view"].create(
    {
        "name": "test search group_expand",
        "model": "res.partner",
        "type": "search",
        "arch": """
            <search>
                <field name="name"/>
                <group expand="0" string="Group By">
                    <filter
                        string="Country"
                        name="country"
                        context="{'group_by': 'country_id'}"
                    />
                </group>
            </search>
        """,
    }
)
env["ir.ui.view"].create(
    {
        "name": "test search field_expand",
        "model": "res.partner",
        "type": "search",
        "arch": """
            <search>
                <field name="name"/>
                <searchpanel>
                    <field name="country_id" expand="1" select="multi"/>
                </searchpanel>
            </search>
        """,
    }
)
env.cr.commit()
