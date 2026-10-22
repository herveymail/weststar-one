CREATE TABLE "assets" (
	"id" serial PRIMARY KEY NOT NULL,
	"client_id" integer NOT NULL,
	"name" varchar(500) NOT NULL,
	"type" varchar(500),
	"status" varchar(500) DEFAULT 'Active',
	"make" varchar(500),
	"model" varchar(500),
	"serial" varchar(500),
	"os" varchar(500),
	"ip" varchar(500),
	"mac" varchar(500),
	"purchase_date" date,
	"warranty_expires" date,
	"notes" text,
	"legacy_id" integer,
	"created_by" integer,
	"archived_at" timestamp with time zone,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "audit_log" (
	"id" serial PRIMARY KEY NOT NULL,
	"user_id" integer,
	"action" varchar(40) NOT NULL,
	"entity" varchar(60) NOT NULL,
	"entity_id" varchar(60),
	"summary" varchar(500),
	"changes" jsonb,
	"ip" varchar(64),
	"created_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "backup_jobs" (
	"id" serial PRIMARY KEY NOT NULL,
	"device" varchar(500) NOT NULL,
	"client_id" integer,
	"plan" varchar(500),
	"last_run_at" timestamp with time zone,
	"last_result" varchar(500) DEFAULT 'Unknown',
	"storage_gb" numeric(14, 2),
	"legacy_id" integer,
	"created_by" integer,
	"archived_at" timestamp with time zone,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "bank_transactions" (
	"id" serial PRIMARY KEY NOT NULL,
	"posted_on" date NOT NULL,
	"description" varchar(500) NOT NULL,
	"account" varchar(500),
	"amount" numeric(14, 2) NOT NULL,
	"match_status" varchar(500) DEFAULT 'Unmatched',
	"invoice_id" integer,
	"notes" text,
	"legacy_id" integer,
	"created_by" integer,
	"archived_at" timestamp with time zone,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "calendar_events" (
	"id" serial PRIMARY KEY NOT NULL,
	"title" varchar(500) NOT NULL,
	"starts_at" timestamp with time zone NOT NULL,
	"ends_at" timestamp with time zone,
	"user_id" integer,
	"client_id" integer,
	"location" varchar(500),
	"notes" text,
	"legacy_id" integer,
	"created_by" integer,
	"archived_at" timestamp with time zone,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "campaigns" (
	"id" serial PRIMARY KEY NOT NULL,
	"name" varchar(500) NOT NULL,
	"type" varchar(500) DEFAULT 'Email',
	"audience" varchar(500),
	"status" varchar(500) DEFAULT 'Draft',
	"send_date" date,
	"subject" varchar(500),
	"body" text,
	"legacy_id" integer,
	"created_by" integer,
	"archived_at" timestamp with time zone,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "client_notes" (
	"id" serial PRIMARY KEY NOT NULL,
	"client_id" integer NOT NULL,
	"title" varchar(500) NOT NULL,
	"body" text,
	"legacy_id" integer,
	"created_by" integer,
	"archived_at" timestamp with time zone,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "clients" (
	"id" serial PRIMARY KEY NOT NULL,
	"name" varchar(200) NOT NULL,
	"status" varchar(500) DEFAULT 'Active',
	"type" varchar(500) DEFAULT 'Business',
	"plan" varchar(500),
	"industry" varchar(500),
	"phone" varchar(500),
	"email" varchar(500),
	"website" varchar(500),
	"address" varchar(500),
	"city" varchar(500),
	"state" varchar(500),
	"zip" varchar(500),
	"account_manager_id" integer,
	"hourly_rate" numeric(14, 2),
	"tax_rate" numeric(14, 2),
	"net_terms" integer DEFAULT 30,
	"sla_response_hours" integer DEFAULT 4,
	"sla_resolution_hours" integer DEFAULT 24,
	"account_alert" varchar(500),
	"notes" text,
	"legacy_id" integer,
	"created_by" integer,
	"archived_at" timestamp with time zone,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "contacts" (
	"id" serial PRIMARY KEY NOT NULL,
	"client_id" integer NOT NULL,
	"name" varchar(500) NOT NULL,
	"title" varchar(500),
	"email" varchar(500),
	"phone" varchar(500),
	"mobile" varchar(500),
	"role" varchar(500) DEFAULT 'Other',
	"is_primary" boolean,
	"notes" text,
	"legacy_id" integer,
	"created_by" integer,
	"archived_at" timestamp with time zone,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "contracts" (
	"id" serial PRIMARY KEY NOT NULL,
	"number" varchar(500),
	"name" varchar(500) NOT NULL,
	"client_id" integer NOT NULL,
	"type" varchar(500) DEFAULT 'Managed',
	"status" varchar(500) DEFAULT 'Draft',
	"start_date" date,
	"end_date" date,
	"auto_renew" boolean DEFAULT true,
	"monthly_rate" numeric(14, 2),
	"included_hours" numeric(14, 2),
	"overage_rate" numeric(14, 2),
	"scope" text,
	"terms" text,
	"legacy_id" integer,
	"created_by" integer,
	"archived_at" timestamp with time zone,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "counters" (
	"name" varchar(60) PRIMARY KEY NOT NULL,
	"value" integer NOT NULL
);
--> statement-breakpoint
CREATE TABLE "domains" (
	"id" serial PRIMARY KEY NOT NULL,
	"name" varchar(500) NOT NULL,
	"client_id" integer,
	"registrar" varchar(500),
	"expires_on" date,
	"dns_provider" varchar(500),
	"ssl_status" varchar(500) DEFAULT 'Unknown',
	"ssl_expires_on" date,
	"notes" text,
	"legacy_id" integer,
	"created_by" integer,
	"archived_at" timestamp with time zone,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "hr_employees" (
	"id" serial PRIMARY KEY NOT NULL,
	"name" varchar(500) NOT NULL,
	"user_id" integer,
	"title" varchar(500),
	"office" varchar(500),
	"status" varchar(500) DEFAULT 'Active',
	"hire_date" date,
	"email" varchar(500),
	"phone" varchar(500),
	"pay_type" varchar(500),
	"pto_balance_hours" numeric(14, 2),
	"ssn" text,
	"bank_routing" text,
	"bank_account" text,
	"emergency_contact" varchar(500),
	"legacy_id" integer,
	"created_by" integer,
	"archived_at" timestamp with time zone,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "expenses" (
	"id" serial PRIMARY KEY NOT NULL,
	"spent_on" date NOT NULL,
	"vendor_id" integer,
	"category" varchar(500),
	"amount" numeric(14, 2) NOT NULL,
	"client_id" integer,
	"billable" boolean,
	"description" varchar(500),
	"legacy_id" integer,
	"created_by" integer,
	"archived_at" timestamp with time zone,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "import_runs" (
	"id" serial PRIMARY KEY NOT NULL,
	"started_at" timestamp with time zone DEFAULT now() NOT NULL,
	"finished_at" timestamp with time zone,
	"dry_run" boolean DEFAULT false NOT NULL,
	"summary" jsonb,
	"error" text
);
--> statement-breakpoint
CREATE TABLE "inventory_items" (
	"id" serial PRIMARY KEY NOT NULL,
	"name" varchar(500) NOT NULL,
	"sku" varchar(500),
	"on_hand" integer,
	"reorder_at" integer,
	"cost" numeric(14, 2),
	"price" numeric(14, 2),
	"location" varchar(500),
	"notes" text,
	"legacy_id" integer,
	"created_by" integer,
	"archived_at" timestamp with time zone,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "invoice_items" (
	"id" serial PRIMARY KEY NOT NULL,
	"invoice_id" integer NOT NULL,
	"description" varchar(500) NOT NULL,
	"qty" numeric(14, 2) DEFAULT 1,
	"rate" numeric(14, 2),
	"taxable" boolean DEFAULT true,
	"line_total" numeric(14, 2),
	"sort_order" integer,
	"legacy_id" integer,
	"created_by" integer,
	"archived_at" timestamp with time zone,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "invoices" (
	"id" serial PRIMARY KEY NOT NULL,
	"number" varchar(500),
	"client_id" integer NOT NULL,
	"status" varchar(500) DEFAULT 'Draft',
	"invoice_date" date NOT NULL,
	"due_date" date NOT NULL,
	"tax_rate" numeric(14, 2),
	"subtotal" numeric(14, 2),
	"tax_amount" numeric(14, 2),
	"total" numeric(14, 2),
	"amount_paid" numeric(14, 2),
	"scope" text,
	"notes" text,
	"legacy_id" integer,
	"created_by" integer,
	"archived_at" timestamp with time zone,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "kb_articles" (
	"id" serial PRIMARY KEY NOT NULL,
	"title" varchar(500) NOT NULL,
	"category" varchar(500),
	"visibility" varchar(500) DEFAULT 'Staff only',
	"views" integer,
	"body" text,
	"legacy_id" integer,
	"created_by" integer,
	"archived_at" timestamp with time zone,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "leads" (
	"id" serial PRIMARY KEY NOT NULL,
	"company" varchar(500) NOT NULL,
	"contact_name" varchar(500),
	"email" varchar(500),
	"phone" varchar(500),
	"stage" varchar(500) DEFAULT 'New',
	"source" varchar(500),
	"value" numeric(14, 2),
	"next_followup" date,
	"assigned_to" integer,
	"notes" text,
	"legacy_id" integer,
	"created_by" integer,
	"archived_at" timestamp with time zone,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "login_attempts" (
	"id" serial PRIMARY KEY NOT NULL,
	"email" varchar(254),
	"ip" varchar(64),
	"success" boolean NOT NULL,
	"reason" varchar(60),
	"created_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "secure_messages" (
	"id" serial PRIMARY KEY NOT NULL,
	"client_id" integer NOT NULL,
	"contact_id" integer,
	"subject" varchar(500) NOT NULL,
	"direction" varchar(500) DEFAULT 'Outbound',
	"status" varchar(500) DEFAULT 'Unread',
	"body" text,
	"legacy_id" integer,
	"created_by" integer,
	"archived_at" timestamp with time zone,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "mfa_recovery_codes" (
	"id" serial PRIMARY KEY NOT NULL,
	"user_id" integer NOT NULL,
	"code_hash" text NOT NULL,
	"used_at" timestamp with time zone,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "mileage_trips" (
	"id" serial PRIMARY KEY NOT NULL,
	"trip_date" date NOT NULL,
	"trip" varchar(500) NOT NULL,
	"miles" numeric(14, 2) NOT NULL,
	"client_id" integer,
	"billable" boolean,
	"user_id" integer,
	"legacy_id" integer,
	"created_by" integer,
	"archived_at" timestamp with time zone,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "client_networks" (
	"id" serial PRIMARY KEY NOT NULL,
	"client_id" integer NOT NULL,
	"name" varchar(500) NOT NULL,
	"subnet" varchar(500),
	"gateway" varchar(500),
	"dns" varchar(500),
	"isp" varchar(500),
	"isp_account" text,
	"wifi_ssid" varchar(500),
	"wifi_password" text,
	"notes" text,
	"legacy_id" integer,
	"created_by" integer,
	"archived_at" timestamp with time zone,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "policies" (
	"id" serial PRIMARY KEY NOT NULL,
	"name" varchar(500) NOT NULL,
	"client_id" integer,
	"version" varchar(500),
	"status" varchar(500) DEFAULT 'Draft',
	"next_review" date,
	"body" text,
	"legacy_id" integer,
	"created_by" integer,
	"archived_at" timestamp with time zone,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "projects" (
	"id" serial PRIMARY KEY NOT NULL,
	"number" varchar(500),
	"name" varchar(500) NOT NULL,
	"client_id" integer,
	"owner_id" integer,
	"status" varchar(500) DEFAULT 'Planning',
	"start_date" date,
	"due_date" date,
	"budget_hours" numeric(14, 2),
	"billable" boolean DEFAULT true,
	"description" text,
	"legacy_id" integer,
	"created_by" integer,
	"archived_at" timestamp with time zone,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "hr_pto_requests" (
	"id" serial PRIMARY KEY NOT NULL,
	"user_id" integer,
	"kind" varchar(500) DEFAULT 'Vacation',
	"starts_on" date NOT NULL,
	"ends_on" date NOT NULL,
	"hours" numeric(14, 2) NOT NULL,
	"status" varchar(500) DEFAULT 'Pending',
	"reason" varchar(500),
	"legacy_id" integer,
	"created_by" integer,
	"archived_at" timestamp with time zone,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "quote_items" (
	"id" serial PRIMARY KEY NOT NULL,
	"quote_id" integer NOT NULL,
	"description" varchar(500) NOT NULL,
	"qty" numeric(14, 2) DEFAULT 1,
	"rate" numeric(14, 2),
	"taxable" boolean DEFAULT true,
	"line_total" numeric(14, 2),
	"sort_order" integer,
	"legacy_id" integer,
	"created_by" integer,
	"archived_at" timestamp with time zone,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "quotes" (
	"id" serial PRIMARY KEY NOT NULL,
	"number" varchar(500),
	"client_id" integer NOT NULL,
	"status" varchar(500) DEFAULT 'Draft',
	"quote_date" date NOT NULL,
	"expires_on" date,
	"tax_rate" numeric(14, 2),
	"subtotal" numeric(14, 2),
	"tax_amount" numeric(14, 2),
	"total" numeric(14, 2),
	"scope" text,
	"notes" text,
	"legacy_id" integer,
	"created_by" integer,
	"archived_at" timestamp with time zone,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "recurring_invoices" (
	"id" serial PRIMARY KEY NOT NULL,
	"name" varchar(500) NOT NULL,
	"client_id" integer NOT NULL,
	"frequency" varchar(500) DEFAULT 'Month',
	"next_run" date NOT NULL,
	"status" varchar(500) DEFAULT 'Active',
	"autopay" boolean,
	"tax_rate" numeric(14, 2),
	"total" numeric(14, 2),
	"notes" text,
	"legacy_id" integer,
	"created_by" integer,
	"archived_at" timestamp with time zone,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "recurring_items" (
	"id" serial PRIMARY KEY NOT NULL,
	"recurring_id" integer NOT NULL,
	"description" varchar(500) NOT NULL,
	"qty" numeric(14, 2) DEFAULT 1,
	"rate" numeric(14, 2),
	"taxable" boolean DEFAULT true,
	"line_total" numeric(14, 2),
	"sort_order" integer,
	"legacy_id" integer,
	"created_by" integer,
	"archived_at" timestamp with time zone,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "renewals" (
	"id" serial PRIMARY KEY NOT NULL,
	"item" varchar(500) NOT NULL,
	"client_id" integer,
	"type" varchar(500),
	"renews_on" date NOT NULL,
	"cost" numeric(14, 2),
	"status" varchar(500) DEFAULT 'Upcoming',
	"notes" text,
	"legacy_id" integer,
	"created_by" integer,
	"archived_at" timestamp with time zone,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "rmm_devices" (
	"id" serial PRIMARY KEY NOT NULL,
	"name" varchar(500) NOT NULL,
	"client_id" integer,
	"os" varchar(500),
	"last_seen_at" timestamp with time zone,
	"status" varchar(500) DEFAULT 'OK',
	"rmm_uid" varchar(500),
	"legacy_id" integer,
	"created_by" integer,
	"archived_at" timestamp with time zone,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "sessions" (
	"id" varchar(64) PRIMARY KEY NOT NULL,
	"user_id" integer NOT NULL,
	"csrf_token" varchar(64) NOT NULL,
	"mfa_passed" boolean DEFAULT false NOT NULL,
	"ip" varchar(64),
	"user_agent" varchar(300),
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"last_seen_at" timestamp with time zone DEFAULT now() NOT NULL,
	"expires_at" timestamp with time zone NOT NULL,
	"revoked_at" timestamp with time zone
);
--> statement-breakpoint
CREATE TABLE "settings" (
	"key" varchar(120) PRIMARY KEY NOT NULL,
	"value" text DEFAULT '' NOT NULL,
	"is_secret" boolean DEFAULT false NOT NULL,
	"updated_by" integer,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "ticket_messages" (
	"id" serial PRIMARY KEY NOT NULL,
	"ticket_id" integer NOT NULL,
	"kind" varchar(10) NOT NULL,
	"author_user_id" integer,
	"author_name" varchar(200),
	"via" varchar(20) DEFAULT 'web' NOT NULL,
	"body" text NOT NULL,
	"legacy_id" integer,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "ticket_time_entries" (
	"id" serial PRIMARY KEY NOT NULL,
	"ticket_id" integer NOT NULL,
	"user_id" integer,
	"minutes" integer NOT NULL,
	"work_type" varchar(40) DEFAULT 'Remote' NOT NULL,
	"description" text DEFAULT '' NOT NULL,
	"billable" boolean DEFAULT true NOT NULL,
	"work_date" date NOT NULL,
	"invoice_id" integer,
	"legacy_id" integer,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "tickets" (
	"id" serial PRIMARY KEY NOT NULL,
	"number" varchar(30) NOT NULL,
	"subject" varchar(255) NOT NULL,
	"details" text DEFAULT '' NOT NULL,
	"client_id" integer,
	"contact_id" integer,
	"contact_name" varchar(150),
	"contact_email" varchar(254),
	"assigned_to" integer,
	"priority" varchar(20) DEFAULT 'Medium' NOT NULL,
	"status" varchar(30) DEFAULT 'New' NOT NULL,
	"category" varchar(100),
	"source" varchar(20) DEFAULT 'Manual' NOT NULL,
	"billable" boolean DEFAULT true NOT NULL,
	"due_date" date,
	"response_due_at" timestamp with time zone,
	"first_response_at" timestamp with time zone,
	"resolved_at" timestamp with time zone,
	"closed_at" timestamp with time zone,
	"sla_breached" boolean DEFAULT false NOT NULL,
	"created_by" integer,
	"legacy_id" integer,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "hr_timeclock" (
	"id" serial PRIMARY KEY NOT NULL,
	"user_id" integer,
	"clock_in" timestamp with time zone NOT NULL,
	"clock_out" timestamp with time zone,
	"status" varchar(500) DEFAULT 'Open',
	"notes" varchar(500),
	"legacy_id" integer,
	"created_by" integer,
	"archived_at" timestamp with time zone,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "training_assignments" (
	"id" serial PRIMARY KEY NOT NULL,
	"course" varchar(500) NOT NULL,
	"client_id" integer NOT NULL,
	"learners" integer,
	"due_date" date,
	"progress" integer,
	"status" varchar(500) DEFAULT 'Not started',
	"legacy_id" integer,
	"created_by" integer,
	"archived_at" timestamp with time zone,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "users" (
	"id" serial PRIMARY KEY NOT NULL,
	"email" varchar(254) NOT NULL,
	"name" varchar(200) NOT NULL,
	"password_hash" text NOT NULL,
	"role" varchar(20) DEFAULT 'tech' NOT NULL,
	"hr_access" boolean DEFAULT false NOT NULL,
	"title" varchar(100),
	"phone" varchar(50),
	"look" varchar(20) DEFAULT 'indigo' NOT NULL,
	"totp_secret_enc" text,
	"totp_pending_enc" text,
	"totp_last_step" integer,
	"mfa_enabled" boolean DEFAULT false NOT NULL,
	"failed_logins" integer DEFAULT 0 NOT NULL,
	"locked_until" timestamp with time zone,
	"last_login_at" timestamp with time zone,
	"password_changed_at" timestamp with time zone,
	"must_change_password" boolean DEFAULT false NOT NULL,
	"legacy_id" integer,
	"archived_at" timestamp with time zone,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "vendors" (
	"id" serial PRIMARY KEY NOT NULL,
	"name" varchar(500) NOT NULL,
	"category" varchar(500),
	"contact_name" varchar(500),
	"email" varchar(500),
	"phone" varchar(500),
	"website" varchar(500),
	"account_number" text,
	"notes" text,
	"legacy_id" integer,
	"created_by" integer,
	"archived_at" timestamp with time zone,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "workflows" (
	"id" serial PRIMARY KEY NOT NULL,
	"name" varchar(500) NOT NULL,
	"trigger" varchar(500) NOT NULL,
	"conditions" text,
	"action" varchar(500) NOT NULL,
	"action_value" varchar(500),
	"status" varchar(500) DEFAULT 'Active',
	"runs" integer,
	"legacy_id" integer,
	"created_by" integer,
	"archived_at" timestamp with time zone,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
ALTER TABLE "assets" ADD CONSTRAINT "assets_client_id_clients_id_fk" FOREIGN KEY ("client_id") REFERENCES "public"."clients"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "assets" ADD CONSTRAINT "assets_created_by_users_id_fk" FOREIGN KEY ("created_by") REFERENCES "public"."users"("id") ON DELETE set null ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "audit_log" ADD CONSTRAINT "audit_log_user_id_users_id_fk" FOREIGN KEY ("user_id") REFERENCES "public"."users"("id") ON DELETE set null ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "backup_jobs" ADD CONSTRAINT "backup_jobs_client_id_clients_id_fk" FOREIGN KEY ("client_id") REFERENCES "public"."clients"("id") ON DELETE set null ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "backup_jobs" ADD CONSTRAINT "backup_jobs_created_by_users_id_fk" FOREIGN KEY ("created_by") REFERENCES "public"."users"("id") ON DELETE set null ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "bank_transactions" ADD CONSTRAINT "bank_transactions_invoice_id_invoices_id_fk" FOREIGN KEY ("invoice_id") REFERENCES "public"."invoices"("id") ON DELETE set null ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "bank_transactions" ADD CONSTRAINT "bank_transactions_created_by_users_id_fk" FOREIGN KEY ("created_by") REFERENCES "public"."users"("id") ON DELETE set null ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "calendar_events" ADD CONSTRAINT "calendar_events_user_id_users_id_fk" FOREIGN KEY ("user_id") REFERENCES "public"."users"("id") ON DELETE set null ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "calendar_events" ADD CONSTRAINT "calendar_events_client_id_clients_id_fk" FOREIGN KEY ("client_id") REFERENCES "public"."clients"("id") ON DELETE set null ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "calendar_events" ADD CONSTRAINT "calendar_events_created_by_users_id_fk" FOREIGN KEY ("created_by") REFERENCES "public"."users"("id") ON DELETE set null ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "campaigns" ADD CONSTRAINT "campaigns_created_by_users_id_fk" FOREIGN KEY ("created_by") REFERENCES "public"."users"("id") ON DELETE set null ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "client_notes" ADD CONSTRAINT "client_notes_client_id_clients_id_fk" FOREIGN KEY ("client_id") REFERENCES "public"."clients"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "client_notes" ADD CONSTRAINT "client_notes_created_by_users_id_fk" FOREIGN KEY ("created_by") REFERENCES "public"."users"("id") ON DELETE set null ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "clients" ADD CONSTRAINT "clients_account_manager_id_users_id_fk" FOREIGN KEY ("account_manager_id") REFERENCES "public"."users"("id") ON DELETE set null ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "clients" ADD CONSTRAINT "clients_created_by_users_id_fk" FOREIGN KEY ("created_by") REFERENCES "public"."users"("id") ON DELETE set null ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "contacts" ADD CONSTRAINT "contacts_client_id_clients_id_fk" FOREIGN KEY ("client_id") REFERENCES "public"."clients"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "contacts" ADD CONSTRAINT "contacts_created_by_users_id_fk" FOREIGN KEY ("created_by") REFERENCES "public"."users"("id") ON DELETE set null ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "contracts" ADD CONSTRAINT "contracts_client_id_clients_id_fk" FOREIGN KEY ("client_id") REFERENCES "public"."clients"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "contracts" ADD CONSTRAINT "contracts_created_by_users_id_fk" FOREIGN KEY ("created_by") REFERENCES "public"."users"("id") ON DELETE set null ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "domains" ADD CONSTRAINT "domains_client_id_clients_id_fk" FOREIGN KEY ("client_id") REFERENCES "public"."clients"("id") ON DELETE set null ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "domains" ADD CONSTRAINT "domains_created_by_users_id_fk" FOREIGN KEY ("created_by") REFERENCES "public"."users"("id") ON DELETE set null ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "hr_employees" ADD CONSTRAINT "hr_employees_user_id_users_id_fk" FOREIGN KEY ("user_id") REFERENCES "public"."users"("id") ON DELETE set null ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "hr_employees" ADD CONSTRAINT "hr_employees_created_by_users_id_fk" FOREIGN KEY ("created_by") REFERENCES "public"."users"("id") ON DELETE set null ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "expenses" ADD CONSTRAINT "expenses_vendor_id_vendors_id_fk" FOREIGN KEY ("vendor_id") REFERENCES "public"."vendors"("id") ON DELETE set null ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "expenses" ADD CONSTRAINT "expenses_client_id_clients_id_fk" FOREIGN KEY ("client_id") REFERENCES "public"."clients"("id") ON DELETE set null ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "expenses" ADD CONSTRAINT "expenses_created_by_users_id_fk" FOREIGN KEY ("created_by") REFERENCES "public"."users"("id") ON DELETE set null ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "inventory_items" ADD CONSTRAINT "inventory_items_created_by_users_id_fk" FOREIGN KEY ("created_by") REFERENCES "public"."users"("id") ON DELETE set null ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "invoice_items" ADD CONSTRAINT "invoice_items_invoice_id_invoices_id_fk" FOREIGN KEY ("invoice_id") REFERENCES "public"."invoices"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "invoice_items" ADD CONSTRAINT "invoice_items_created_by_users_id_fk" FOREIGN KEY ("created_by") REFERENCES "public"."users"("id") ON DELETE set null ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "invoices" ADD CONSTRAINT "invoices_client_id_clients_id_fk" FOREIGN KEY ("client_id") REFERENCES "public"."clients"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "invoices" ADD CONSTRAINT "invoices_created_by_users_id_fk" FOREIGN KEY ("created_by") REFERENCES "public"."users"("id") ON DELETE set null ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "kb_articles" ADD CONSTRAINT "kb_articles_created_by_users_id_fk" FOREIGN KEY ("created_by") REFERENCES "public"."users"("id") ON DELETE set null ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "leads" ADD CONSTRAINT "leads_assigned_to_users_id_fk" FOREIGN KEY ("assigned_to") REFERENCES "public"."users"("id") ON DELETE set null ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "leads" ADD CONSTRAINT "leads_created_by_users_id_fk" FOREIGN KEY ("created_by") REFERENCES "public"."users"("id") ON DELETE set null ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "secure_messages" ADD CONSTRAINT "secure_messages_client_id_clients_id_fk" FOREIGN KEY ("client_id") REFERENCES "public"."clients"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "secure_messages" ADD CONSTRAINT "secure_messages_contact_id_contacts_id_fk" FOREIGN KEY ("contact_id") REFERENCES "public"."contacts"("id") ON DELETE set null ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "secure_messages" ADD CONSTRAINT "secure_messages_created_by_users_id_fk" FOREIGN KEY ("created_by") REFERENCES "public"."users"("id") ON DELETE set null ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "mfa_recovery_codes" ADD CONSTRAINT "mfa_recovery_codes_user_id_users_id_fk" FOREIGN KEY ("user_id") REFERENCES "public"."users"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "mileage_trips" ADD CONSTRAINT "mileage_trips_client_id_clients_id_fk" FOREIGN KEY ("client_id") REFERENCES "public"."clients"("id") ON DELETE set null ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "mileage_trips" ADD CONSTRAINT "mileage_trips_user_id_users_id_fk" FOREIGN KEY ("user_id") REFERENCES "public"."users"("id") ON DELETE set null ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "mileage_trips" ADD CONSTRAINT "mileage_trips_created_by_users_id_fk" FOREIGN KEY ("created_by") REFERENCES "public"."users"("id") ON DELETE set null ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "client_networks" ADD CONSTRAINT "client_networks_client_id_clients_id_fk" FOREIGN KEY ("client_id") REFERENCES "public"."clients"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "client_networks" ADD CONSTRAINT "client_networks_created_by_users_id_fk" FOREIGN KEY ("created_by") REFERENCES "public"."users"("id") ON DELETE set null ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "policies" ADD CONSTRAINT "policies_client_id_clients_id_fk" FOREIGN KEY ("client_id") REFERENCES "public"."clients"("id") ON DELETE set null ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "policies" ADD CONSTRAINT "policies_created_by_users_id_fk" FOREIGN KEY ("created_by") REFERENCES "public"."users"("id") ON DELETE set null ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "projects" ADD CONSTRAINT "projects_client_id_clients_id_fk" FOREIGN KEY ("client_id") REFERENCES "public"."clients"("id") ON DELETE set null ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "projects" ADD CONSTRAINT "projects_owner_id_users_id_fk" FOREIGN KEY ("owner_id") REFERENCES "public"."users"("id") ON DELETE set null ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "projects" ADD CONSTRAINT "projects_created_by_users_id_fk" FOREIGN KEY ("created_by") REFERENCES "public"."users"("id") ON DELETE set null ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "hr_pto_requests" ADD CONSTRAINT "hr_pto_requests_user_id_users_id_fk" FOREIGN KEY ("user_id") REFERENCES "public"."users"("id") ON DELETE set null ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "hr_pto_requests" ADD CONSTRAINT "hr_pto_requests_created_by_users_id_fk" FOREIGN KEY ("created_by") REFERENCES "public"."users"("id") ON DELETE set null ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "quote_items" ADD CONSTRAINT "quote_items_quote_id_quotes_id_fk" FOREIGN KEY ("quote_id") REFERENCES "public"."quotes"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "quote_items" ADD CONSTRAINT "quote_items_created_by_users_id_fk" FOREIGN KEY ("created_by") REFERENCES "public"."users"("id") ON DELETE set null ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "quotes" ADD CONSTRAINT "quotes_client_id_clients_id_fk" FOREIGN KEY ("client_id") REFERENCES "public"."clients"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "quotes" ADD CONSTRAINT "quotes_created_by_users_id_fk" FOREIGN KEY ("created_by") REFERENCES "public"."users"("id") ON DELETE set null ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "recurring_invoices" ADD CONSTRAINT "recurring_invoices_client_id_clients_id_fk" FOREIGN KEY ("client_id") REFERENCES "public"."clients"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "recurring_invoices" ADD CONSTRAINT "recurring_invoices_created_by_users_id_fk" FOREIGN KEY ("created_by") REFERENCES "public"."users"("id") ON DELETE set null ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "recurring_items" ADD CONSTRAINT "recurring_items_recurring_id_recurring_invoices_id_fk" FOREIGN KEY ("recurring_id") REFERENCES "public"."recurring_invoices"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "recurring_items" ADD CONSTRAINT "recurring_items_created_by_users_id_fk" FOREIGN KEY ("created_by") REFERENCES "public"."users"("id") ON DELETE set null ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "renewals" ADD CONSTRAINT "renewals_client_id_clients_id_fk" FOREIGN KEY ("client_id") REFERENCES "public"."clients"("id") ON DELETE set null ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "renewals" ADD CONSTRAINT "renewals_created_by_users_id_fk" FOREIGN KEY ("created_by") REFERENCES "public"."users"("id") ON DELETE set null ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "rmm_devices" ADD CONSTRAINT "rmm_devices_client_id_clients_id_fk" FOREIGN KEY ("client_id") REFERENCES "public"."clients"("id") ON DELETE set null ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "rmm_devices" ADD CONSTRAINT "rmm_devices_created_by_users_id_fk" FOREIGN KEY ("created_by") REFERENCES "public"."users"("id") ON DELETE set null ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "sessions" ADD CONSTRAINT "sessions_user_id_users_id_fk" FOREIGN KEY ("user_id") REFERENCES "public"."users"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "settings" ADD CONSTRAINT "settings_updated_by_users_id_fk" FOREIGN KEY ("updated_by") REFERENCES "public"."users"("id") ON DELETE set null ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "ticket_messages" ADD CONSTRAINT "ticket_messages_ticket_id_tickets_id_fk" FOREIGN KEY ("ticket_id") REFERENCES "public"."tickets"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "ticket_messages" ADD CONSTRAINT "ticket_messages_author_user_id_users_id_fk" FOREIGN KEY ("author_user_id") REFERENCES "public"."users"("id") ON DELETE set null ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "ticket_time_entries" ADD CONSTRAINT "ticket_time_entries_ticket_id_tickets_id_fk" FOREIGN KEY ("ticket_id") REFERENCES "public"."tickets"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "ticket_time_entries" ADD CONSTRAINT "ticket_time_entries_user_id_users_id_fk" FOREIGN KEY ("user_id") REFERENCES "public"."users"("id") ON DELETE set null ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "ticket_time_entries" ADD CONSTRAINT "ticket_time_entries_invoice_id_invoices_id_fk" FOREIGN KEY ("invoice_id") REFERENCES "public"."invoices"("id") ON DELETE set null ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "tickets" ADD CONSTRAINT "tickets_client_id_clients_id_fk" FOREIGN KEY ("client_id") REFERENCES "public"."clients"("id") ON DELETE set null ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "tickets" ADD CONSTRAINT "tickets_contact_id_contacts_id_fk" FOREIGN KEY ("contact_id") REFERENCES "public"."contacts"("id") ON DELETE set null ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "tickets" ADD CONSTRAINT "tickets_assigned_to_users_id_fk" FOREIGN KEY ("assigned_to") REFERENCES "public"."users"("id") ON DELETE set null ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "tickets" ADD CONSTRAINT "tickets_created_by_users_id_fk" FOREIGN KEY ("created_by") REFERENCES "public"."users"("id") ON DELETE set null ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "hr_timeclock" ADD CONSTRAINT "hr_timeclock_user_id_users_id_fk" FOREIGN KEY ("user_id") REFERENCES "public"."users"("id") ON DELETE set null ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "hr_timeclock" ADD CONSTRAINT "hr_timeclock_created_by_users_id_fk" FOREIGN KEY ("created_by") REFERENCES "public"."users"("id") ON DELETE set null ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "training_assignments" ADD CONSTRAINT "training_assignments_client_id_clients_id_fk" FOREIGN KEY ("client_id") REFERENCES "public"."clients"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "training_assignments" ADD CONSTRAINT "training_assignments_created_by_users_id_fk" FOREIGN KEY ("created_by") REFERENCES "public"."users"("id") ON DELETE set null ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vendors" ADD CONSTRAINT "vendors_created_by_users_id_fk" FOREIGN KEY ("created_by") REFERENCES "public"."users"("id") ON DELETE set null ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "workflows" ADD CONSTRAINT "workflows_created_by_users_id_fk" FOREIGN KEY ("created_by") REFERENCES "public"."users"("id") ON DELETE set null ON UPDATE no action;--> statement-breakpoint
CREATE UNIQUE INDEX "assets_legacy" ON "assets" USING btree ("legacy_id");--> statement-breakpoint
CREATE INDEX "assets_client_id" ON "assets" USING btree ("client_id");--> statement-breakpoint
CREATE INDEX "audit_entity" ON "audit_log" USING btree ("entity","entity_id");--> statement-breakpoint
CREATE INDEX "audit_time" ON "audit_log" USING btree ("created_at");--> statement-breakpoint
CREATE UNIQUE INDEX "backup_jobs_legacy" ON "backup_jobs" USING btree ("legacy_id");--> statement-breakpoint
CREATE INDEX "backup_jobs_client_id" ON "backup_jobs" USING btree ("client_id");--> statement-breakpoint
CREATE UNIQUE INDEX "bank_transactions_legacy" ON "bank_transactions" USING btree ("legacy_id");--> statement-breakpoint
CREATE INDEX "bank_transactions_invoice_id" ON "bank_transactions" USING btree ("invoice_id");--> statement-breakpoint
CREATE UNIQUE INDEX "calendar_events_legacy" ON "calendar_events" USING btree ("legacy_id");--> statement-breakpoint
CREATE INDEX "calendar_events_user_id" ON "calendar_events" USING btree ("user_id");--> statement-breakpoint
CREATE INDEX "calendar_events_client_id" ON "calendar_events" USING btree ("client_id");--> statement-breakpoint
CREATE UNIQUE INDEX "campaigns_legacy" ON "campaigns" USING btree ("legacy_id");--> statement-breakpoint
CREATE UNIQUE INDEX "client_notes_legacy" ON "client_notes" USING btree ("legacy_id");--> statement-breakpoint
CREATE INDEX "client_notes_client_id" ON "client_notes" USING btree ("client_id");--> statement-breakpoint
CREATE UNIQUE INDEX "clients_legacy" ON "clients" USING btree ("legacy_id");--> statement-breakpoint
CREATE INDEX "clients_account_manager_id" ON "clients" USING btree ("account_manager_id");--> statement-breakpoint
CREATE UNIQUE INDEX "contacts_legacy" ON "contacts" USING btree ("legacy_id");--> statement-breakpoint
CREATE INDEX "contacts_client_id" ON "contacts" USING btree ("client_id");--> statement-breakpoint
CREATE UNIQUE INDEX "contracts_legacy" ON "contracts" USING btree ("legacy_id");--> statement-breakpoint
CREATE INDEX "contracts_client_id" ON "contracts" USING btree ("client_id");--> statement-breakpoint
CREATE UNIQUE INDEX "contracts_number" ON "contracts" USING btree ("number");--> statement-breakpoint
CREATE UNIQUE INDEX "domains_legacy" ON "domains" USING btree ("legacy_id");--> statement-breakpoint
CREATE INDEX "domains_client_id" ON "domains" USING btree ("client_id");--> statement-breakpoint
CREATE UNIQUE INDEX "hr_employees_legacy" ON "hr_employees" USING btree ("legacy_id");--> statement-breakpoint
CREATE INDEX "hr_employees_user_id" ON "hr_employees" USING btree ("user_id");--> statement-breakpoint
CREATE UNIQUE INDEX "expenses_legacy" ON "expenses" USING btree ("legacy_id");--> statement-breakpoint
CREATE INDEX "expenses_vendor_id" ON "expenses" USING btree ("vendor_id");--> statement-breakpoint
CREATE INDEX "expenses_client_id" ON "expenses" USING btree ("client_id");--> statement-breakpoint
CREATE UNIQUE INDEX "inventory_items_legacy" ON "inventory_items" USING btree ("legacy_id");--> statement-breakpoint
CREATE UNIQUE INDEX "invoice_items_legacy" ON "invoice_items" USING btree ("legacy_id");--> statement-breakpoint
CREATE INDEX "invoice_items_invoice_id" ON "invoice_items" USING btree ("invoice_id");--> statement-breakpoint
CREATE UNIQUE INDEX "invoices_legacy" ON "invoices" USING btree ("legacy_id");--> statement-breakpoint
CREATE INDEX "invoices_client_id" ON "invoices" USING btree ("client_id");--> statement-breakpoint
CREATE UNIQUE INDEX "invoices_number" ON "invoices" USING btree ("number");--> statement-breakpoint
CREATE UNIQUE INDEX "kb_articles_legacy" ON "kb_articles" USING btree ("legacy_id");--> statement-breakpoint
CREATE UNIQUE INDEX "leads_legacy" ON "leads" USING btree ("legacy_id");--> statement-breakpoint
CREATE INDEX "leads_assigned_to" ON "leads" USING btree ("assigned_to");--> statement-breakpoint
CREATE INDEX "login_attempts_ip_time" ON "login_attempts" USING btree ("ip","created_at");--> statement-breakpoint
CREATE INDEX "login_attempts_email_time" ON "login_attempts" USING btree ("email","created_at");--> statement-breakpoint
CREATE UNIQUE INDEX "secure_messages_legacy" ON "secure_messages" USING btree ("legacy_id");--> statement-breakpoint
CREATE INDEX "secure_messages_client_id" ON "secure_messages" USING btree ("client_id");--> statement-breakpoint
CREATE INDEX "secure_messages_contact_id" ON "secure_messages" USING btree ("contact_id");--> statement-breakpoint
CREATE INDEX "mfa_codes_user" ON "mfa_recovery_codes" USING btree ("user_id");--> statement-breakpoint
CREATE UNIQUE INDEX "mileage_trips_legacy" ON "mileage_trips" USING btree ("legacy_id");--> statement-breakpoint
CREATE INDEX "mileage_trips_client_id" ON "mileage_trips" USING btree ("client_id");--> statement-breakpoint
CREATE INDEX "mileage_trips_user_id" ON "mileage_trips" USING btree ("user_id");--> statement-breakpoint
CREATE UNIQUE INDEX "client_networks_legacy" ON "client_networks" USING btree ("legacy_id");--> statement-breakpoint
CREATE INDEX "client_networks_client_id" ON "client_networks" USING btree ("client_id");--> statement-breakpoint
CREATE UNIQUE INDEX "policies_legacy" ON "policies" USING btree ("legacy_id");--> statement-breakpoint
CREATE INDEX "policies_client_id" ON "policies" USING btree ("client_id");--> statement-breakpoint
CREATE UNIQUE INDEX "projects_legacy" ON "projects" USING btree ("legacy_id");--> statement-breakpoint
CREATE INDEX "projects_client_id" ON "projects" USING btree ("client_id");--> statement-breakpoint
CREATE INDEX "projects_owner_id" ON "projects" USING btree ("owner_id");--> statement-breakpoint
CREATE UNIQUE INDEX "projects_number" ON "projects" USING btree ("number");--> statement-breakpoint
CREATE UNIQUE INDEX "hr_pto_requests_legacy" ON "hr_pto_requests" USING btree ("legacy_id");--> statement-breakpoint
CREATE INDEX "hr_pto_requests_user_id" ON "hr_pto_requests" USING btree ("user_id");--> statement-breakpoint
CREATE UNIQUE INDEX "quote_items_legacy" ON "quote_items" USING btree ("legacy_id");--> statement-breakpoint
CREATE INDEX "quote_items_quote_id" ON "quote_items" USING btree ("quote_id");--> statement-breakpoint
CREATE UNIQUE INDEX "quotes_legacy" ON "quotes" USING btree ("legacy_id");--> statement-breakpoint
CREATE INDEX "quotes_client_id" ON "quotes" USING btree ("client_id");--> statement-breakpoint
CREATE UNIQUE INDEX "quotes_number" ON "quotes" USING btree ("number");--> statement-breakpoint
CREATE UNIQUE INDEX "recurring_invoices_legacy" ON "recurring_invoices" USING btree ("legacy_id");--> statement-breakpoint
CREATE INDEX "recurring_invoices_client_id" ON "recurring_invoices" USING btree ("client_id");--> statement-breakpoint
CREATE UNIQUE INDEX "recurring_items_legacy" ON "recurring_items" USING btree ("legacy_id");--> statement-breakpoint
CREATE INDEX "recurring_items_recurring_id" ON "recurring_items" USING btree ("recurring_id");--> statement-breakpoint
CREATE UNIQUE INDEX "renewals_legacy" ON "renewals" USING btree ("legacy_id");--> statement-breakpoint
CREATE INDEX "renewals_client_id" ON "renewals" USING btree ("client_id");--> statement-breakpoint
CREATE UNIQUE INDEX "rmm_devices_legacy" ON "rmm_devices" USING btree ("legacy_id");--> statement-breakpoint
CREATE INDEX "rmm_devices_client_id" ON "rmm_devices" USING btree ("client_id");--> statement-breakpoint
CREATE INDEX "sessions_user" ON "sessions" USING btree ("user_id");--> statement-breakpoint
CREATE INDEX "ticket_messages_ticket" ON "ticket_messages" USING btree ("ticket_id","created_at");--> statement-breakpoint
CREATE UNIQUE INDEX "ticket_messages_legacy" ON "ticket_messages" USING btree ("legacy_id");--> statement-breakpoint
CREATE INDEX "ticket_time_ticket" ON "ticket_time_entries" USING btree ("ticket_id");--> statement-breakpoint
CREATE UNIQUE INDEX "ticket_time_legacy" ON "ticket_time_entries" USING btree ("legacy_id");--> statement-breakpoint
CREATE UNIQUE INDEX "tickets_number" ON "tickets" USING btree ("number");--> statement-breakpoint
CREATE UNIQUE INDEX "tickets_legacy" ON "tickets" USING btree ("legacy_id");--> statement-breakpoint
CREATE INDEX "tickets_status" ON "tickets" USING btree ("status");--> statement-breakpoint
CREATE INDEX "tickets_client" ON "tickets" USING btree ("client_id");--> statement-breakpoint
CREATE INDEX "tickets_assigned" ON "tickets" USING btree ("assigned_to");--> statement-breakpoint
CREATE UNIQUE INDEX "hr_timeclock_legacy" ON "hr_timeclock" USING btree ("legacy_id");--> statement-breakpoint
CREATE INDEX "hr_timeclock_user_id" ON "hr_timeclock" USING btree ("user_id");--> statement-breakpoint
CREATE UNIQUE INDEX "training_assignments_legacy" ON "training_assignments" USING btree ("legacy_id");--> statement-breakpoint
CREATE INDEX "training_assignments_client_id" ON "training_assignments" USING btree ("client_id");--> statement-breakpoint
CREATE UNIQUE INDEX "users_email_lower" ON "users" USING btree (lower("email"));--> statement-breakpoint
CREATE UNIQUE INDEX "users_legacy" ON "users" USING btree ("legacy_id");--> statement-breakpoint
CREATE UNIQUE INDEX "vendors_legacy" ON "vendors" USING btree ("legacy_id");--> statement-breakpoint
CREATE UNIQUE INDEX "workflows_legacy" ON "workflows" USING btree ("legacy_id");