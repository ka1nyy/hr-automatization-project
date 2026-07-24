-- =====================================================================
-- SPK Ertis Corporate HR API — PostgreSQL schema
-- =====================================================================
-- Auto-generated from the SQLAlchemy ORM models (app.models / Base.metadata)
-- using the PostgreSQL (psycopg) dialect. Matches exactly what Alembic
-- migrates: every model registered in Base.metadata is included (94 tables).
--
-- Target database: PostgreSQL (see SPK_DATABASE_URL, default db "spk_hr").
-- Tables are emitted in dependency order; the trailing ALTER TABLE resolves
-- a circular foreign key (employees <-> user_accounts).
--
-- Notes:
--   * All enum-like columns are stored as VARCHAR (no native PG ENUM types).
--   * UUID columns use the native "uuid" type; IIN is stored encrypted (BYTEA).
--   * Timestamps are TIMESTAMP WITH TIME ZONE.
-- =====================================================================

-- Required for the GiST EXCLUDE constraints below, which use the "=" operator
-- on scalar (uuid/text) columns alongside a range && operator. Without this
-- extension PostgreSQL raises:
--   ERROR: data type uuid has no default operator class for access method "gist"
CREATE EXTENSION IF NOT EXISTS btree_gist;

CREATE TABLE audit_events (
	organization_id UUID, 
	actor_id UUID, 
	action VARCHAR(100) NOT NULL, 
	entity_type VARCHAR(100) NOT NULL, 
	entity_id UUID NOT NULL, 
	before_state JSONB, 
	after_state JSONB, 
	reason TEXT, 
	request_id UUID, 
	occurred_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	id UUID NOT NULL, 
	CONSTRAINT pk_audit_events PRIMARY KEY (id)
);

CREATE INDEX ix_audit_events_entity_type ON audit_events (entity_type);

CREATE INDEX ix_audit_events_organization_occurred ON audit_events (organization_id, occurred_at);

CREATE INDEX ix_audit_events_actor_occurred ON audit_events (actor_id, occurred_at);

CREATE INDEX ix_audit_events_actor_id ON audit_events (actor_id);

CREATE INDEX ix_audit_events_organization_id ON audit_events (organization_id);

CREATE INDEX ix_audit_events_entity_id ON audit_events (entity_id);

CREATE INDEX ix_audit_events_request_id ON audit_events (request_id);

CREATE INDEX ix_audit_events_entity ON audit_events (entity_type, entity_id, occurred_at);

CREATE INDEX ix_audit_events_action ON audit_events (action);

CREATE TABLE outbox_events (
	event_name VARCHAR(100) NOT NULL, 
	aggregate_type VARCHAR(100) NOT NULL, 
	aggregate_id UUID NOT NULL, 
	payload JSONB NOT NULL, 
	schema_version INTEGER NOT NULL, 
	occurred_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	available_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	processed_at TIMESTAMP WITH TIME ZONE, 
	attempts INTEGER DEFAULT '0' NOT NULL, 
	last_error TEXT, 
	id UUID NOT NULL, 
	CONSTRAINT pk_outbox_events PRIMARY KEY (id), 
	CONSTRAINT ck_outbox_events_attempts_nonnegative CHECK (attempts >= 0), 
	CONSTRAINT ck_outbox_events_schema_version_positive CHECK (schema_version >= 1)
);

CREATE INDEX ix_outbox_events_aggregate_id ON outbox_events (aggregate_id);

CREATE INDEX ix_outbox_events_pending ON outbox_events (available_at, occurred_at) WHERE processed_at IS NULL;

CREATE TABLE permissions (
	id UUID NOT NULL, 
	code VARCHAR(128) NOT NULL, 
	name VARCHAR(255) NOT NULL, 
	description TEXT NOT NULL, 
	active BOOLEAN DEFAULT true NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	CONSTRAINT pk_permissions PRIMARY KEY (id), 
	CONSTRAINT uq_permissions_code UNIQUE (code)
);

CREATE INDEX ix_permissions_active ON permissions (active);

CREATE TABLE people (
	id UUID NOT NULL, 
	first_name VARCHAR(160) NOT NULL, 
	last_name VARCHAR(160) NOT NULL, 
	middle_name VARCHAR(160), 
	display_name VARCHAR(500) NOT NULL, 
	protected_iin BYTEA, 
	birth_date DATE, 
	personal_email VARCHAR(320), 
	phone VARCHAR(80), 
	status VARCHAR(32) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	revision INTEGER NOT NULL, 
	CONSTRAINT pk_people PRIMARY KEY (id)
);

CREATE TABLE organizations (
	id UUID NOT NULL, 
	code VARCHAR(64) NOT NULL, 
	legal_name VARCHAR(255) NOT NULL, 
	display_name VARCHAR(255) NOT NULL, 
	status VARCHAR(32) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	CONSTRAINT pk_organizations PRIMARY KEY (id), 
	CONSTRAINT uq_organizations_code UNIQUE (code)
);

CREATE INDEX ix_organizations_status ON organizations (status);

CREATE TABLE leave_types (
	organization_id UUID NOT NULL, 
	code VARCHAR(80) NOT NULL, 
	name VARCHAR(250) NOT NULL, 
	paid BOOLEAN NOT NULL, 
	requires_balance BOOLEAN NOT NULL, 
	active BOOLEAN NOT NULL, 
	id UUID NOT NULL, 
	revision INTEGER NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_leave_types PRIMARY KEY (id), 
	CONSTRAINT uq_leave_types_organization_id_code UNIQUE (organization_id, code), 
	CONSTRAINT fk_leave_types_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT
);

CREATE INDEX ix_leave_types_organization_id ON leave_types (organization_id);

CREATE TABLE roles (
	id UUID NOT NULL, 
	organization_id UUID, 
	code VARCHAR(128) NOT NULL, 
	name VARCHAR(255) NOT NULL, 
	description TEXT, 
	active BOOLEAN DEFAULT true NOT NULL, 
	system BOOLEAN DEFAULT false NOT NULL, 
	revision INTEGER DEFAULT 1 NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	CONSTRAINT pk_roles PRIMARY KEY (id), 
	CONSTRAINT ck_roles_ck_roles_revision_positive CHECK (revision > 0), 
	CONSTRAINT fk_roles_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT
);

CREATE UNIQUE INDEX uq_roles_global_code ON roles (code) WHERE organization_id IS NULL;

CREATE INDEX ix_roles_organization_id ON roles (organization_id);

CREATE UNIQUE INDEX uq_roles_organization_code ON roles (organization_id, code) WHERE organization_id IS NOT NULL;

CREATE INDEX ix_roles_active ON roles (active);

CREATE TABLE access_scopes (
	id UUID NOT NULL, 
	scope_type VARCHAR(40) NOT NULL, 
	organization_id UUID, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	CONSTRAINT pk_access_scopes PRIMARY KEY (id), 
	CONSTRAINT ck_access_scopes_ck_access_scopes_organization_required CHECK (organization_id IS NOT NULL), 
	CONSTRAINT fk_access_scopes_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT
);

CREATE INDEX ix_access_scopes_organization ON access_scopes (organization_id, scope_type);

CREATE INDEX ix_access_scopes_organization_id ON access_scopes (organization_id);

CREATE TABLE document_types (
	organization_id UUID NOT NULL, 
	code VARCHAR(120) NOT NULL, 
	name VARCHAR(300) NOT NULL, 
	description TEXT, 
	default_confidentiality VARCHAR(30) NOT NULL, 
	allowed_mime_types JSONB NOT NULL, 
	maximum_size_bytes INTEGER NOT NULL, 
	active BOOLEAN NOT NULL, 
	id UUID NOT NULL, 
	revision INTEGER NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_document_types PRIMARY KEY (id), 
	CONSTRAINT uq_document_types_organization_id_code UNIQUE (organization_id, code), 
	CONSTRAINT fk_document_types_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT
);

CREATE INDEX ix_document_types_organization_id ON document_types (organization_id);

CREATE TABLE employees (
	id UUID NOT NULL, 
	organization_id UUID NOT NULL, 
	created_by UUID NOT NULL, 
	person_id UUID NOT NULL, 
	employee_number VARCHAR(64) NOT NULL, 
	employment_status VARCHAR(32) NOT NULL, 
	position_title VARCHAR(255), 
	department_name VARCHAR(255), 
	manager_name VARCHAR(500), 
	employment_type_label VARCHAR(128), 
	hire_date DATE NOT NULL, 
	probation_end DATE, 
	termination_date DATE, 
	corporate_email VARCHAR(320), 
	active BOOLEAN NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	revision INTEGER NOT NULL, 
	CONSTRAINT pk_employees PRIMARY KEY (id), 
	CONSTRAINT uq_employees_organization_number UNIQUE (organization_id, employee_number), 
	CONSTRAINT uq_employees_organization_person UNIQUE (organization_id, person_id), 
	CONSTRAINT ck_employees_ck_employees_valid_dates CHECK (termination_date IS NULL OR termination_date >= hire_date), 
	CONSTRAINT fk_employees_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_employees_person_id_people FOREIGN KEY(person_id) REFERENCES people (id) ON DELETE RESTRICT
);

CREATE INDEX ix_employees_organization_active_status ON employees (organization_id, active, employment_status);

CREATE TABLE organization_unit_types (
	id UUID NOT NULL, 
	organization_id UUID NOT NULL, 
	code VARCHAR(64) NOT NULL, 
	name VARCHAR(255) NOT NULL, 
	description TEXT, 
	active BOOLEAN DEFAULT true NOT NULL, 
	custom_fields_schema JSONB DEFAULT '{}'::jsonb NOT NULL, 
	revision INTEGER DEFAULT 1 NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	CONSTRAINT pk_organization_unit_types PRIMARY KEY (id), 
	CONSTRAINT uq_organization_unit_types_code UNIQUE (organization_id, code), 
	CONSTRAINT ck_organization_unit_types_ck_organization_unit_types_r_9aa8 CHECK (revision > 0), 
	CONSTRAINT fk_organization_unit_types_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT
);

CREATE INDEX ix_organization_unit_types_active ON organization_unit_types (organization_id, active);

CREATE TABLE organization_relationship_types (
	id UUID NOT NULL, 
	organization_id UUID NOT NULL, 
	code VARCHAR(64) NOT NULL, 
	name VARCHAR(255) NOT NULL, 
	description TEXT, 
	directed BOOLEAN DEFAULT true NOT NULL, 
	prevents_cycles BOOLEAN DEFAULT false NOT NULL, 
	allow_self_link BOOLEAN DEFAULT false NOT NULL, 
	active BOOLEAN DEFAULT true NOT NULL, 
	metadata_schema JSONB DEFAULT '{}'::jsonb NOT NULL, 
	revision INTEGER DEFAULT 1 NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	CONSTRAINT pk_organization_relationship_types PRIMARY KEY (id), 
	CONSTRAINT uq_organization_relationship_types_code UNIQUE (organization_id, code), 
	CONSTRAINT ck_organization_relationship_types_ck_organization_rela_e320 CHECK (revision > 0), 
	CONSTRAINT fk_organization_relationship_types_organization_id_orga_81c4 FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT
);

CREATE INDEX ix_organization_relationship_types_active ON organization_relationship_types (organization_id, active);

CREATE TABLE position_definitions (
	id UUID NOT NULL, 
	organization_id UUID NOT NULL, 
	code VARCHAR(64) NOT NULL, 
	name VARCHAR(255) NOT NULL, 
	description TEXT, 
	job_family VARCHAR(128), 
	grade VARCHAR(64), 
	active BOOLEAN DEFAULT true NOT NULL, 
	custom_fields JSONB DEFAULT '{}'::jsonb NOT NULL, 
	revision INTEGER DEFAULT 1 NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	CONSTRAINT pk_position_definitions PRIMARY KEY (id), 
	CONSTRAINT uq_position_definitions_organization_code UNIQUE (organization_id, code), 
	CONSTRAINT ck_position_definitions_ck_position_definitions_revisio_3986 CHECK (revision > 0), 
	CONSTRAINT fk_position_definitions_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT
);

CREATE INDEX ix_position_definitions_active ON position_definitions (organization_id, active);

CREATE INDEX ix_position_definitions_job_family ON position_definitions (organization_id, job_family);

CREATE TABLE vacancy_publication_channels (
	organization_id UUID NOT NULL, 
	code VARCHAR(100) NOT NULL, 
	name VARCHAR(300) NOT NULL, 
	channel_type VARCHAR(50) NOT NULL, 
	active BOOLEAN NOT NULL, 
	id UUID NOT NULL, 
	revision INTEGER NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_vacancy_publication_channels PRIMARY KEY (id), 
	CONSTRAINT uq_vacancy_publication_channels_organization_id_code UNIQUE (organization_id, code), 
	CONSTRAINT fk_vacancy_publication_channels_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT
);

CREATE TABLE candidates (
	organization_id UUID NOT NULL, 
	first_name VARCHAR(160) NOT NULL, 
	last_name VARCHAR(160) NOT NULL, 
	middle_name VARCHAR(160), 
	display_name VARCHAR(500) NOT NULL, 
	protected_personal_email TEXT, 
	protected_phone TEXT, 
	protected_identity TEXT, 
	source VARCHAR(100) NOT NULL, 
	consent_status VARCHAR(30) NOT NULL, 
	consent_at TIMESTAMP WITH TIME ZONE, 
	retention_until DATE, 
	status VARCHAR(30) NOT NULL, 
	anonymized_at TIMESTAMP WITH TIME ZONE, 
	id UUID NOT NULL, 
	revision INTEGER NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_candidates PRIMARY KEY (id), 
	CONSTRAINT fk_candidates_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT
);

CREATE INDEX ix_candidates_org_status ON candidates (organization_id, status);

CREATE TABLE normative_sources (
	organization_id UUID NOT NULL, 
	code VARCHAR(100) NOT NULL, 
	title VARCHAR(500) NOT NULL, 
	source_type VARCHAR(50) NOT NULL, 
	authority_status VARCHAR(30) NOT NULL, 
	file_reference VARCHAR(1000), 
	effective_from DATE, 
	approved_at TIMESTAMP WITH TIME ZONE, 
	notes TEXT, 
	id UUID NOT NULL, 
	revision INTEGER NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_normative_sources PRIMARY KEY (id), 
	CONSTRAINT uq_normative_sources_organization_id_code UNIQUE (organization_id, code), 
	CONSTRAINT fk_normative_sources_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT
);

CREATE INDEX ix_normative_sources_organization_id ON normative_sources (organization_id);

CREATE INDEX ix_normative_sources_authority_status ON normative_sources (authority_status);

CREATE TABLE termination_reasons (
	organization_id UUID NOT NULL, 
	code VARCHAR(100) NOT NULL, 
	name VARCHAR(300) NOT NULL, 
	legal_review_required BOOLEAN NOT NULL, 
	employee_initiated BOOLEAN NOT NULL, 
	active BOOLEAN NOT NULL, 
	id UUID NOT NULL, 
	revision INTEGER NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_termination_reasons PRIMARY KEY (id), 
	CONSTRAINT uq_termination_reasons_organization_id_code UNIQUE (organization_id, code), 
	CONSTRAINT fk_termination_reasons_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT
);

CREATE TABLE time_codes (
	organization_id UUID NOT NULL, 
	code VARCHAR(20) NOT NULL, 
	name VARCHAR(300) NOT NULL, 
	category VARCHAR(30) NOT NULL, 
	paid BOOLEAN NOT NULL, 
	counts_as_worked_time BOOLEAN NOT NULL, 
	external_code VARCHAR(50), 
	active BOOLEAN NOT NULL, 
	id UUID NOT NULL, 
	revision INTEGER NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_time_codes PRIMARY KEY (id), 
	CONSTRAINT uq_time_codes_organization_code UNIQUE (organization_id, code), 
	CONSTRAINT fk_time_codes_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT
);

CREATE INDEX ix_time_codes_organization_active ON time_codes (organization_id, active);

CREATE INDEX ix_time_codes_organization_id ON time_codes (organization_id);

CREATE TABLE process_definitions (
	organization_id UUID NOT NULL, 
	code VARCHAR(100) NOT NULL, 
	name VARCHAR(300) NOT NULL, 
	description TEXT, 
	active BOOLEAN NOT NULL, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_process_definitions PRIMARY KEY (id), 
	CONSTRAINT uq_process_definitions_organization_id_code UNIQUE (organization_id, code), 
	CONSTRAINT fk_process_definitions_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT
);

CREATE INDEX ix_process_definitions_organization_id ON process_definitions (organization_id);

CREATE TABLE form_definitions (
	organization_id UUID NOT NULL, 
	code VARCHAR(100) NOT NULL, 
	name VARCHAR(300) NOT NULL, 
	active BOOLEAN NOT NULL, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_form_definitions PRIMARY KEY (id), 
	CONSTRAINT uq_form_definitions_organization_id_code UNIQUE (organization_id, code), 
	CONSTRAINT fk_form_definitions_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT
);

CREATE TABLE leave_balances (
	organization_id UUID NOT NULL, 
	employee_id UUID NOT NULL, 
	leave_type_id UUID NOT NULL, 
	year INTEGER NOT NULL, 
	entitled_days NUMERIC(7, 2) NOT NULL, 
	carried_days NUMERIC(7, 2) NOT NULL, 
	reserved_days NUMERIC(7, 2) NOT NULL, 
	used_days NUMERIC(7, 2) NOT NULL, 
	id UUID NOT NULL, 
	revision INTEGER NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_leave_balances PRIMARY KEY (id), 
	CONSTRAINT uq_leave_balances_employee_id_leave_type_id_year UNIQUE (employee_id, leave_type_id, year), 
	CONSTRAINT fk_leave_balances_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_leave_balances_employee_id_employees FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_leave_balances_leave_type_id_leave_types FOREIGN KEY(leave_type_id) REFERENCES leave_types (id) ON DELETE RESTRICT
);

CREATE INDEX ix_leave_balances_organization_id ON leave_balances (organization_id);

CREATE INDEX ix_leave_balances_employee_id ON leave_balances (employee_id);

CREATE TABLE document_templates (
	organization_id UUID NOT NULL, 
	document_type_id UUID NOT NULL, 
	code VARCHAR(120) NOT NULL, 
	name VARCHAR(300) NOT NULL, 
	active BOOLEAN NOT NULL, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_document_templates PRIMARY KEY (id), 
	CONSTRAINT uq_document_templates_organization_id_code UNIQUE (organization_id, code), 
	CONSTRAINT fk_document_templates_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_document_templates_document_type_id_document_types FOREIGN KEY(document_type_id) REFERENCES document_types (id) ON DELETE RESTRICT
);

CREATE INDEX ix_document_templates_organization_id ON document_templates (organization_id);

CREATE TABLE employee_absences (
	id UUID NOT NULL, 
	employee_id UUID NOT NULL, 
	absence_type VARCHAR(32) NOT NULL, 
	date_from DATE NOT NULL, 
	date_to DATE NOT NULL, 
	reason VARCHAR(1000) NOT NULL, 
	details VARCHAR(300), 
	status VARCHAR(16) NOT NULL, 
	created_by UUID NOT NULL, 
	source_document_id UUID, 
	source_type VARCHAR(40), 
	source_id UUID, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	revision INTEGER DEFAULT 1 NOT NULL, 
	CONSTRAINT pk_employee_absences PRIMARY KEY (id), 
	CONSTRAINT ck_employee_absences_ck_absences_valid_dates CHECK (date_to >= date_from), 
	CONSTRAINT uq_employee_absences_source UNIQUE (source_type, source_id), 
	CONSTRAINT fk_employee_absences_employee_id_employees FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE RESTRICT
);

CREATE INDEX ix_absences_status_dates ON employee_absences (status, date_from, date_to);

CREATE INDEX ix_absences_employee_dates ON employee_absences (employee_id, date_from, date_to);

CREATE TABLE delegations (
	id UUID NOT NULL, 
	delegator_employee_id UUID NOT NULL, 
	delegate_employee_id UUID NOT NULL, 
	scope_type VARCHAR(40) NOT NULL, 
	scope_reference VARCHAR(500), 
	delegated_permissions JSONB NOT NULL, 
	effective_from TIMESTAMP WITH TIME ZONE NOT NULL, 
	effective_to TIMESTAMP WITH TIME ZONE NOT NULL, 
	reason TEXT NOT NULL, 
	source_document_id UUID, 
	status VARCHAR(32) NOT NULL, 
	created_by UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	revoked_at TIMESTAMP WITH TIME ZONE, 
	revision INTEGER NOT NULL, 
	metadata JSONB NOT NULL, 
	CONSTRAINT pk_delegations PRIMARY KEY (id), 
	CONSTRAINT ck_delegations_ck_delegations_distinct_employees CHECK (delegator_employee_id <> delegate_employee_id), 
	CONSTRAINT ck_delegations_ck_delegations_valid_dates CHECK (effective_to > effective_from), 
	CONSTRAINT fk_delegations_delegator_employee_id_employees FOREIGN KEY(delegator_employee_id) REFERENCES employees (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_delegations_delegate_employee_id_employees FOREIGN KEY(delegate_employee_id) REFERENCES employees (id) ON DELETE RESTRICT
);

CREATE INDEX ix_delegations_delegator_effective ON delegations (delegator_employee_id, effective_from, effective_to);

CREATE INDEX ix_delegations_delegate_effective ON delegations (delegate_employee_id, effective_from, effective_to);

CREATE TABLE user_accounts (
	id UUID NOT NULL, 
	external_subject VARCHAR(255) NOT NULL, 
	username VARCHAR(150) NOT NULL, 
	email VARCHAR(320), 
	display_name VARCHAR(255) NOT NULL, 
	employee_id UUID, 
	status VARCHAR(32) NOT NULL, 
	active BOOLEAN DEFAULT true NOT NULL, 
	last_login_at TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	revision INTEGER DEFAULT 1 NOT NULL, 
	CONSTRAINT pk_user_accounts PRIMARY KEY (id), 
	CONSTRAINT ck_user_accounts_ck_user_accounts_revision_positive CHECK (revision > 0), 
	CONSTRAINT fk_user_accounts_employee_id_employees FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE SET NULL
);

CREATE UNIQUE INDEX uq_user_accounts_username_active ON user_accounts (username) WHERE active;

CREATE INDEX ix_user_accounts_employee_id ON user_accounts (employee_id);

CREATE UNIQUE INDEX uq_user_accounts_external_subject_active ON user_accounts (external_subject) WHERE active;

CREATE TABLE organization_unit_type_allowed_parents (
	unit_type_id UUID NOT NULL, 
	parent_type_id UUID NOT NULL, 
	CONSTRAINT pk_organization_unit_type_allowed_parents PRIMARY KEY (unit_type_id, parent_type_id), 
	CONSTRAINT fk_organization_unit_type_allowed_parents_unit_type_id__9b5e FOREIGN KEY(unit_type_id) REFERENCES organization_unit_types (id) ON DELETE CASCADE, 
	CONSTRAINT fk_organization_unit_type_allowed_parents_parent_type_i_32e5 FOREIGN KEY(parent_type_id) REFERENCES organization_unit_types (id) ON DELETE RESTRICT
);

CREATE TABLE authority_bindings (
	organization_id UUID NOT NULL, 
	entity_type VARCHAR(80) NOT NULL, 
	entity_id UUID NOT NULL, 
	authority_status VARCHAR(30) NOT NULL, 
	source_id UUID, 
	assertion TEXT NOT NULL, 
	effective_from DATE NOT NULL, 
	effective_to DATE, 
	granted_permissions JSONB NOT NULL, 
	id UUID NOT NULL, 
	revision INTEGER NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_authority_bindings PRIMARY KEY (id), 
	CONSTRAINT uq_authority_bindings_organization_id_entity_type_entit_75dc UNIQUE (organization_id, entity_type, entity_id, effective_from), 
	CONSTRAINT fk_authority_bindings_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_authority_bindings_source_id_normative_sources FOREIGN KEY(source_id) REFERENCES normative_sources (id) ON DELETE RESTRICT
);

CREATE INDEX ix_authority_bindings_entity_id ON authority_bindings (entity_id);

CREATE INDEX ix_authority_bindings_organization_id ON authority_bindings (organization_id);

CREATE INDEX ix_authority_bindings_authority_status ON authority_bindings (authority_status);

CREATE INDEX ix_authority_bindings_entity ON authority_bindings (entity_type, entity_id, authority_status);

CREATE TABLE regulated_hiring_stage_definitions (
	organization_id UUID NOT NULL, 
	source_id UUID, 
	version_number INTEGER NOT NULL, 
	sequence INTEGER NOT NULL, 
	code VARCHAR(100) NOT NULL, 
	name VARCHAR(300) NOT NULL, 
	owner_role_code VARCHAR(100) NOT NULL, 
	sla_min_days INTEGER, 
	sla_max_days INTEGER, 
	working_days BOOLEAN NOT NULL, 
	entry_criteria JSONB NOT NULL, 
	exit_criteria JSONB NOT NULL, 
	active BOOLEAN NOT NULL, 
	id UUID NOT NULL, 
	revision INTEGER NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_regulated_hiring_stage_definitions PRIMARY KEY (id), 
	CONSTRAINT uq_regulated_hiring_stage_definitions_organization_id_c_7ccc UNIQUE (organization_id, code, version_number), 
	CONSTRAINT uq_regulated_hiring_stage_definitions_organization_id_s_4745 UNIQUE (organization_id, sequence, version_number), 
	CONSTRAINT ck_regulated_hiring_stage_definitions_regulated_hiring__668d CHECK (sequence >= 0 AND sequence <= 22), 
	CONSTRAINT ck_regulated_hiring_stage_definitions_regulated_hiring__d81d CHECK (version_number > 0), 
	CONSTRAINT fk_regulated_hiring_stage_definitions_organization_id_o_93f8 FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_regulated_hiring_stage_definitions_source_id_normati_afab FOREIGN KEY(source_id) REFERENCES normative_sources (id) ON DELETE RESTRICT
);

CREATE INDEX ix_regulated_hiring_stage_definitions_organization_id ON regulated_hiring_stage_definitions (organization_id);

CREATE TABLE regulated_hiring_form_definitions (
	organization_id UUID NOT NULL, 
	source_id UUID, 
	version_number INTEGER NOT NULL, 
	sequence INTEGER NOT NULL, 
	code VARCHAR(30) NOT NULL, 
	name VARCHAR(500) NOT NULL, 
	owner_role_code VARCHAR(100) NOT NULL, 
	signer_role_codes JSONB NOT NULL, 
	data_schema JSONB NOT NULL, 
	immutable_after_signing BOOLEAN NOT NULL, 
	active BOOLEAN NOT NULL, 
	id UUID NOT NULL, 
	revision INTEGER NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_regulated_hiring_form_definitions PRIMARY KEY (id), 
	CONSTRAINT uq_regulated_hiring_form_definitions_organization_id_co_58bb UNIQUE (organization_id, code, version_number), 
	CONSTRAINT ck_regulated_hiring_form_definitions_regulated_hiring_f_aa19 CHECK (sequence >= 1 AND sequence <= 21), 
	CONSTRAINT fk_regulated_hiring_form_definitions_organization_id_or_8e1a FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_regulated_hiring_form_definitions_source_id_normativ_48b0 FOREIGN KEY(source_id) REFERENCES normative_sources (id) ON DELETE RESTRICT
);

CREATE INDEX ix_regulated_hiring_form_definitions_organization_id ON regulated_hiring_form_definitions (organization_id);

CREATE TABLE work_schedules (
	organization_id UUID NOT NULL, 
	code VARCHAR(100) NOT NULL, 
	name VARCHAR(300) NOT NULL, 
	kind VARCHAR(30) NOT NULL, 
	cycle_length_days INTEGER NOT NULL, 
	weekly_hours NUMERIC(5, 2), 
	default_time_code_id UUID, 
	active BOOLEAN NOT NULL, 
	id UUID NOT NULL, 
	revision INTEGER NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_work_schedules PRIMARY KEY (id), 
	CONSTRAINT uq_work_schedules_organization_code UNIQUE (organization_id, code), 
	CONSTRAINT ck_work_schedules_cycle_positive CHECK (cycle_length_days > 0), 
	CONSTRAINT ck_work_schedules_weekly_hours_positive CHECK (weekly_hours IS NULL OR weekly_hours > 0), 
	CONSTRAINT fk_work_schedules_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_work_schedules_default_time_code_id_time_codes FOREIGN KEY(default_time_code_id) REFERENCES time_codes (id) ON DELETE RESTRICT
);

CREATE INDEX ix_work_schedules_organization_id ON work_schedules (organization_id);

CREATE TABLE role_permissions (
	role_id UUID NOT NULL, 
	permission_id UUID NOT NULL, 
	granted_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	granted_by UUID, 
	CONSTRAINT pk_role_permissions PRIMARY KEY (role_id, permission_id), 
	CONSTRAINT fk_role_permissions_role_id_roles FOREIGN KEY(role_id) REFERENCES roles (id) ON DELETE CASCADE, 
	CONSTRAINT fk_role_permissions_permission_id_permissions FOREIGN KEY(permission_id) REFERENCES permissions (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_role_permissions_granted_by_user_accounts FOREIGN KEY(granted_by) REFERENCES user_accounts (id) ON DELETE SET NULL
);

CREATE INDEX ix_role_permissions_permission_id ON role_permissions (permission_id);

CREATE TABLE user_role_assignments (
	id UUID NOT NULL, 
	user_id UUID NOT NULL, 
	role_id UUID NOT NULL, 
	scope_id UUID NOT NULL, 
	effective_from TIMESTAMP WITH TIME ZONE NOT NULL, 
	effective_to TIMESTAMP WITH TIME ZONE, 
	created_by UUID, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	revoked_at TIMESTAMP WITH TIME ZONE, 
	revoked_by UUID, 
	revocation_reason TEXT, 
	revision INTEGER DEFAULT 1 NOT NULL, 
	CONSTRAINT pk_user_role_assignments PRIMARY KEY (id), 
	CONSTRAINT ck_user_role_assignments_ck_user_role_assignments_effec_5393 CHECK (effective_to IS NULL OR effective_to > effective_from), 
	CONSTRAINT ck_user_role_assignments_ck_user_role_assignments_revis_a777 CHECK (revision > 0), 
	CONSTRAINT fk_user_role_assignments_user_id_user_accounts FOREIGN KEY(user_id) REFERENCES user_accounts (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_user_role_assignments_role_id_roles FOREIGN KEY(role_id) REFERENCES roles (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_user_role_assignments_scope_id_access_scopes FOREIGN KEY(scope_id) REFERENCES access_scopes (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_user_role_assignments_created_by_user_accounts FOREIGN KEY(created_by) REFERENCES user_accounts (id) ON DELETE SET NULL, 
	CONSTRAINT fk_user_role_assignments_revoked_by_user_accounts FOREIGN KEY(revoked_by) REFERENCES user_accounts (id) ON DELETE SET NULL
);

CREATE INDEX ix_user_role_assignments_user_effective ON user_role_assignments (user_id, effective_from, effective_to);

CREATE INDEX ix_user_role_assignments_active ON user_role_assignments (user_id, role_id) WHERE revoked_at IS NULL;

CREATE TABLE document_template_versions (
	template_id UUID NOT NULL, 
	version_number INTEGER NOT NULL, 
	status VARCHAR(30) NOT NULL, 
	based_on_version_id UUID, 
	storage_key VARCHAR(1000) NOT NULL, 
	content_sha256 VARCHAR(64) NOT NULL, 
	variable_schema JSONB NOT NULL, 
	created_by UUID NOT NULL, 
	published_by UUID, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	published_at TIMESTAMP WITH TIME ZONE, 
	id UUID NOT NULL, 
	revision INTEGER NOT NULL, 
	CONSTRAINT pk_document_template_versions PRIMARY KEY (id), 
	CONSTRAINT uq_document_template_versions_template_id_version_number UNIQUE (template_id, version_number), 
	CONSTRAINT fk_document_template_versions_template_id_document_templates FOREIGN KEY(template_id) REFERENCES document_templates (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_document_template_versions_based_on_version_id_docum_409d FOREIGN KEY(based_on_version_id) REFERENCES document_template_versions (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_document_template_versions_created_by_user_accounts FOREIGN KEY(created_by) REFERENCES user_accounts (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_document_template_versions_published_by_user_accounts FOREIGN KEY(published_by) REFERENCES user_accounts (id) ON DELETE RESTRICT
);

CREATE INDEX ix_document_template_versions_template_id ON document_template_versions (template_id);

CREATE TABLE organization_structure_versions (
	id UUID NOT NULL, 
	organization_id UUID NOT NULL, 
	version_number INTEGER NOT NULL, 
	name VARCHAR(255) NOT NULL, 
	status VARCHAR(32) NOT NULL, 
	based_on_version_id UUID, 
	effective_from DATE, 
	effective_to DATE, 
	revision INTEGER DEFAULT 1 NOT NULL, 
	created_by UUID NOT NULL, 
	published_by UUID, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	published_at TIMESTAMP WITH TIME ZONE, 
	CONSTRAINT pk_organization_structure_versions PRIMARY KEY (id), 
	CONSTRAINT uq_organization_structure_versions_number UNIQUE (organization_id, version_number), 
	CONSTRAINT ck_organization_structure_versions_ck_organization_stru_e482 CHECK (version_number > 0), 
	CONSTRAINT ck_organization_structure_versions_ck_organization_stru_5bf4 CHECK (revision > 0), 
	CONSTRAINT ck_organization_structure_versions_ck_organization_stru_dd8f CHECK (effective_to IS NULL OR effective_from IS NULL OR effective_to >= effective_from), 
	CONSTRAINT ck_organization_structure_versions_ck_organization_stru_305a CHECK (status <> 'published' OR effective_from IS NOT NULL), 
	CONSTRAINT excl_organization_structure_versions_published_overlap EXCLUDE USING gist (organization_id WITH =, daterange(effective_from, effective_to, '[]') WITH &&) WHERE (status = 'published'), 
	CONSTRAINT fk_organization_structure_versions_organization_id_orga_02ea FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_organization_structure_versions_based_on_version_id__1e58 FOREIGN KEY(based_on_version_id) REFERENCES organization_structure_versions (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_organization_structure_versions_created_by_user_accounts FOREIGN KEY(created_by) REFERENCES user_accounts (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_organization_structure_versions_published_by_user_accounts FOREIGN KEY(published_by) REFERENCES user_accounts (id) ON DELETE SET NULL
);

CREATE INDEX ix_organization_structure_versions_active ON organization_structure_versions (organization_id, status, effective_from, effective_to);

CREATE INDEX ix_organization_structure_versions_based_on ON organization_structure_versions (based_on_version_id);

CREATE TABLE work_schedule_days (
	work_schedule_id UUID NOT NULL, 
	cycle_day INTEGER NOT NULL, 
	working_day BOOLEAN NOT NULL, 
	hours NUMERIC(5, 2) NOT NULL, 
	starts_at_minute INTEGER, 
	time_code_id UUID, 
	id UUID NOT NULL, 
	revision INTEGER NOT NULL, 
	CONSTRAINT pk_work_schedule_days PRIMARY KEY (id), 
	CONSTRAINT uq_work_schedule_days_schedule_day UNIQUE (work_schedule_id, cycle_day), 
	CONSTRAINT ck_work_schedule_days_cycle_day_nonnegative CHECK (cycle_day >= 0), 
	CONSTRAINT ck_work_schedule_days_hours_nonnegative CHECK (hours >= 0), 
	CONSTRAINT fk_work_schedule_days_work_schedule_id_work_schedules FOREIGN KEY(work_schedule_id) REFERENCES work_schedules (id) ON DELETE CASCADE, 
	CONSTRAINT fk_work_schedule_days_time_code_id_time_codes FOREIGN KEY(time_code_id) REFERENCES time_codes (id) ON DELETE RESTRICT
);

CREATE INDEX ix_work_schedule_days_work_schedule_id ON work_schedule_days (work_schedule_id);

CREATE TABLE employee_work_schedules (
	employee_id UUID NOT NULL, 
	work_schedule_id UUID NOT NULL, 
	effective_from DATE NOT NULL, 
	effective_to DATE, 
	cycle_anchor_date DATE, 
	assigned_by_user_id UUID NOT NULL, 
	id UUID NOT NULL, 
	revision INTEGER NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_employee_work_schedules PRIMARY KEY (id), 
	CONSTRAINT ck_employee_work_schedules_valid_dates CHECK (effective_to IS NULL OR effective_to >= effective_from), 
	CONSTRAINT fk_employee_work_schedules_employee_id_employees FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_employee_work_schedules_work_schedule_id_work_schedules FOREIGN KEY(work_schedule_id) REFERENCES work_schedules (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_employee_work_schedules_assigned_by_user_id_user_accounts FOREIGN KEY(assigned_by_user_id) REFERENCES user_accounts (id) ON DELETE RESTRICT
);

CREATE INDEX ix_employee_work_schedules_employee_id ON employee_work_schedules (employee_id);

CREATE INDEX ix_employee_work_schedules_employee_effective ON employee_work_schedules (employee_id, effective_from, effective_to);

CREATE TABLE process_definition_versions (
	process_definition_id UUID NOT NULL, 
	version_number INTEGER NOT NULL, 
	name VARCHAR(300) NOT NULL, 
	status VARCHAR(30) NOT NULL, 
	based_on_version_id UUID, 
	effective_from TIMESTAMP WITH TIME ZONE, 
	effective_to TIMESTAMP WITH TIME ZONE, 
	created_by UUID NOT NULL, 
	published_by UUID, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	published_at TIMESTAMP WITH TIME ZONE, 
	id UUID NOT NULL, 
	revision INTEGER NOT NULL, 
	CONSTRAINT pk_process_definition_versions PRIMARY KEY (id), 
	CONSTRAINT uq_process_definition_versions_process_definition_id_ve_c802 UNIQUE (process_definition_id, version_number), 
	CONSTRAINT ck_process_definition_versions_version_positive CHECK (version_number > 0), 
	CONSTRAINT fk_process_definition_versions_process_definition_id_pr_e616 FOREIGN KEY(process_definition_id) REFERENCES process_definitions (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_process_definition_versions_based_on_version_id_proc_0f83 FOREIGN KEY(based_on_version_id) REFERENCES process_definition_versions (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_process_definition_versions_created_by_user_accounts FOREIGN KEY(created_by) REFERENCES user_accounts (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_process_definition_versions_published_by_user_accounts FOREIGN KEY(published_by) REFERENCES user_accounts (id) ON DELETE RESTRICT
);

CREATE INDEX ix_process_definition_versions_status ON process_definition_versions (status);

CREATE INDEX ix_process_definition_versions_effective ON process_definition_versions (process_definition_id, status, effective_from);

CREATE INDEX ix_process_definition_versions_process_definition_id ON process_definition_versions (process_definition_id);

CREATE TABLE form_definition_versions (
	form_definition_id UUID NOT NULL, 
	version_number INTEGER NOT NULL, 
	status VARCHAR(30) NOT NULL, 
	based_on_version_id UUID, 
	created_by UUID NOT NULL, 
	published_by UUID, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	published_at TIMESTAMP WITH TIME ZONE, 
	id UUID NOT NULL, 
	revision INTEGER NOT NULL, 
	CONSTRAINT pk_form_definition_versions PRIMARY KEY (id), 
	CONSTRAINT uq_form_definition_versions_form_definition_id_version_number UNIQUE (form_definition_id, version_number), 
	CONSTRAINT fk_form_definition_versions_form_definition_id_form_definitions FOREIGN KEY(form_definition_id) REFERENCES form_definitions (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_form_definition_versions_based_on_version_id_form_de_8534 FOREIGN KEY(based_on_version_id) REFERENCES form_definition_versions (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_form_definition_versions_created_by_user_accounts FOREIGN KEY(created_by) REFERENCES user_accounts (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_form_definition_versions_published_by_user_accounts FOREIGN KEY(published_by) REFERENCES user_accounts (id) ON DELETE RESTRICT
);

CREATE TABLE organization_policies (
	id UUID NOT NULL, 
	organization_id UUID NOT NULL, 
	structure_version_id UUID, 
	effective_from DATE, 
	effective_to DATE, 
	managers_can_create_employee_drafts BOOLEAN DEFAULT false NOT NULL, 
	managers_can_assign_existing_employees BOOLEAN DEFAULT false NOT NULL, 
	manager_changes_require_hr_approval BOOLEAN DEFAULT true NOT NULL, 
	managers_can_create_staffing_slots BOOLEAN DEFAULT false NOT NULL, 
	staffing_changes_require_finance_review BOOLEAN DEFAULT true NOT NULL, 
	structure_publish_requires_review BOOLEAN DEFAULT true NOT NULL, 
	allow_multiple_unit_heads BOOLEAN DEFAULT false NOT NULL, 
	allow_cross_unit_relationships BOOLEAN DEFAULT true NOT NULL, 
	revision INTEGER DEFAULT 1 NOT NULL, 
	created_by UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	CONSTRAINT pk_organization_policies PRIMARY KEY (id), 
	CONSTRAINT uq_organization_policies_structure_version UNIQUE (structure_version_id), 
	CONSTRAINT ck_organization_policies_ck_organization_policies_revis_50d5 CHECK (revision > 0), 
	CONSTRAINT ck_organization_policies_ck_organization_policies_effec_6371 CHECK (effective_to IS NULL OR effective_from IS NULL OR effective_to >= effective_from), 
	CONSTRAINT fk_organization_policies_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_organization_policies_structure_version_id_organizat_9f7e FOREIGN KEY(structure_version_id) REFERENCES organization_structure_versions (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_organization_policies_created_by_user_accounts FOREIGN KEY(created_by) REFERENCES user_accounts (id) ON DELETE RESTRICT
);

CREATE UNIQUE INDEX uq_organization_policies_default ON organization_policies (organization_id) WHERE structure_version_id IS NULL;

CREATE TABLE organization_structure_review_requests (
	id UUID NOT NULL, 
	organization_id UUID NOT NULL, 
	structure_version_id UUID NOT NULL, 
	status VARCHAR(32) NOT NULL, 
	submitted_by UUID NOT NULL, 
	submitted_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	resolved_by UUID, 
	resolved_at TIMESTAMP WITH TIME ZONE, 
	submission_reason TEXT, 
	resolution_reason TEXT, 
	revision INTEGER DEFAULT 1 NOT NULL, 
	CONSTRAINT pk_organization_structure_review_requests PRIMARY KEY (id), 
	CONSTRAINT ck_organization_structure_review_requests_ck_organizati_dc16 CHECK (revision > 0), 
	CONSTRAINT fk_organization_structure_review_requests_organization__27ec FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_organization_structure_review_requests_structure_ver_53f0 FOREIGN KEY(structure_version_id) REFERENCES organization_structure_versions (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_organization_structure_review_requests_submitted_by__7d40 FOREIGN KEY(submitted_by) REFERENCES user_accounts (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_organization_structure_review_requests_resolved_by_u_105d FOREIGN KEY(resolved_by) REFERENCES user_accounts (id) ON DELETE SET NULL
);

CREATE INDEX ix_organization_structure_review_requests_status ON organization_structure_review_requests (organization_id, status);

CREATE UNIQUE INDEX uq_organization_structure_review_requests_pending ON organization_structure_review_requests (structure_version_id) WHERE status = 'pending';

CREATE TABLE organization_units (
	id UUID NOT NULL, 
	structure_version_id UUID NOT NULL, 
	stable_key UUID NOT NULL, 
	code VARCHAR(64) NOT NULL, 
	name VARCHAR(255) NOT NULL, 
	short_name VARCHAR(255), 
	unit_type_id UUID NOT NULL, 
	parent_unit_id UUID, 
	sort_order INTEGER DEFAULT 0 NOT NULL, 
	description TEXT, 
	active BOOLEAN DEFAULT true NOT NULL, 
	custom_fields JSONB DEFAULT '{}'::jsonb NOT NULL, 
	revision INTEGER DEFAULT 1 NOT NULL, 
	CONSTRAINT pk_organization_units PRIMARY KEY (id), 
	CONSTRAINT uq_organization_units_id_version UNIQUE (id, structure_version_id), 
	CONSTRAINT uq_organization_units_version_code UNIQUE (structure_version_id, code), 
	CONSTRAINT uq_organization_units_version_stable_key UNIQUE (structure_version_id, stable_key), 
	CONSTRAINT fk_organization_units_parent_same_version FOREIGN KEY(parent_unit_id, structure_version_id) REFERENCES organization_units (id, structure_version_id) ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED, 
	CONSTRAINT ck_organization_units_ck_organization_units_revision_positive CHECK (revision > 0), 
	CONSTRAINT ck_organization_units_ck_organization_units_sort_order__7240 CHECK (sort_order >= 0), 
	CONSTRAINT fk_organization_units_structure_version_id_organization_896d FOREIGN KEY(structure_version_id) REFERENCES organization_structure_versions (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_organization_units_unit_type_id_organization_unit_types FOREIGN KEY(unit_type_id) REFERENCES organization_unit_types (id) ON DELETE RESTRICT
);

CREATE INDEX ix_organization_units_tree ON organization_units (structure_version_id, parent_unit_id, active, sort_order);

CREATE UNIQUE INDEX uq_organization_units_single_active_root ON organization_units (structure_version_id) WHERE parent_unit_id IS NULL AND active;

CREATE INDEX ix_organization_units_stable_key ON organization_units (stable_key);

CREATE TABLE workflow_actor_rules (
	definition_version_id UUID NOT NULL, 
	code VARCHAR(100) NOT NULL, 
	name VARCHAR(300) NOT NULL, 
	rule_type VARCHAR(50) NOT NULL, 
	configuration JSONB NOT NULL, 
	active BOOLEAN NOT NULL, 
	id UUID NOT NULL, 
	revision INTEGER NOT NULL, 
	CONSTRAINT pk_workflow_actor_rules PRIMARY KEY (id), 
	CONSTRAINT uq_workflow_actor_rules_definition_version_id_code UNIQUE (definition_version_id, code), 
	CONSTRAINT fk_workflow_actor_rules_definition_version_id_process_d_cb9c FOREIGN KEY(definition_version_id) REFERENCES process_definition_versions (id) ON DELETE CASCADE
);

CREATE INDEX ix_workflow_actor_rules_definition_version_id ON workflow_actor_rules (definition_version_id);

CREATE TABLE process_instances (
	organization_id UUID NOT NULL, 
	process_definition_id UUID NOT NULL, 
	definition_version_id UUID NOT NULL, 
	business_type VARCHAR(100) NOT NULL, 
	business_entity_id UUID NOT NULL, 
	initiator_user_id UUID NOT NULL, 
	status VARCHAR(30) NOT NULL, 
	current_phase VARCHAR(100), 
	started_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	completed_at TIMESTAMP WITH TIME ZONE, 
	cancelled_at TIMESTAMP WITH TIME ZONE, 
	snapshot JSONB NOT NULL, 
	id UUID NOT NULL, 
	revision INTEGER NOT NULL, 
	CONSTRAINT pk_process_instances PRIMARY KEY (id), 
	CONSTRAINT fk_process_instances_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_process_instances_process_definition_id_process_definitions FOREIGN KEY(process_definition_id) REFERENCES process_definitions (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_process_instances_definition_version_id_process_defi_dcfd FOREIGN KEY(definition_version_id) REFERENCES process_definition_versions (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_process_instances_initiator_user_id_user_accounts FOREIGN KEY(initiator_user_id) REFERENCES user_accounts (id) ON DELETE RESTRICT
);

CREATE INDEX ix_process_instances_business ON process_instances (business_type, business_entity_id);

CREATE INDEX ix_process_instances_status ON process_instances (status);

CREATE INDEX ix_process_instances_scope_status ON process_instances (organization_id, status, started_at);

CREATE INDEX ix_process_instances_organization_id ON process_instances (organization_id);

CREATE TABLE form_field_definitions (
	form_version_id UUID NOT NULL, 
	code VARCHAR(100) NOT NULL, 
	label VARCHAR(300) NOT NULL, 
	field_type VARCHAR(50) NOT NULL, 
	required BOOLEAN NOT NULL, 
	validation_rules JSONB NOT NULL, 
	reference_data_source VARCHAR(200), 
	visibility_rule JSONB, 
	editability_rule JSONB, 
	confidentiality VARCHAR(30) NOT NULL, 
	ordering INTEGER NOT NULL, 
	help_text TEXT, 
	id UUID NOT NULL, 
	revision INTEGER NOT NULL, 
	CONSTRAINT pk_form_field_definitions PRIMARY KEY (id), 
	CONSTRAINT uq_form_field_definitions_form_version_id_code UNIQUE (form_version_id, code), 
	CONSTRAINT fk_form_field_definitions_form_version_id_form_definiti_282a FOREIGN KEY(form_version_id) REFERENCES form_definition_versions (id) ON DELETE CASCADE
);

CREATE TABLE leave_requests (
	organization_id UUID NOT NULL, 
	employee_id UUID NOT NULL, 
	unit_id UUID NOT NULL, 
	leave_type_id UUID NOT NULL, 
	start_date DATE NOT NULL, 
	end_date DATE NOT NULL, 
	requested_days NUMERIC(7, 2) NOT NULL, 
	reason TEXT, 
	status VARCHAR(40) NOT NULL, 
	returned_from_stage VARCHAR(40), 
	process_instance_id UUID, 
	submitted_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	approved_at TIMESTAMP WITH TIME ZONE, 
	cancelled_at TIMESTAMP WITH TIME ZONE, 
	cancellation_reason TEXT, 
	id UUID NOT NULL, 
	revision INTEGER NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_leave_requests PRIMARY KEY (id), 
	CONSTRAINT fk_leave_requests_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_leave_requests_employee_id_employees FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_leave_requests_unit_id_organization_units FOREIGN KEY(unit_id) REFERENCES organization_units (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_leave_requests_leave_type_id_leave_types FOREIGN KEY(leave_type_id) REFERENCES leave_types (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_leave_requests_process_instance_id_process_instances FOREIGN KEY(process_instance_id) REFERENCES process_instances (id) ON DELETE RESTRICT
);

CREATE INDEX ix_leave_requests_status ON leave_requests (status);

CREATE INDEX ix_leave_requests_employee_dates ON leave_requests (employee_id, start_date, end_date);

CREATE INDEX ix_leave_requests_employee_id ON leave_requests (employee_id);

CREATE INDEX ix_leave_requests_scope_status ON leave_requests (organization_id, unit_id, status);

CREATE INDEX ix_leave_requests_unit_id ON leave_requests (unit_id);

CREATE INDEX ix_leave_requests_organization_id ON leave_requests (organization_id);

CREATE TABLE business_trip_requests (
	organization_id UUID NOT NULL, 
	employee_id UUID NOT NULL, 
	unit_id UUID NOT NULL, 
	destination VARCHAR(500) NOT NULL, 
	start_date DATE NOT NULL, 
	end_date DATE NOT NULL, 
	purpose TEXT NOT NULL, 
	estimated_cost NUMERIC(14, 2) NOT NULL, 
	currency VARCHAR(3) NOT NULL, 
	funding_details JSONB NOT NULL, 
	status VARCHAR(40) NOT NULL, 
	returned_from_stage VARCHAR(40), 
	process_instance_id UUID, 
	submitted_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	approved_at TIMESTAMP WITH TIME ZONE, 
	registered_at TIMESTAMP WITH TIME ZONE, 
	cancelled_at TIMESTAMP WITH TIME ZONE, 
	cancellation_reason TEXT, 
	id UUID NOT NULL, 
	revision INTEGER NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_business_trip_requests PRIMARY KEY (id), 
	CONSTRAINT fk_business_trip_requests_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_business_trip_requests_employee_id_employees FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_business_trip_requests_unit_id_organization_units FOREIGN KEY(unit_id) REFERENCES organization_units (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_business_trip_requests_process_instance_id_process_instances FOREIGN KEY(process_instance_id) REFERENCES process_instances (id) ON DELETE RESTRICT
);

CREATE INDEX ix_business_trip_requests_organization_id ON business_trip_requests (organization_id);

CREATE INDEX ix_business_trips_employee_dates ON business_trip_requests (employee_id, start_date, end_date);

CREATE INDEX ix_business_trips_scope_status ON business_trip_requests (organization_id, unit_id, status);

CREATE INDEX ix_business_trip_requests_unit_id ON business_trip_requests (unit_id);

CREATE INDEX ix_business_trip_requests_employee_id ON business_trip_requests (employee_id);

CREATE INDEX ix_business_trip_requests_status ON business_trip_requests (status);

CREATE TABLE access_scope_units (
	scope_id UUID NOT NULL, 
	unit_id UUID NOT NULL, 
	CONSTRAINT pk_access_scope_units PRIMARY KEY (scope_id, unit_id), 
	CONSTRAINT fk_access_scope_units_scope_id_access_scopes FOREIGN KEY(scope_id) REFERENCES access_scopes (id) ON DELETE CASCADE, 
	CONSTRAINT fk_access_scope_units_unit_id_organization_units FOREIGN KEY(unit_id) REFERENCES organization_units (id) ON DELETE RESTRICT
);

CREATE INDEX ix_access_scope_units_unit_id ON access_scope_units (unit_id);

CREATE TABLE document_records (
	organization_id UUID NOT NULL, 
	document_type_id UUID NOT NULL, 
	template_version_id UUID, 
	process_instance_id UUID, 
	business_entity_type VARCHAR(100) NOT NULL, 
	business_entity_id UUID NOT NULL, 
	title VARCHAR(500) NOT NULL, 
	status VARCHAR(40) NOT NULL, 
	registration_number VARCHAR(200), 
	registration_date DATE, 
	current_version_number INTEGER NOT NULL, 
	confidentiality_level VARCHAR(30) NOT NULL, 
	created_by UUID NOT NULL, 
	id UUID NOT NULL, 
	revision INTEGER NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_document_records PRIMARY KEY (id), 
	CONSTRAINT fk_document_records_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_document_records_document_type_id_document_types FOREIGN KEY(document_type_id) REFERENCES document_types (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_document_records_template_version_id_document_templa_dfaf FOREIGN KEY(template_version_id) REFERENCES document_template_versions (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_document_records_process_instance_id_process_instances FOREIGN KEY(process_instance_id) REFERENCES process_instances (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_document_records_created_by_user_accounts FOREIGN KEY(created_by) REFERENCES user_accounts (id) ON DELETE RESTRICT
);

CREATE INDEX ix_document_records_organization_id ON document_records (organization_id);

CREATE INDEX ix_document_records_status ON document_records (status);

CREATE INDEX ix_document_records_process ON document_records (process_instance_id, status);

CREATE INDEX ix_document_records_business ON document_records (business_entity_type, business_entity_id);

CREATE TABLE organization_relationships (
	id UUID NOT NULL, 
	structure_version_id UUID NOT NULL, 
	relationship_type_id UUID NOT NULL, 
	source_unit_id UUID NOT NULL, 
	target_unit_id UUID NOT NULL, 
	effective_from DATE, 
	effective_to DATE, 
	metadata JSONB DEFAULT '{}'::jsonb NOT NULL, 
	active BOOLEAN DEFAULT true NOT NULL, 
	revision INTEGER DEFAULT 1 NOT NULL, 
	CONSTRAINT pk_organization_relationships PRIMARY KEY (id), 
	CONSTRAINT ck_organization_relationships_ck_organization_relations_42be CHECK (effective_to IS NULL OR effective_from IS NULL OR effective_to >= effective_from), 
	CONSTRAINT ck_organization_relationships_ck_organization_relations_9c8a CHECK (revision > 0), 
	CONSTRAINT fk_organization_relationships_structure_version_id_orga_701f FOREIGN KEY(structure_version_id) REFERENCES organization_structure_versions (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_organization_relationships_relationship_type_id_orga_6739 FOREIGN KEY(relationship_type_id) REFERENCES organization_relationship_types (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_organization_relationships_source_unit_id_organization_units FOREIGN KEY(source_unit_id) REFERENCES organization_units (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_organization_relationships_target_unit_id_organization_units FOREIGN KEY(target_unit_id) REFERENCES organization_units (id) ON DELETE RESTRICT
);

CREATE INDEX ix_organization_relationships_version_active ON organization_relationships (structure_version_id, active);

CREATE INDEX ix_organization_relationships_source_target ON organization_relationships (source_unit_id, target_unit_id);

CREATE TABLE staffing_slots (
	id UUID NOT NULL, 
	structure_version_id UUID NOT NULL, 
	stable_key UUID NOT NULL, 
	organization_unit_id UUID NOT NULL, 
	position_definition_id UUID NOT NULL, 
	reports_to_slot_id UUID, 
	head_of_unit BOOLEAN DEFAULT false NOT NULL, 
	full_time_equivalent NUMERIC(5, 2) DEFAULT 1.00 NOT NULL, 
	employment_type VARCHAR(32) NOT NULL, 
	status VARCHAR(32) NOT NULL, 
	effective_from DATE, 
	effective_to DATE, 
	revision INTEGER DEFAULT 1 NOT NULL, 
	custom_fields JSONB DEFAULT '{}'::jsonb NOT NULL, 
	CONSTRAINT pk_staffing_slots PRIMARY KEY (id), 
	CONSTRAINT uq_staffing_slots_version_stable_key UNIQUE (structure_version_id, stable_key), 
	CONSTRAINT ck_staffing_slots_ck_staffing_slots_revision_positive CHECK (revision > 0), 
	CONSTRAINT ck_staffing_slots_ck_staffing_slots_fte_range CHECK (full_time_equivalent > 0 AND full_time_equivalent <= 1), 
	CONSTRAINT ck_staffing_slots_ck_staffing_slots_effective_range CHECK (effective_to IS NULL OR effective_from IS NULL OR effective_to >= effective_from), 
	CONSTRAINT fk_staffing_slots_structure_version_id_organization_str_b6b3 FOREIGN KEY(structure_version_id) REFERENCES organization_structure_versions (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_staffing_slots_organization_unit_id_organization_units FOREIGN KEY(organization_unit_id) REFERENCES organization_units (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_staffing_slots_position_definition_id_position_definitions FOREIGN KEY(position_definition_id) REFERENCES position_definitions (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_staffing_slots_reports_to_slot_id_staffing_slots FOREIGN KEY(reports_to_slot_id) REFERENCES staffing_slots (id) ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED
);

CREATE INDEX ix_staffing_slots_active_head ON staffing_slots (organization_unit_id, head_of_unit) WHERE status NOT IN ('closing', 'closed');

CREATE INDEX ix_staffing_slots_version_unit_status ON staffing_slots (structure_version_id, organization_unit_id, status);

CREATE INDEX ix_staffing_slots_reports_to ON staffing_slots (reports_to_slot_id);

CREATE TABLE timesheet_periods (
	organization_id UUID NOT NULL, 
	organization_unit_id UUID NOT NULL, 
	period_start DATE NOT NULL, 
	period_end DATE NOT NULL, 
	status VARCHAR(30) NOT NULL, 
	manager_confirmed_at TIMESTAMP WITH TIME ZONE, 
	manager_confirmed_by_user_id UUID, 
	closed_at TIMESTAMP WITH TIME ZONE, 
	closed_by_user_id UUID, 
	sent_to_accounting_at TIMESTAMP WITH TIME ZONE, 
	reopened_at TIMESTAMP WITH TIME ZONE, 
	reopen_reason TEXT, 
	id UUID NOT NULL, 
	revision INTEGER NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_timesheet_periods PRIMARY KEY (id), 
	CONSTRAINT uq_timesheet_periods_unit_period UNIQUE (organization_unit_id, period_start), 
	CONSTRAINT ck_timesheet_periods_valid_dates CHECK (period_end >= period_start), 
	CONSTRAINT fk_timesheet_periods_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_timesheet_periods_organization_unit_id_organization_units FOREIGN KEY(organization_unit_id) REFERENCES organization_units (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_timesheet_periods_manager_confirmed_by_user_id_user_accounts FOREIGN KEY(manager_confirmed_by_user_id) REFERENCES user_accounts (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_timesheet_periods_closed_by_user_id_user_accounts FOREIGN KEY(closed_by_user_id) REFERENCES user_accounts (id) ON DELETE RESTRICT
);

CREATE INDEX ix_timesheet_periods_scope_status ON timesheet_periods (organization_id, status, period_start);

CREATE INDEX ix_timesheet_periods_status ON timesheet_periods (status);

CREATE INDEX ix_timesheet_periods_organization_unit_id ON timesheet_periods (organization_unit_id);

CREATE INDEX ix_timesheet_periods_organization_id ON timesheet_periods (organization_id);

CREATE TABLE process_step_definitions (
	definition_version_id UUID NOT NULL, 
	stable_key UUID NOT NULL, 
	code VARCHAR(100) NOT NULL, 
	name VARCHAR(300) NOT NULL, 
	step_type VARCHAR(50) NOT NULL, 
	sequence INTEGER NOT NULL, 
	actor_rule_id UUID, 
	allowed_actions JSONB NOT NULL, 
	due_duration_seconds INTEGER, 
	required_document_type_ids JSONB NOT NULL, 
	configuration JSONB NOT NULL, 
	completion_mode VARCHAR(10) NOT NULL, 
	required_approvers INTEGER NOT NULL, 
	active BOOLEAN NOT NULL, 
	id UUID NOT NULL, 
	revision INTEGER NOT NULL, 
	CONSTRAINT pk_process_step_definitions PRIMARY KEY (id), 
	CONSTRAINT uq_process_step_definitions_definition_version_id_code UNIQUE (definition_version_id, code), 
	CONSTRAINT uq_process_step_definitions_definition_version_id_stable_key UNIQUE (definition_version_id, stable_key), 
	CONSTRAINT ck_process_step_definitions_sequence_nonnegative CHECK (sequence >= 0), 
	CONSTRAINT ck_process_step_definitions_required_approvers_positive CHECK (required_approvers > 0), 
	CONSTRAINT fk_process_step_definitions_definition_version_id_proce_ac67 FOREIGN KEY(definition_version_id) REFERENCES process_definition_versions (id) ON DELETE CASCADE, 
	CONSTRAINT fk_process_step_definitions_actor_rule_id_workflow_actor_rules FOREIGN KEY(actor_rule_id) REFERENCES workflow_actor_rules (id) ON DELETE RESTRICT
);

CREATE INDEX ix_process_step_definitions_definition_version_id ON process_step_definitions (definition_version_id);

CREATE TABLE process_history_entries (
	process_instance_id UUID NOT NULL, 
	event_type VARCHAR(80) NOT NULL, 
	actor_user_id UUID, 
	summary VARCHAR(1000) NOT NULL, 
	metadata JSONB NOT NULL, 
	occurred_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	id UUID NOT NULL, 
	CONSTRAINT pk_process_history_entries PRIMARY KEY (id), 
	CONSTRAINT fk_process_history_entries_process_instance_id_process__2869 FOREIGN KEY(process_instance_id) REFERENCES process_instances (id) ON DELETE CASCADE, 
	CONSTRAINT fk_process_history_entries_actor_user_id_user_accounts FOREIGN KEY(actor_user_id) REFERENCES user_accounts (id) ON DELETE RESTRICT
);

CREATE INDEX ix_process_history_entries_process_instance_id ON process_history_entries (process_instance_id);

CREATE INDEX ix_process_history_instance_time ON process_history_entries (process_instance_id, occurred_at);

CREATE TABLE form_submissions (
	organization_id UUID NOT NULL, 
	form_version_id UUID NOT NULL, 
	process_instance_id UUID, 
	business_entity_type VARCHAR(100) NOT NULL, 
	business_entity_id UUID NOT NULL, 
	submitted_by UUID NOT NULL, 
	data JSONB NOT NULL, 
	submitted_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	id UUID NOT NULL, 
	revision INTEGER NOT NULL, 
	CONSTRAINT pk_form_submissions PRIMARY KEY (id), 
	CONSTRAINT fk_form_submissions_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_form_submissions_form_version_id_form_definition_versions FOREIGN KEY(form_version_id) REFERENCES form_definition_versions (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_form_submissions_process_instance_id_process_instances FOREIGN KEY(process_instance_id) REFERENCES process_instances (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_form_submissions_submitted_by_user_accounts FOREIGN KEY(submitted_by) REFERENCES user_accounts (id) ON DELETE RESTRICT
);

CREATE INDEX ix_form_submissions_business ON form_submissions (business_entity_type, business_entity_id);

CREATE TABLE document_versions (
	document_id UUID NOT NULL, 
	version_number INTEGER NOT NULL, 
	storage_key VARCHAR(1000) NOT NULL, 
	original_filename VARCHAR(500) NOT NULL, 
	safe_filename VARCHAR(500) NOT NULL, 
	mime_type VARCHAR(200) NOT NULL, 
	size_bytes INTEGER NOT NULL, 
	sha256 VARCHAR(64) NOT NULL, 
	author_user_id UUID NOT NULL, 
	source_type VARCHAR(30) NOT NULL, 
	metadata JSONB NOT NULL, 
	immutable BOOLEAN NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	id UUID NOT NULL, 
	CONSTRAINT pk_document_versions PRIMARY KEY (id), 
	CONSTRAINT uq_document_versions_document_id_version_number UNIQUE (document_id, version_number), 
	CONSTRAINT ck_document_versions_size_nonnegative CHECK (size_bytes >= 0), 
	CONSTRAINT fk_document_versions_document_id_document_records FOREIGN KEY(document_id) REFERENCES document_records (id) ON DELETE RESTRICT, 
	CONSTRAINT uq_document_versions_storage_key UNIQUE (storage_key), 
	CONSTRAINT fk_document_versions_author_user_id_user_accounts FOREIGN KEY(author_user_id) REFERENCES user_accounts (id) ON DELETE RESTRICT
);

CREATE INDEX ix_document_versions_document_id ON document_versions (document_id);

CREATE TABLE document_checklist_items (
	organization_id UUID NOT NULL, 
	process_instance_id UUID, 
	business_entity_type VARCHAR(100) NOT NULL, 
	business_entity_id UUID NOT NULL, 
	document_type_id UUID NOT NULL, 
	document_id UUID, 
	mandatory BOOLEAN NOT NULL, 
	status VARCHAR(30) NOT NULL, 
	rejection_comment TEXT, 
	id UUID NOT NULL, 
	revision INTEGER NOT NULL, 
	CONSTRAINT pk_document_checklist_items PRIMARY KEY (id), 
	CONSTRAINT uq_document_checklist_items_business_entity_type_busine_4411 UNIQUE (business_entity_type, business_entity_id, document_type_id), 
	CONSTRAINT fk_document_checklist_items_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_document_checklist_items_process_instance_id_process_250e FOREIGN KEY(process_instance_id) REFERENCES process_instances (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_document_checklist_items_document_type_id_document_types FOREIGN KEY(document_type_id) REFERENCES document_types (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_document_checklist_items_document_id_document_records FOREIGN KEY(document_id) REFERENCES document_records (id) ON DELETE RESTRICT
);

CREATE TABLE employee_assignments (
	id UUID NOT NULL, 
	employee_id UUID NOT NULL, 
	staffing_slot_id UUID NOT NULL, 
	assignment_type VARCHAR(32) NOT NULL, 
	full_time_equivalent NUMERIC(5, 2) NOT NULL, 
	effective_from DATE NOT NULL, 
	effective_to DATE, 
	"primary" BOOLEAN NOT NULL, 
	acting BOOLEAN NOT NULL, 
	status VARCHAR(32) NOT NULL, 
	source_document_id UUID, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	revision INTEGER NOT NULL, 
	CONSTRAINT pk_employee_assignments PRIMARY KEY (id), 
	CONSTRAINT ck_employee_assignments_ck_assignments_fte_positive CHECK (full_time_equivalent > 0), 
	CONSTRAINT ck_employee_assignments_ck_assignments_fte_maximum CHECK (full_time_equivalent <= 1), 
	CONSTRAINT ck_employee_assignments_ck_assignments_valid_dates CHECK (effective_to IS NULL OR effective_to >= effective_from), 
	CONSTRAINT fk_employee_assignments_employee_id_employees FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_employee_assignments_staffing_slot_id_staffing_slots FOREIGN KEY(staffing_slot_id) REFERENCES staffing_slots (id) ON DELETE RESTRICT, 
	CONSTRAINT ex_employee_assignments_one_primary_period EXCLUDE USING gist (employee_id WITH =, daterange(effective_from, effective_to, '[]') WITH &&) WHERE ("primary" AND status IN ('pending_review', 'planned', 'active', 'scheduled_end', 'ended'))
);

CREATE INDEX ix_assignments_employee_effective ON employee_assignments (employee_id, effective_from, effective_to);

CREATE INDEX ix_assignments_slot_effective ON employee_assignments (staffing_slot_id, effective_from, effective_to);

CREATE TABLE recruitment_requests (
	organization_id UUID NOT NULL, 
	requesting_unit_id UUID NOT NULL, 
	requested_by_employee_id UUID NOT NULL, 
	staffing_slot_id UUID, 
	position_definition_id UUID NOT NULL, 
	requested_fte NUMERIC(5, 2) NOT NULL, 
	employment_type VARCHAR(50) NOT NULL, 
	desired_start_date DATE NOT NULL, 
	reason TEXT NOT NULL, 
	responsibilities TEXT NOT NULL, 
	requirements TEXT NOT NULL, 
	proposed_compensation JSONB, 
	status VARCHAR(40) NOT NULL, 
	process_instance_id UUID, 
	id UUID NOT NULL, 
	revision INTEGER NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_recruitment_requests PRIMARY KEY (id), 
	CONSTRAINT fk_recruitment_requests_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_recruitment_requests_requesting_unit_id_organization_units FOREIGN KEY(requesting_unit_id) REFERENCES organization_units (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_recruitment_requests_requested_by_employee_id_employees FOREIGN KEY(requested_by_employee_id) REFERENCES employees (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_recruitment_requests_staffing_slot_id_staffing_slots FOREIGN KEY(staffing_slot_id) REFERENCES staffing_slots (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_recruitment_requests_position_definition_id_position_1244 FOREIGN KEY(position_definition_id) REFERENCES position_definitions (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_recruitment_requests_process_instance_id_process_instances FOREIGN KEY(process_instance_id) REFERENCES process_instances (id) ON DELETE RESTRICT
);

CREATE INDEX ix_recruitment_requests_status ON recruitment_requests (status);

CREATE INDEX ix_recruitment_requests_requesting_unit_id ON recruitment_requests (requesting_unit_id);

CREATE INDEX ix_recruitment_requests_organization_id ON recruitment_requests (organization_id);

CREATE TABLE competition_commissions (
	organization_id UUID NOT NULL, 
	code VARCHAR(100) NOT NULL, 
	meeting_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	quorum_required INTEGER NOT NULL, 
	protocol_document_id UUID, 
	status VARCHAR(30) NOT NULL, 
	id UUID NOT NULL, 
	revision INTEGER NOT NULL, 
	CONSTRAINT pk_competition_commissions PRIMARY KEY (id), 
	CONSTRAINT fk_competition_commissions_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_competition_commissions_protocol_document_id_documen_8f59 FOREIGN KEY(protocol_document_id) REFERENCES document_records (id) ON DELETE RESTRICT
);

CREATE TABLE timesheet_entries (
	timesheet_period_id UUID NOT NULL, 
	employee_id UUID NOT NULL, 
	entry_date DATE NOT NULL, 
	time_code_id UUID NOT NULL, 
	hours NUMERIC(5, 2) NOT NULL, 
	source VARCHAR(30) NOT NULL, 
	source_absence_id UUID, 
	source_leave_request_id UUID, 
	manual_reason TEXT, 
	locked BOOLEAN NOT NULL, 
	created_by_user_id UUID NOT NULL, 
	id UUID NOT NULL, 
	revision INTEGER NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_timesheet_entries PRIMARY KEY (id), 
	CONSTRAINT uq_timesheet_entries_period_employee_date_code UNIQUE (timesheet_period_id, employee_id, entry_date, time_code_id), 
	CONSTRAINT ck_timesheet_entries_hours_nonnegative CHECK (hours >= 0), 
	CONSTRAINT ck_timesheet_entries_hours_maximum CHECK (hours <= 24), 
	CONSTRAINT ck_timesheet_entries_manual_reason_present CHECK ((source IN ('manual', 'correction')) = (manual_reason IS NOT NULL)), 
	CONSTRAINT fk_timesheet_entries_timesheet_period_id_timesheet_periods FOREIGN KEY(timesheet_period_id) REFERENCES timesheet_periods (id) ON DELETE CASCADE, 
	CONSTRAINT fk_timesheet_entries_employee_id_employees FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_timesheet_entries_time_code_id_time_codes FOREIGN KEY(time_code_id) REFERENCES time_codes (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_timesheet_entries_source_absence_id_employee_absences FOREIGN KEY(source_absence_id) REFERENCES employee_absences (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_timesheet_entries_source_leave_request_id_leave_requests FOREIGN KEY(source_leave_request_id) REFERENCES leave_requests (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_timesheet_entries_created_by_user_id_user_accounts FOREIGN KEY(created_by_user_id) REFERENCES user_accounts (id) ON DELETE RESTRICT
);

CREATE INDEX ix_timesheet_entries_employee_id ON timesheet_entries (employee_id);

CREATE INDEX ix_timesheet_entries_timesheet_period_id ON timesheet_entries (timesheet_period_id);

CREATE INDEX ix_timesheet_entries_period_employee ON timesheet_entries (timesheet_period_id, employee_id);

CREATE INDEX ix_timesheet_entries_employee_date ON timesheet_entries (employee_id, entry_date);

CREATE TABLE process_transition_definitions (
	definition_version_id UUID NOT NULL, 
	source_step_id UUID NOT NULL, 
	target_step_id UUID NOT NULL, 
	action VARCHAR(30) NOT NULL, 
	condition JSONB, 
	priority INTEGER NOT NULL, 
	active BOOLEAN NOT NULL, 
	id UUID NOT NULL, 
	CONSTRAINT pk_process_transition_definitions PRIMARY KEY (id), 
	CONSTRAINT uq_process_transition_definitions_definition_version_id_d02b UNIQUE (definition_version_id, source_step_id, target_step_id, action), 
	CONSTRAINT fk_process_transition_definitions_definition_version_id_4b10 FOREIGN KEY(definition_version_id) REFERENCES process_definition_versions (id) ON DELETE CASCADE, 
	CONSTRAINT fk_process_transition_definitions_source_step_id_proces_f43d FOREIGN KEY(source_step_id) REFERENCES process_step_definitions (id) ON DELETE CASCADE, 
	CONSTRAINT fk_process_transition_definitions_target_step_id_proces_ff10 FOREIGN KEY(target_step_id) REFERENCES process_step_definitions (id) ON DELETE CASCADE
);

CREATE INDEX ix_process_transition_definitions_definition_version_id ON process_transition_definitions (definition_version_id);

CREATE TABLE workflow_tasks (
	process_instance_id UUID NOT NULL, 
	step_definition_id UUID NOT NULL, 
	assigned_user_id UUID, 
	assigned_employee_id UUID, 
	assigned_unit_id UUID, 
	status VARCHAR(30) NOT NULL, 
	due_at TIMESTAMP WITH TIME ZONE, 
	decision VARCHAR(30), 
	decision_comment TEXT, 
	idempotency_key VARCHAR(200), 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	completed_at TIMESTAMP WITH TIME ZONE, 
	id UUID NOT NULL, 
	revision INTEGER NOT NULL, 
	CONSTRAINT pk_workflow_tasks PRIMARY KEY (id), 
	CONSTRAINT uq_workflow_task_assignment UNIQUE (process_instance_id, step_definition_id, assigned_user_id), 
	CONSTRAINT fk_workflow_tasks_process_instance_id_process_instances FOREIGN KEY(process_instance_id) REFERENCES process_instances (id) ON DELETE CASCADE, 
	CONSTRAINT fk_workflow_tasks_step_definition_id_process_step_definitions FOREIGN KEY(step_definition_id) REFERENCES process_step_definitions (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_workflow_tasks_assigned_user_id_user_accounts FOREIGN KEY(assigned_user_id) REFERENCES user_accounts (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_workflow_tasks_assigned_employee_id_employees FOREIGN KEY(assigned_employee_id) REFERENCES employees (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_workflow_tasks_assigned_unit_id_organization_units FOREIGN KEY(assigned_unit_id) REFERENCES organization_units (id) ON DELETE RESTRICT, 
	CONSTRAINT uq_workflow_tasks_idempotency_key UNIQUE (idempotency_key)
);

CREATE INDEX ix_workflow_tasks_assigned_user_id ON workflow_tasks (assigned_user_id);

CREATE INDEX ix_workflow_tasks_process_instance_id ON workflow_tasks (process_instance_id);

CREATE INDEX ix_workflow_tasks_assigned ON workflow_tasks (assigned_user_id, status, due_at);

CREATE INDEX ix_workflow_tasks_status ON workflow_tasks (status);

CREATE TABLE document_acknowledgements (
	document_id UUID NOT NULL, 
	document_version_id UUID NOT NULL, 
	assigned_employee_id UUID NOT NULL, 
	assigned_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	acknowledged_at TIMESTAMP WITH TIME ZONE, 
	status VARCHAR(30) NOT NULL, 
	evidence_metadata JSONB NOT NULL, 
	id UUID NOT NULL, 
	revision INTEGER NOT NULL, 
	CONSTRAINT pk_document_acknowledgements PRIMARY KEY (id), 
	CONSTRAINT uq_document_acknowledgements_document_version_id_assign_d537 UNIQUE (document_version_id, assigned_employee_id), 
	CONSTRAINT fk_document_acknowledgements_document_id_document_records FOREIGN KEY(document_id) REFERENCES document_records (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_document_acknowledgements_document_version_id_docume_e194 FOREIGN KEY(document_version_id) REFERENCES document_versions (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_document_acknowledgements_assigned_employee_id_employees FOREIGN KEY(assigned_employee_id) REFERENCES employees (id) ON DELETE RESTRICT
);

CREATE TABLE document_signatures (
	document_id UUID NOT NULL, 
	document_version_id UUID NOT NULL, 
	signer_user_id UUID NOT NULL, 
	status VARCHAR(30) NOT NULL, 
	provider_reference VARCHAR(500), 
	manual_confirmation BOOLEAN NOT NULL, 
	requested_at TIMESTAMP WITH TIME ZONE, 
	resolved_at TIMESTAMP WITH TIME ZONE, 
	evidence_metadata JSONB NOT NULL, 
	id UUID NOT NULL, 
	revision INTEGER NOT NULL, 
	CONSTRAINT pk_document_signatures PRIMARY KEY (id), 
	CONSTRAINT fk_document_signatures_document_id_document_records FOREIGN KEY(document_id) REFERENCES document_records (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_document_signatures_document_version_id_document_versions FOREIGN KEY(document_version_id) REFERENCES document_versions (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_document_signatures_signer_user_id_user_accounts FOREIGN KEY(signer_user_id) REFERENCES user_accounts (id) ON DELETE RESTRICT
);

CREATE INDEX ix_document_signatures_document ON document_signatures (document_id, status);

CREATE TABLE employee_assignment_review_requests (
	id UUID NOT NULL, 
	organization_id UUID NOT NULL, 
	assignment_id UUID NOT NULL, 
	status VARCHAR(32) NOT NULL, 
	submitted_by UUID NOT NULL, 
	submitted_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	resolved_by UUID, 
	resolved_at TIMESTAMP WITH TIME ZONE, 
	submission_reason TEXT NOT NULL, 
	resolution_reason TEXT, 
	revision INTEGER NOT NULL, 
	CONSTRAINT pk_employee_assignment_review_requests PRIMARY KEY (id), 
	CONSTRAINT ck_employee_assignment_review_requests_ck_employee_assi_3a07 CHECK (revision > 0), 
	CONSTRAINT fk_employee_assignment_review_requests_organization_id__ebba FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_employee_assignment_review_requests_assignment_id_em_c3e5 FOREIGN KEY(assignment_id) REFERENCES employee_assignments (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_employee_assignment_review_requests_submitted_by_use_0eb6 FOREIGN KEY(submitted_by) REFERENCES user_accounts (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_employee_assignment_review_requests_resolved_by_user_bf57 FOREIGN KEY(resolved_by) REFERENCES user_accounts (id) ON DELETE SET NULL
);

CREATE UNIQUE INDEX uq_employee_assignment_reviews_pending ON employee_assignment_review_requests (assignment_id) WHERE status = 'pending';

CREATE INDEX ix_employee_assignment_reviews_organization_status ON employee_assignment_review_requests (organization_id, status);

CREATE TABLE new_employee_hiring_requests (
	organization_id UUID NOT NULL, 
	request_number VARCHAR(80) NOT NULL, 
	created_by UUID NOT NULL, 
	protected_personal_data TEXT NOT NULL, 
	employment_data JSONB NOT NULL, 
	education_data JSONB NOT NULL, 
	status VARCHAR(40) NOT NULL, 
	current_stage INTEGER NOT NULL, 
	approval_cycle INTEGER NOT NULL, 
	pdf_document_id UUID, 
	pdf_version_id UUID, 
	final_pdf_version_id UUID, 
	submitted_at TIMESTAMP WITH TIME ZONE, 
	final_approved_at TIMESTAMP WITH TIME ZONE, 
	dispatched_at TIMESTAMP WITH TIME ZONE, 
	completed_at TIMESTAMP WITH TIME ZONE, 
	hired_employee_id UUID, 
	id UUID NOT NULL, 
	revision INTEGER NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_new_employee_hiring_requests PRIMARY KEY (id), 
	CONSTRAINT uq_new_employee_hiring_requests_organization_id_request_number UNIQUE (organization_id, request_number), 
	CONSTRAINT fk_new_employee_hiring_requests_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_new_employee_hiring_requests_created_by_user_accounts FOREIGN KEY(created_by) REFERENCES user_accounts (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_new_employee_hiring_requests_pdf_document_id_documen_8072 FOREIGN KEY(pdf_document_id) REFERENCES document_records (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_new_employee_hiring_requests_pdf_version_id_document_f7bd FOREIGN KEY(pdf_version_id) REFERENCES document_versions (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_new_employee_hiring_requests_final_pdf_version_id_do_e40a FOREIGN KEY(final_pdf_version_id) REFERENCES document_versions (id) ON DELETE RESTRICT, 
	CONSTRAINT uq_new_employee_hiring_requests_hired_employee_id UNIQUE (hired_employee_id), 
	CONSTRAINT fk_new_employee_hiring_requests_hired_employee_id_employees FOREIGN KEY(hired_employee_id) REFERENCES employees (id) ON DELETE SET NULL
);

CREATE INDEX ix_new_employee_hiring_requests_status ON new_employee_hiring_requests (status);

CREATE INDEX ix_new_hiring_requests_status_stage ON new_employee_hiring_requests (organization_id, status, current_stage);

CREATE INDEX ix_new_employee_hiring_requests_created_by ON new_employee_hiring_requests (created_by);

CREATE INDEX ix_new_employee_hiring_requests_organization_id ON new_employee_hiring_requests (organization_id);

CREATE TABLE recruitment_staffing_reviews (
	recruitment_request_id UUID NOT NULL, 
	reviewer_user_id UUID NOT NULL, 
	vacant_slot_confirmed BOOLEAN NOT NULL, 
	approved_fte NUMERIC(5, 2), 
	budget_confirmed BOOLEAN NOT NULL, 
	compensation_range JSONB, 
	decision VARCHAR(30) NOT NULL, 
	comment TEXT NOT NULL, 
	reviewed_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	id UUID NOT NULL, 
	revision INTEGER NOT NULL, 
	CONSTRAINT pk_recruitment_staffing_reviews PRIMARY KEY (id), 
	CONSTRAINT uq_recruitment_staffing_reviews_recruitment_request_id UNIQUE (recruitment_request_id), 
	CONSTRAINT fk_recruitment_staffing_reviews_recruitment_request_id__8cd4 FOREIGN KEY(recruitment_request_id) REFERENCES recruitment_requests (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_recruitment_staffing_reviews_reviewer_user_id_user_accounts FOREIGN KEY(reviewer_user_id) REFERENCES user_accounts (id) ON DELETE RESTRICT
);

CREATE TABLE vacancies (
	organization_id UUID NOT NULL, 
	recruitment_request_id UUID NOT NULL, 
	staffing_slot_id UUID NOT NULL, 
	code VARCHAR(100) NOT NULL, 
	title VARCHAR(300) NOT NULL, 
	description TEXT NOT NULL, 
	responsibilities TEXT NOT NULL, 
	requirements TEXT NOT NULL, 
	employment_conditions JSONB NOT NULL, 
	publication_status VARCHAR(40) NOT NULL, 
	internal_published_at TIMESTAMP WITH TIME ZONE, 
	external_published_at TIMESTAMP WITH TIME ZONE, 
	application_deadline DATE, 
	closed_at TIMESTAMP WITH TIME ZONE, 
	close_reason TEXT, 
	id UUID NOT NULL, 
	revision INTEGER NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_vacancies PRIMARY KEY (id), 
	CONSTRAINT uq_vacancies_organization_id_code UNIQUE (organization_id, code), 
	CONSTRAINT fk_vacancies_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_vacancies_recruitment_request_id_recruitment_requests FOREIGN KEY(recruitment_request_id) REFERENCES recruitment_requests (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_vacancies_staffing_slot_id_staffing_slots FOREIGN KEY(staffing_slot_id) REFERENCES staffing_slots (id) ON DELETE RESTRICT
);

CREATE INDEX ix_vacancies_publication_status ON vacancies (publication_status);

CREATE INDEX ix_vacancies_organization_id ON vacancies (organization_id);

CREATE TABLE competition_commission_members (
	commission_id UUID NOT NULL, 
	employee_id UUID NOT NULL, 
	role VARCHAR(30) NOT NULL, 
	conflict_declared BOOLEAN NOT NULL, 
	declaration TEXT, 
	id UUID NOT NULL, 
	revision INTEGER NOT NULL, 
	CONSTRAINT pk_competition_commission_members PRIMARY KEY (id), 
	CONSTRAINT uq_competition_commission_members_commission_id_employee_id UNIQUE (commission_id, employee_id), 
	CONSTRAINT fk_competition_commission_members_commission_id_competi_86b2 FOREIGN KEY(commission_id) REFERENCES competition_commissions (id) ON DELETE CASCADE, 
	CONSTRAINT fk_competition_commission_members_employee_id_employees FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE RESTRICT
);

CREATE TABLE termination_cases (
	organization_id UUID NOT NULL, 
	employee_id UUID NOT NULL, 
	initiated_by_user_id UUID NOT NULL, 
	initiated_by_employee_id UUID, 
	reason_id UUID NOT NULL, 
	legal_basis TEXT NOT NULL, 
	requested_date DATE NOT NULL, 
	effective_date DATE, 
	status VARCHAR(50) NOT NULL, 
	process_instance_id UUID, 
	order_document_id UUID, 
	primary_assignment_id UUID, 
	secondary_assignment_plan JSONB NOT NULL, 
	manager_notified_at TIMESTAMP WITH TIME ZONE, 
	scheduled_at TIMESTAMP WITH TIME ZONE, 
	effective_at TIMESTAMP WITH TIME ZONE, 
	completed_at TIMESTAMP WITH TIME ZONE, 
	cancelled_at TIMESTAMP WITH TIME ZONE, 
	cancellation_reason TEXT, 
	id UUID NOT NULL, 
	revision INTEGER NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_termination_cases PRIMARY KEY (id), 
	CONSTRAINT fk_termination_cases_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_termination_cases_employee_id_employees FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_termination_cases_initiated_by_user_id_user_accounts FOREIGN KEY(initiated_by_user_id) REFERENCES user_accounts (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_termination_cases_initiated_by_employee_id_employees FOREIGN KEY(initiated_by_employee_id) REFERENCES employees (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_termination_cases_reason_id_termination_reasons FOREIGN KEY(reason_id) REFERENCES termination_reasons (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_termination_cases_process_instance_id_process_instances FOREIGN KEY(process_instance_id) REFERENCES process_instances (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_termination_cases_order_document_id_document_records FOREIGN KEY(order_document_id) REFERENCES document_records (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_termination_cases_primary_assignment_id_employee_assignments FOREIGN KEY(primary_assignment_id) REFERENCES employee_assignments (id) ON DELETE RESTRICT
);

CREATE INDEX ix_termination_cases_status ON termination_cases (status);

CREATE INDEX ix_termination_cases_employee_id ON termination_cases (employee_id);

CREATE INDEX ix_termination_cases_scope_status ON termination_cases (organization_id, status, effective_date);

CREATE INDEX ix_termination_cases_organization_id ON termination_cases (organization_id);

CREATE TABLE timesheet_corrections (
	organization_id UUID NOT NULL, 
	timesheet_period_id UUID NOT NULL, 
	employee_id UUID NOT NULL, 
	entry_date DATE NOT NULL, 
	timesheet_entry_id UUID, 
	previous_time_code_id UUID, 
	previous_hours NUMERIC(5, 2), 
	requested_time_code_id UUID, 
	requested_hours NUMERIC(5, 2), 
	reason TEXT NOT NULL, 
	status VARCHAR(30) NOT NULL, 
	process_instance_id UUID, 
	requested_by_user_id UUID NOT NULL, 
	applied_at TIMESTAMP WITH TIME ZONE, 
	applied_by_user_id UUID, 
	decision_reason TEXT, 
	metadata JSONB NOT NULL, 
	id UUID NOT NULL, 
	revision INTEGER NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_timesheet_corrections PRIMARY KEY (id), 
	CONSTRAINT ck_timesheet_corrections_requested_hours_nonnegative CHECK (requested_hours IS NULL OR requested_hours >= 0), 
	CONSTRAINT fk_timesheet_corrections_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_timesheet_corrections_timesheet_period_id_timesheet_periods FOREIGN KEY(timesheet_period_id) REFERENCES timesheet_periods (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_timesheet_corrections_employee_id_employees FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_timesheet_corrections_timesheet_entry_id_timesheet_entries FOREIGN KEY(timesheet_entry_id) REFERENCES timesheet_entries (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_timesheet_corrections_previous_time_code_id_time_codes FOREIGN KEY(previous_time_code_id) REFERENCES time_codes (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_timesheet_corrections_requested_time_code_id_time_codes FOREIGN KEY(requested_time_code_id) REFERENCES time_codes (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_timesheet_corrections_process_instance_id_process_instances FOREIGN KEY(process_instance_id) REFERENCES process_instances (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_timesheet_corrections_requested_by_user_id_user_accounts FOREIGN KEY(requested_by_user_id) REFERENCES user_accounts (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_timesheet_corrections_applied_by_user_id_user_accounts FOREIGN KEY(applied_by_user_id) REFERENCES user_accounts (id) ON DELETE RESTRICT
);

CREATE INDEX ix_timesheet_corrections_scope_status ON timesheet_corrections (organization_id, status);

CREATE INDEX ix_timesheet_corrections_status ON timesheet_corrections (status);

CREATE INDEX ix_timesheet_corrections_process_instance ON timesheet_corrections (process_instance_id);

CREATE INDEX ix_timesheet_corrections_period ON timesheet_corrections (timesheet_period_id);

CREATE INDEX ix_timesheet_corrections_employee_id ON timesheet_corrections (employee_id);

CREATE INDEX ix_timesheet_corrections_organization_id ON timesheet_corrections (organization_id);

CREATE TABLE new_employee_hiring_attachments (
	request_id UUID NOT NULL, 
	category VARCHAR(40) NOT NULL, 
	document_id UUID NOT NULL, 
	current_version_id UUID NOT NULL, 
	original_filename VARCHAR(500) NOT NULL, 
	size_bytes INTEGER NOT NULL, 
	mime_type VARCHAR(200) NOT NULL, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_new_employee_hiring_attachments PRIMARY KEY (id), 
	CONSTRAINT uq_new_employee_hiring_attachments_request_id_category UNIQUE (request_id, category), 
	CONSTRAINT fk_new_employee_hiring_attachments_request_id_new_emplo_160d FOREIGN KEY(request_id) REFERENCES new_employee_hiring_requests (id) ON DELETE CASCADE, 
	CONSTRAINT fk_new_employee_hiring_attachments_document_id_document_records FOREIGN KEY(document_id) REFERENCES document_records (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_new_employee_hiring_attachments_current_version_id_d_77dd FOREIGN KEY(current_version_id) REFERENCES document_versions (id) ON DELETE RESTRICT
);

CREATE INDEX ix_new_employee_hiring_attachments_request_id ON new_employee_hiring_attachments (request_id);

CREATE TABLE new_employee_hiring_approval_decisions (
	request_id UUID NOT NULL, 
	approval_cycle INTEGER NOT NULL, 
	stage_number INTEGER NOT NULL, 
	stage_code VARCHAR(80) NOT NULL, 
	stage_name VARCHAR(300) NOT NULL, 
	approver_user_id UUID NOT NULL, 
	approver_name VARCHAR(255) NOT NULL, 
	approver_role VARCHAR(255) NOT NULL, 
	decision VARCHAR(30) NOT NULL, 
	comment TEXT, 
	decided_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	id UUID NOT NULL, 
	CONSTRAINT pk_new_employee_hiring_approval_decisions PRIMARY KEY (id), 
	CONSTRAINT uq_new_employee_hiring_approval_decisions_request_id_ap_576b UNIQUE (request_id, approval_cycle, stage_number), 
	CONSTRAINT fk_new_employee_hiring_approval_decisions_request_id_ne_0752 FOREIGN KEY(request_id) REFERENCES new_employee_hiring_requests (id) ON DELETE CASCADE, 
	CONSTRAINT fk_new_employee_hiring_approval_decisions_approver_user_c9a6 FOREIGN KEY(approver_user_id) REFERENCES user_accounts (id) ON DELETE RESTRICT
);

CREATE INDEX ix_new_employee_hiring_approval_decisions_request_id ON new_employee_hiring_approval_decisions (request_id);

CREATE TABLE new_employee_hiring_dispatches (
	request_id UUID NOT NULL, 
	recipient_type VARCHAR(30) NOT NULL, 
	assigned_user_id UUID NOT NULL, 
	assigned_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	acknowledged_at TIMESTAMP WITH TIME ZONE, 
	status VARCHAR(30) NOT NULL, 
	id UUID NOT NULL, 
	revision INTEGER NOT NULL, 
	CONSTRAINT pk_new_employee_hiring_dispatches PRIMARY KEY (id), 
	CONSTRAINT uq_new_employee_hiring_dispatches_request_id_recipient_type UNIQUE (request_id, recipient_type), 
	CONSTRAINT fk_new_employee_hiring_dispatches_request_id_new_employ_695d FOREIGN KEY(request_id) REFERENCES new_employee_hiring_requests (id) ON DELETE CASCADE, 
	CONSTRAINT fk_new_employee_hiring_dispatches_assigned_user_id_user_50b4 FOREIGN KEY(assigned_user_id) REFERENCES user_accounts (id) ON DELETE RESTRICT
);

CREATE INDEX ix_new_employee_hiring_dispatches_request_id ON new_employee_hiring_dispatches (request_id);

CREATE INDEX ix_new_employee_hiring_dispatches_assigned_user_id ON new_employee_hiring_dispatches (assigned_user_id);

CREATE TABLE vacancy_publications (
	vacancy_id UUID NOT NULL, 
	channel_id UUID NOT NULL, 
	status VARCHAR(30) NOT NULL, 
	external_reference VARCHAR(1000), 
	published_at TIMESTAMP WITH TIME ZONE, 
	responsible_employee_id UUID NOT NULL, 
	manual BOOLEAN NOT NULL, 
	id UUID NOT NULL, 
	revision INTEGER NOT NULL, 
	CONSTRAINT pk_vacancy_publications PRIMARY KEY (id), 
	CONSTRAINT uq_vacancy_publications_vacancy_id_channel_id UNIQUE (vacancy_id, channel_id), 
	CONSTRAINT fk_vacancy_publications_vacancy_id_vacancies FOREIGN KEY(vacancy_id) REFERENCES vacancies (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_vacancy_publications_channel_id_vacancy_publication_channels FOREIGN KEY(channel_id) REFERENCES vacancy_publication_channels (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_vacancy_publications_responsible_employee_id_employees FOREIGN KEY(responsible_employee_id) REFERENCES employees (id) ON DELETE RESTRICT
);

CREATE TABLE candidate_applications (
	candidate_id UUID NOT NULL, 
	vacancy_id UUID NOT NULL, 
	status VARCHAR(40) NOT NULL, 
	current_stage VARCHAR(40) NOT NULL, 
	source VARCHAR(100) NOT NULL, 
	applied_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	withdrawn_at TIMESTAMP WITH TIME ZONE, 
	rejection_reason_code VARCHAR(100), 
	rejection_comment TEXT, 
	id UUID NOT NULL, 
	revision INTEGER NOT NULL, 
	CONSTRAINT pk_candidate_applications PRIMARY KEY (id), 
	CONSTRAINT uq_candidate_applications_candidate_id_vacancy_id UNIQUE (candidate_id, vacancy_id), 
	CONSTRAINT fk_candidate_applications_candidate_id_candidates FOREIGN KEY(candidate_id) REFERENCES candidates (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_candidate_applications_vacancy_id_vacancies FOREIGN KEY(vacancy_id) REFERENCES vacancies (id) ON DELETE RESTRICT
);

CREATE INDEX ix_candidate_applications_candidate_id ON candidate_applications (candidate_id);

CREATE INDEX ix_candidate_applications_vacancy_id ON candidate_applications (vacancy_id);

CREATE INDEX ix_candidate_applications_status ON candidate_applications (status);

CREATE TABLE regulated_candidate_consents (
	organization_id UUID NOT NULL, 
	candidate_id UUID NOT NULL, 
	vacancy_id UUID NOT NULL, 
	consent_version INTEGER NOT NULL, 
	purposes JSONB NOT NULL, 
	granted BOOLEAN NOT NULL, 
	reserve_granted BOOLEAN NOT NULL, 
	reference_checks_granted BOOLEAN NOT NULL, 
	granted_at TIMESTAMP WITH TIME ZONE, 
	withdrawn_at TIMESTAMP WITH TIME ZONE, 
	retention_until DATE, 
	evidence_document_id UUID, 
	id UUID NOT NULL, 
	revision INTEGER NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_regulated_candidate_consents PRIMARY KEY (id), 
	CONSTRAINT uq_regulated_candidate_consents_candidate_id_vacancy_id_13fe UNIQUE (candidate_id, vacancy_id, consent_version), 
	CONSTRAINT fk_regulated_candidate_consents_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_regulated_candidate_consents_candidate_id_candidates FOREIGN KEY(candidate_id) REFERENCES candidates (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_regulated_candidate_consents_vacancy_id_vacancies FOREIGN KEY(vacancy_id) REFERENCES vacancies (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_regulated_candidate_consents_evidence_document_id_do_a4fd FOREIGN KEY(evidence_document_id) REFERENCES document_records (id) ON DELETE RESTRICT
);

CREATE INDEX ix_regulated_candidate_consents_organization_id ON regulated_candidate_consents (organization_id);

CREATE INDEX ix_regulated_candidate_consents_candidate_id ON regulated_candidate_consents (candidate_id);

CREATE INDEX ix_regulated_candidate_consents_vacancy_id ON regulated_candidate_consents (vacancy_id);

CREATE TABLE offboarding_tasks (
	termination_case_id UUID NOT NULL, 
	task_type VARCHAR(50) NOT NULL, 
	assigned_user_id UUID, 
	assigned_employee_id UUID, 
	assigned_unit_id UUID, 
	status VARCHAR(30) NOT NULL, 
	due_at TIMESTAMP WITH TIME ZONE, 
	completed_at TIMESTAMP WITH TIME ZONE, 
	evidence JSONB NOT NULL, 
	restricted_notes TEXT, 
	id UUID NOT NULL, 
	revision INTEGER NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_offboarding_tasks PRIMARY KEY (id), 
	CONSTRAINT uq_offboarding_tasks_termination_case_id_task_type UNIQUE (termination_case_id, task_type), 
	CONSTRAINT fk_offboarding_tasks_termination_case_id_termination_cases FOREIGN KEY(termination_case_id) REFERENCES termination_cases (id) ON DELETE CASCADE, 
	CONSTRAINT fk_offboarding_tasks_assigned_user_id_user_accounts FOREIGN KEY(assigned_user_id) REFERENCES user_accounts (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_offboarding_tasks_assigned_employee_id_employees FOREIGN KEY(assigned_employee_id) REFERENCES employees (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_offboarding_tasks_assigned_unit_id_organization_units FOREIGN KEY(assigned_unit_id) REFERENCES organization_units (id) ON DELETE RESTRICT
);

CREATE INDEX ix_offboarding_tasks_termination_case_id ON offboarding_tasks (termination_case_id);

CREATE TABLE candidate_screenings (
	application_id UUID NOT NULL, 
	reviewer_user_id UUID NOT NULL, 
	criteria_results JSONB NOT NULL, 
	decision VARCHAR(30) NOT NULL, 
	comment TEXT NOT NULL, 
	reviewed_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	id UUID NOT NULL, 
	revision INTEGER NOT NULL, 
	CONSTRAINT pk_candidate_screenings PRIMARY KEY (id), 
	CONSTRAINT fk_candidate_screenings_application_id_candidate_applications FOREIGN KEY(application_id) REFERENCES candidate_applications (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_candidate_screenings_reviewer_user_id_user_accounts FOREIGN KEY(reviewer_user_id) REFERENCES user_accounts (id) ON DELETE RESTRICT
);

CREATE INDEX ix_candidate_screenings_application_id ON candidate_screenings (application_id);

CREATE TABLE interviews (
	application_id UUID NOT NULL, 
	round_number INTEGER NOT NULL, 
	scheduled_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	format VARCHAR(30) NOT NULL, 
	location_reference VARCHAR(1000), 
	status VARCHAR(30) NOT NULL, 
	restricted_notes TEXT, 
	id UUID NOT NULL, 
	revision INTEGER NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_interviews PRIMARY KEY (id), 
	CONSTRAINT fk_interviews_application_id_candidate_applications FOREIGN KEY(application_id) REFERENCES candidate_applications (id) ON DELETE RESTRICT
);

CREATE INDEX ix_interviews_application_id ON interviews (application_id);

CREATE TABLE competition_commission_decisions (
	commission_id UUID NOT NULL, 
	application_id UUID NOT NULL, 
	decision VARCHAR(50) NOT NULL, 
	comment TEXT NOT NULL, 
	decided_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	id UUID NOT NULL, 
	CONSTRAINT pk_competition_commission_decisions PRIMARY KEY (id), 
	CONSTRAINT uq_competition_commission_decisions_commission_id_appli_a449 UNIQUE (commission_id, application_id), 
	CONSTRAINT fk_competition_commission_decisions_commission_id_compe_4730 FOREIGN KEY(commission_id) REFERENCES competition_commissions (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_competition_commission_decisions_application_id_cand_7ab6 FOREIGN KEY(application_id) REFERENCES candidate_applications (id) ON DELETE RESTRICT
);

CREATE TABLE job_offers (
	application_id UUID NOT NULL, 
	position_definition_id UUID NOT NULL, 
	staffing_slot_id UUID NOT NULL, 
	proposed_conditions JSONB NOT NULL, 
	proposed_start_date DATE NOT NULL, 
	expiration_date DATE NOT NULL, 
	status VARCHAR(30) NOT NULL, 
	accepted_at TIMESTAMP WITH TIME ZONE, 
	declined_at TIMESTAMP WITH TIME ZONE, 
	decline_reason TEXT, 
	document_id UUID, 
	id UUID NOT NULL, 
	revision INTEGER NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_job_offers PRIMARY KEY (id), 
	CONSTRAINT uq_job_offers_application_id UNIQUE (application_id), 
	CONSTRAINT fk_job_offers_application_id_candidate_applications FOREIGN KEY(application_id) REFERENCES candidate_applications (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_job_offers_position_definition_id_position_definitions FOREIGN KEY(position_definition_id) REFERENCES position_definitions (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_job_offers_staffing_slot_id_staffing_slots FOREIGN KEY(staffing_slot_id) REFERENCES staffing_slots (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_job_offers_document_id_document_records FOREIGN KEY(document_id) REFERENCES document_records (id) ON DELETE RESTRICT
);

CREATE TABLE hiring_cases (
	organization_id UUID NOT NULL, 
	candidate_application_id UUID NOT NULL, 
	recruitment_request_id UUID NOT NULL, 
	staffing_slot_id UUID NOT NULL, 
	proposed_start_date DATE NOT NULL, 
	status VARCHAR(50) NOT NULL, 
	process_instance_id UUID, 
	person_id UUID, 
	employee_id UUID, 
	assignment_id UUID, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	completed_at TIMESTAMP WITH TIME ZONE, 
	id UUID NOT NULL, 
	revision INTEGER NOT NULL, 
	CONSTRAINT pk_hiring_cases PRIMARY KEY (id), 
	CONSTRAINT fk_hiring_cases_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
	CONSTRAINT uq_hiring_cases_candidate_application_id UNIQUE (candidate_application_id), 
	CONSTRAINT fk_hiring_cases_candidate_application_id_candidate_applications FOREIGN KEY(candidate_application_id) REFERENCES candidate_applications (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_hiring_cases_recruitment_request_id_recruitment_requests FOREIGN KEY(recruitment_request_id) REFERENCES recruitment_requests (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_hiring_cases_staffing_slot_id_staffing_slots FOREIGN KEY(staffing_slot_id) REFERENCES staffing_slots (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_hiring_cases_process_instance_id_process_instances FOREIGN KEY(process_instance_id) REFERENCES process_instances (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_hiring_cases_person_id_people FOREIGN KEY(person_id) REFERENCES people (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_hiring_cases_employee_id_employees FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_hiring_cases_assignment_id_employee_assignments FOREIGN KEY(assignment_id) REFERENCES employee_assignments (id) ON DELETE RESTRICT
);

CREATE INDEX ix_hiring_cases_status ON hiring_cases (status);

CREATE INDEX ix_hiring_cases_organization_id ON hiring_cases (organization_id);

CREATE TABLE regulated_hiring_cases (
	organization_id UUID NOT NULL, 
	recruitment_request_id UUID NOT NULL, 
	staffing_slot_id UUID NOT NULL, 
	candidate_application_id UUID, 
	business_key VARCHAR(200) NOT NULL, 
	status VARCHAR(30) NOT NULL, 
	current_stage_code VARCHAR(100) NOT NULL, 
	current_stage_sequence INTEGER NOT NULL, 
	process_engine VARCHAR(30) NOT NULL, 
	camunda_process_instance_key VARCHAR(100), 
	initiated_by_user_id UUID NOT NULL, 
	started_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	completed_at TIMESTAMP WITH TIME ZONE, 
	cancelled_at TIMESTAMP WITH TIME ZONE, 
	terminal_reason TEXT, 
	id UUID NOT NULL, 
	revision INTEGER NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_regulated_hiring_cases PRIMARY KEY (id), 
	CONSTRAINT uq_regulated_hiring_cases_organization_id_business_key UNIQUE (organization_id, business_key), 
	CONSTRAINT uq_regulated_hiring_cases_recruitment_request_id UNIQUE (recruitment_request_id), 
	CONSTRAINT fk_regulated_hiring_cases_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_regulated_hiring_cases_recruitment_request_id_recrui_20c8 FOREIGN KEY(recruitment_request_id) REFERENCES recruitment_requests (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_regulated_hiring_cases_staffing_slot_id_staffing_slots FOREIGN KEY(staffing_slot_id) REFERENCES staffing_slots (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_regulated_hiring_cases_candidate_application_id_cand_f920 FOREIGN KEY(candidate_application_id) REFERENCES candidate_applications (id) ON DELETE RESTRICT, 
	CONSTRAINT uq_regulated_hiring_cases_camunda_process_instance_key UNIQUE (camunda_process_instance_key), 
	CONSTRAINT fk_regulated_hiring_cases_initiated_by_user_id_user_accounts FOREIGN KEY(initiated_by_user_id) REFERENCES user_accounts (id) ON DELETE RESTRICT
);

CREATE INDEX ix_regulated_hiring_cases_organization_id ON regulated_hiring_cases (organization_id);

CREATE INDEX ix_regulated_hiring_cases_current_stage_code ON regulated_hiring_cases (current_stage_code);

CREATE INDEX ix_regulated_hiring_cases_scope_status ON regulated_hiring_cases (organization_id, status);

CREATE INDEX ix_regulated_hiring_cases_status ON regulated_hiring_cases (status);

CREATE TABLE regulated_commission_evaluations (
	commission_id UUID NOT NULL, 
	application_id UUID NOT NULL, 
	member_employee_id UUID NOT NULL, 
	version_number INTEGER NOT NULL, 
	criterion_scores JSONB NOT NULL, 
	total_score NUMERIC(5, 2) NOT NULL, 
	recommendation VARCHAR(30) NOT NULL, 
	factual_basis JSONB NOT NULL, 
	conflict_declared BOOLEAN NOT NULL, 
	amended_from_id UUID, 
	submitted_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	id UUID NOT NULL, 
	CONSTRAINT pk_regulated_commission_evaluations PRIMARY KEY (id), 
	CONSTRAINT uq_regulated_commission_evaluations_commission_id_appli_cab4 UNIQUE (commission_id, application_id, member_employee_id, version_number), 
	CONSTRAINT ck_regulated_commission_evaluations_regulated_commission_score CHECK (total_score >= 0 AND total_score <= 100), 
	CONSTRAINT fk_regulated_commission_evaluations_commission_id_compe_7ce8 FOREIGN KEY(commission_id) REFERENCES competition_commissions (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_regulated_commission_evaluations_application_id_cand_5685 FOREIGN KEY(application_id) REFERENCES candidate_applications (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_regulated_commission_evaluations_member_employee_id__f8ff FOREIGN KEY(member_employee_id) REFERENCES employees (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_regulated_commission_evaluations_amended_from_id_reg_fe19 FOREIGN KEY(amended_from_id) REFERENCES regulated_commission_evaluations (id) ON DELETE RESTRICT
);

CREATE INDEX ix_regulated_commission_evaluations_commission_id ON regulated_commission_evaluations (commission_id);

CREATE INDEX ix_regulated_commission_evaluations_application_id ON regulated_commission_evaluations (application_id);

CREATE TABLE offboarding_waivers (
	offboarding_task_id UUID NOT NULL, 
	authorized_by_user_id UUID NOT NULL, 
	reason TEXT NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	id UUID NOT NULL, 
	CONSTRAINT pk_offboarding_waivers PRIMARY KEY (id), 
	CONSTRAINT uq_offboarding_waivers_offboarding_task_id UNIQUE (offboarding_task_id), 
	CONSTRAINT fk_offboarding_waivers_offboarding_task_id_offboarding_tasks FOREIGN KEY(offboarding_task_id) REFERENCES offboarding_tasks (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_offboarding_waivers_authorized_by_user_id_user_accounts FOREIGN KEY(authorized_by_user_id) REFERENCES user_accounts (id) ON DELETE RESTRICT
);

CREATE TABLE interview_participants (
	interview_id UUID NOT NULL, 
	employee_id UUID NOT NULL, 
	role VARCHAR(50) NOT NULL, 
	required BOOLEAN NOT NULL, 
	id UUID NOT NULL, 
	CONSTRAINT pk_interview_participants PRIMARY KEY (id), 
	CONSTRAINT uq_interview_participants_interview_id_employee_id UNIQUE (interview_id, employee_id), 
	CONSTRAINT fk_interview_participants_interview_id_interviews FOREIGN KEY(interview_id) REFERENCES interviews (id) ON DELETE CASCADE, 
	CONSTRAINT fk_interview_participants_employee_id_employees FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE RESTRICT
);

CREATE TABLE interview_evaluations (
	interview_id UUID NOT NULL, 
	interviewer_employee_id UUID NOT NULL, 
	version_number INTEGER NOT NULL, 
	criteria_results JSONB NOT NULL, 
	recommendation VARCHAR(50) NOT NULL, 
	comment TEXT NOT NULL, 
	submitted_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	amended_from_id UUID, 
	id UUID NOT NULL, 
	CONSTRAINT pk_interview_evaluations PRIMARY KEY (id), 
	CONSTRAINT uq_interview_evaluations_interview_id_interviewer_emplo_19c4 UNIQUE (interview_id, interviewer_employee_id, version_number), 
	CONSTRAINT fk_interview_evaluations_interview_id_interviews FOREIGN KEY(interview_id) REFERENCES interviews (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_interview_evaluations_interviewer_employee_id_employees FOREIGN KEY(interviewer_employee_id) REFERENCES employees (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_interview_evaluations_amended_from_id_interview_evaluations FOREIGN KEY(amended_from_id) REFERENCES interview_evaluations (id) ON DELETE RESTRICT
);

CREATE TABLE onboarding_tasks (
	hiring_case_id UUID NOT NULL, 
	task_type VARCHAR(50) NOT NULL, 
	assigned_unit_id UUID, 
	assigned_employee_id UUID, 
	status VARCHAR(30) NOT NULL, 
	due_at TIMESTAMP WITH TIME ZONE, 
	completed_at TIMESTAMP WITH TIME ZONE, 
	completion_evidence JSONB NOT NULL, 
	id UUID NOT NULL, 
	revision INTEGER NOT NULL, 
	CONSTRAINT pk_onboarding_tasks PRIMARY KEY (id), 
	CONSTRAINT fk_onboarding_tasks_hiring_case_id_hiring_cases FOREIGN KEY(hiring_case_id) REFERENCES hiring_cases (id) ON DELETE CASCADE, 
	CONSTRAINT fk_onboarding_tasks_assigned_unit_id_organization_units FOREIGN KEY(assigned_unit_id) REFERENCES organization_units (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_onboarding_tasks_assigned_employee_id_employees FOREIGN KEY(assigned_employee_id) REFERENCES employees (id) ON DELETE RESTRICT
);

CREATE INDEX ix_onboarding_tasks_hiring_case_id ON onboarding_tasks (hiring_case_id);

CREATE TABLE regulated_hiring_stage_executions (
	case_id UUID NOT NULL, 
	stage_definition_id UUID NOT NULL, 
	stage_code VARCHAR(100) NOT NULL, 
	stage_sequence INTEGER NOT NULL, 
	cycle INTEGER NOT NULL, 
	status VARCHAR(30) NOT NULL, 
	assigned_user_id UUID, 
	assigned_employee_id UUID, 
	started_at TIMESTAMP WITH TIME ZONE, 
	due_at TIMESTAMP WITH TIME ZONE, 
	completed_at TIMESTAMP WITH TIME ZONE, 
	decision VARCHAR(30), 
	decision_comment TEXT, 
	evidence JSONB NOT NULL, 
	id UUID NOT NULL, 
	revision INTEGER NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_regulated_hiring_stage_executions PRIMARY KEY (id), 
	CONSTRAINT uq_regulated_hiring_stage_executions_case_id_stage_code_cycle UNIQUE (case_id, stage_code, cycle), 
	CONSTRAINT ck_regulated_hiring_stage_executions_regulated_hiring_s_613a CHECK (cycle > 0), 
	CONSTRAINT fk_regulated_hiring_stage_executions_case_id_regulated__8cfe FOREIGN KEY(case_id) REFERENCES regulated_hiring_cases (id) ON DELETE CASCADE, 
	CONSTRAINT fk_regulated_hiring_stage_executions_stage_definition_i_87a6 FOREIGN KEY(stage_definition_id) REFERENCES regulated_hiring_stage_definitions (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_regulated_hiring_stage_executions_assigned_user_id_u_24e5 FOREIGN KEY(assigned_user_id) REFERENCES user_accounts (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_regulated_hiring_stage_executions_assigned_employee__f5f4 FOREIGN KEY(assigned_employee_id) REFERENCES employees (id) ON DELETE RESTRICT
);

CREATE INDEX ix_regulated_hiring_stage_execution_active ON regulated_hiring_stage_executions (case_id, status, due_at);

CREATE INDEX ix_regulated_hiring_stage_executions_status ON regulated_hiring_stage_executions (status);

CREATE INDEX ix_regulated_hiring_stage_executions_case_id ON regulated_hiring_stage_executions (case_id);

CREATE TABLE regulated_hiring_form_records (
	case_id UUID NOT NULL, 
	form_definition_id UUID NOT NULL, 
	record_version INTEGER NOT NULL, 
	status VARCHAR(30) NOT NULL, 
	data JSONB NOT NULL, 
	created_by_user_id UUID NOT NULL, 
	signed_by JSONB NOT NULL, 
	signed_at TIMESTAMP WITH TIME ZONE, 
	document_id UUID, 
	supersedes_record_id UUID, 
	correction_reason TEXT, 
	id UUID NOT NULL, 
	revision INTEGER NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_regulated_hiring_form_records PRIMARY KEY (id), 
	CONSTRAINT uq_regulated_hiring_form_records_case_id_form_definitio_d618 UNIQUE (case_id, form_definition_id, record_version), 
	CONSTRAINT ck_regulated_hiring_form_records_regulated_hiring_form__0d87 CHECK (record_version > 0), 
	CONSTRAINT fk_regulated_hiring_form_records_case_id_regulated_hiring_cases FOREIGN KEY(case_id) REFERENCES regulated_hiring_cases (id) ON DELETE CASCADE, 
	CONSTRAINT fk_regulated_hiring_form_records_form_definition_id_reg_bede FOREIGN KEY(form_definition_id) REFERENCES regulated_hiring_form_definitions (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_regulated_hiring_form_records_created_by_user_id_use_a581 FOREIGN KEY(created_by_user_id) REFERENCES user_accounts (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_regulated_hiring_form_records_document_id_document_records FOREIGN KEY(document_id) REFERENCES document_records (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_regulated_hiring_form_records_supersedes_record_id_r_ad98 FOREIGN KEY(supersedes_record_id) REFERENCES regulated_hiring_form_records (id) ON DELETE RESTRICT
);

CREATE INDEX ix_regulated_hiring_form_records_status ON regulated_hiring_form_records (status);

CREATE INDEX ix_regulated_hiring_form_records_case_id ON regulated_hiring_form_records (case_id);

CREATE TABLE regulated_employment_registrations (
	case_id UUID NOT NULL, 
	contract_document_id UUID, 
	contract_signed_by_employer_at TIMESTAMP WITH TIME ZONE, 
	contract_signed_by_candidate_at TIMESTAMP WITH TIME ZONE, 
	order_document_id UUID, 
	order_signed_at TIMESTAMP WITH TIME ZONE, 
	order_acknowledged_at TIMESTAMP WITH TIME ZONE, 
	planned_start_date DATE NOT NULL, 
	esutd_due_date DATE, 
	esutd_submitted_at TIMESTAMP WITH TIME ZONE, 
	esutd_confirmation VARCHAR(500), 
	personnel_file_created_at TIMESTAMP WITH TIME ZONE, 
	admitted_to_work_at TIMESTAMP WITH TIME ZONE, 
	id UUID NOT NULL, 
	revision INTEGER NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_regulated_employment_registrations PRIMARY KEY (id), 
	CONSTRAINT uq_regulated_employment_registrations_case_id UNIQUE (case_id), 
	CONSTRAINT fk_regulated_employment_registrations_case_id_regulated_95ce FOREIGN KEY(case_id) REFERENCES regulated_hiring_cases (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_regulated_employment_registrations_contract_document_fc3d FOREIGN KEY(contract_document_id) REFERENCES document_records (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_regulated_employment_registrations_order_document_id_2677 FOREIGN KEY(order_document_id) REFERENCES document_records (id) ON DELETE RESTRICT
);

CREATE INDEX ix_regulated_employment_registrations_case_id ON regulated_employment_registrations (case_id);

CREATE TABLE regulated_probation_plans (
	case_id UUID NOT NULL, 
	employee_id UUID, 
	duration_months INTEGER NOT NULL, 
	goals_30 JSONB NOT NULL, 
	goals_60 JSONB NOT NULL, 
	goals_90 JSONB NOT NULL, 
	signed_by_manager_at TIMESTAMP WITH TIME ZONE, 
	signed_by_employee_at TIMESTAMP WITH TIME ZONE, 
	review_30 JSONB, 
	review_60 JSONB, 
	final_review JSONB, 
	legal_review_required BOOLEAN NOT NULL, 
	legal_reviewed_at TIMESTAMP WITH TIME ZONE, 
	result VARCHAR(30), 
	id UUID NOT NULL, 
	revision INTEGER NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_regulated_probation_plans PRIMARY KEY (id), 
	CONSTRAINT uq_regulated_probation_plans_case_id UNIQUE (case_id), 
	CONSTRAINT ck_regulated_probation_plans_regulated_probation_duration CHECK (duration_months > 0 AND duration_months <= 6), 
	CONSTRAINT fk_regulated_probation_plans_case_id_regulated_hiring_cases FOREIGN KEY(case_id) REFERENCES regulated_hiring_cases (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_regulated_probation_plans_employee_id_employees FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE RESTRICT
);

CREATE INDEX ix_regulated_probation_plans_case_id ON regulated_probation_plans (case_id);

CREATE TABLE regulated_hiring_stage_actions (
	case_id UUID NOT NULL, 
	stage_execution_id UUID NOT NULL, 
	actor_user_id UUID NOT NULL, 
	action VARCHAR(30) NOT NULL, 
	reason TEXT, 
	safe_metadata JSONB NOT NULL, 
	idempotency_key VARCHAR(200) NOT NULL, 
	occurred_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	id UUID NOT NULL, 
	CONSTRAINT pk_regulated_hiring_stage_actions PRIMARY KEY (id), 
	CONSTRAINT fk_regulated_hiring_stage_actions_case_id_regulated_hir_5b9c FOREIGN KEY(case_id) REFERENCES regulated_hiring_cases (id) ON DELETE CASCADE, 
	CONSTRAINT fk_regulated_hiring_stage_actions_stage_execution_id_re_c8e5 FOREIGN KEY(stage_execution_id) REFERENCES regulated_hiring_stage_executions (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_regulated_hiring_stage_actions_actor_user_id_user_accounts FOREIGN KEY(actor_user_id) REFERENCES user_accounts (id) ON DELETE RESTRICT, 
	CONSTRAINT uq_regulated_hiring_stage_actions_idempotency_key UNIQUE (idempotency_key)
);

CREATE INDEX ix_regulated_hiring_stage_actions_case_time ON regulated_hiring_stage_actions (case_id, occurred_at);

CREATE INDEX ix_regulated_hiring_stage_actions_case_id ON regulated_hiring_stage_actions (case_id);

ALTER TABLE employees ADD CONSTRAINT fk_employees_created_by_user_accounts FOREIGN KEY(created_by) REFERENCES user_accounts (id) ON DELETE RESTRICT;

