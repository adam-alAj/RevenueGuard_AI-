"""0002 seed roles and permissions

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-19

This migration seeds the 6 default roles and their permission matrix.
Roles are per-organization — this migration creates role templates that
the registration endpoint copies for each new organization.

The permission matrix defines which roles can perform which actions on
which resources. Resource "*" with action "*" means full access.

"""


from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


# Permission matrix: role_name -> [(resource, action, description)]
PERMISSION_MATRIX = {
    "Owner": [
        ("*", "*", "Full access to all resources and actions"),
    ],
    "Admin": [
        ("users", "read", "View users"),
        ("users", "write", "Invite and manage users"),
        ("customers", "read", "View customers"),
        ("customers", "write", "Create and edit customers"),
        ("contracts", "read", "View contracts"),
        ("contracts", "write", "Create and edit contracts"),
        ("invoices", "read", "View invoices"),
        ("invoices", "write", "Create and edit invoices"),
        ("payments", "read", "View payments"),
        ("payments", "write", "Record and edit payments"),
        ("projects", "read", "View projects"),
        ("projects", "write", "Create and edit projects"),
        ("leakage", "read", "View leakage cases"),
        ("leakage", "write", "Manage leakage cases"),
        ("rules", "read", "View detection rules"),
        ("rules", "write", "Configure detection rules"),
        ("recovery", "read", "View recovery actions"),
        ("recovery", "write", "Manage recovery actions"),
        ("approvals", "read", "View approvals"),
        ("approvals", "write", "Approve and reject cases"),
        ("integrations", "read", "View integrations"),
        ("integrations", "write", "Manage integrations"),
        ("imports", "read", "View import jobs"),
        ("imports", "write", "Create import jobs"),
        ("audit", "read", "View audit logs"),
    ],
    "Finance Manager": [
        ("customers", "read", "View customers"),
        ("contracts", "read", "View contracts"),
        ("invoices", "read", "View invoices"),
        ("invoices", "write", "Create and edit invoices"),
        ("payments", "read", "View payments"),
        ("payments", "write", "Record and edit payments"),
        ("projects", "read", "View projects"),
        ("leakage", "read", "View leakage cases"),
        ("leakage", "write", "Manage leakage cases"),
        ("rules", "read", "View detection rules"),
        ("recovery", "read", "View recovery actions"),
        ("recovery", "write", "Manage recovery actions"),
        ("approvals", "read", "View approvals"),
        ("approvals", "write", "Approve and reject cases"),
        ("imports", "read", "View import jobs"),
        ("imports", "write", "Create import jobs"),
        ("audit", "read", "View audit logs"),
    ],
    "Accountant": [
        ("customers", "read", "View customers"),
        ("contracts", "read", "View contracts"),
        ("invoices", "read", "View invoices"),
        ("invoices", "write", "Create and edit invoices"),
        ("payments", "read", "View payments"),
        ("payments", "write", "Record and edit payments"),
        ("projects", "read", "View projects"),
        ("leakage", "read", "View leakage cases"),
        ("recovery", "read", "View recovery actions"),
        ("imports", "read", "View import jobs"),
        ("imports", "write", "Create import jobs"),
    ],
    "Analyst": [
        ("customers", "read", "View customers"),
        ("contracts", "read", "View contracts"),
        ("invoices", "read", "View invoices"),
        ("payments", "read", "View payments"),
        ("projects", "read", "View projects"),
        ("leakage", "read", "View leakage cases"),
        ("recovery", "read", "View recovery actions"),
        ("rules", "read", "View detection rules"),
        ("audit", "read", "View audit logs"),
    ],
    "Viewer": [
        ("customers", "read", "View customers"),
        ("contracts", "read", "View contracts"),
        ("invoices", "read", "View invoices"),
        ("payments", "read", "View payments"),
        ("projects", "read", "View projects"),
        ("leakage", "read", "View leakage cases"),
    ],
}


def upgrade() -> None:
    # Create permissions table (if not already created by 0001)
    # Permissions are global (not per-org) — they define the available actions.
    op.execute("""
        INSERT INTO permissions (id, resource, action, description, created_at, updated_at)
        SELECT gen_random_uuid(), resource, action, description, NOW(), NOW()
        FROM (VALUES
            ('*', '*', 'Full access to all resources and actions'),
            ('users', 'read', 'View users'),
            ('users', 'write', 'Invite and manage users'),
            ('customers', 'read', 'View customers'),
            ('customers', 'write', 'Create and edit customers'),
            ('contracts', 'read', 'View contracts'),
            ('contracts', 'write', 'Create and edit contracts'),
            ('invoices', 'read', 'View invoices'),
            ('invoices', 'write', 'Create and edit invoices'),
            ('payments', 'read', 'View payments'),
            ('payments', 'write', 'Record and edit payments'),
            ('projects', 'read', 'View projects'),
            ('projects', 'write', 'Create and edit projects'),
            ('leakage', 'read', 'View leakage cases'),
            ('leakage', 'write', 'Manage leakage cases'),
            ('rules', 'read', 'View detection rules'),
            ('rules', 'write', 'Configure detection rules'),
            ('recovery', 'read', 'View recovery actions'),
            ('recovery', 'write', 'Manage recovery actions'),
            ('approvals', 'read', 'View approvals'),
            ('approvals', 'write', 'Approve and reject cases'),
            ('integrations', 'read', 'View integrations'),
            ('integrations', 'write', 'Manage integrations'),
            ('imports', 'read', 'View import jobs'),
            ('imports', 'write', 'Create import jobs'),
            ('audit', 'read', 'View audit logs')
        ) AS v(resource, action, description)
        ON CONFLICT DO NOTHING;
    """)


def downgrade() -> None:
    # Remove seeded permissions
    op.execute("DELETE FROM permissions WHERE resource = '*' AND action = '*'")
    op.execute("""
        DELETE FROM permissions
        WHERE description IN (
            'Full access to all resources and actions',
            'View users', 'Invite and manage users',
            'View customers', 'Create and edit customers',
            'View contracts', 'Create and edit contracts',
            'View invoices', 'Create and edit invoices',
            'View payments', 'Record and edit payments',
            'View projects', 'Create and edit projects',
            'View leakage cases', 'Manage leakage cases',
            'View detection rules', 'Configure detection rules',
            'View recovery actions', 'Manage recovery actions',
            'View approvals', 'Approve and reject cases',
            'View integrations', 'Manage integrations',
            'View import jobs', 'Create import jobs',
            'View audit logs'
        )
    """)
