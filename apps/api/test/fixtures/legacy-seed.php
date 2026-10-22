<?php
// Builds a small but realistic copy of an old Weststar One database for importer tests.
// Uses the old app's own encryption functions (copied verbatim below) so the ciphertext is exactly what production holds.
define('APP_KEY', getenv('OLD_APP_KEY'));
define('ENCRYPTION_KEY', getenv('OLD_ENCRYPTION_KEY'));
function encrypt_value(string $plaintext): string {
    $iv = openssl_random_pseudo_bytes(16);
    $encrypted = openssl_encrypt($plaintext, 'aes-256-cbc', hex2bin(ENCRYPTION_KEY), 0, $iv);
    return base64_encode($iv . '::' . $encrypted);
}
function net_secret_enc(string $plain): string {
    $plain = trim($plain);
    if ($plain === '') return '';
    try { return 'nenc:' . encrypt_value($plain); } catch (\Throwable $e) { return ''; }
}
function mf_secret_key(): string {
    static $warned = false;
    $key = defined('APP_KEY') ? (string)APP_KEY : (defined('DB_PASS') ? (string)DB_PASS : 'myflow_default_key');
    if (!$warned && ($key === '' || $key === 'CHANGE_ME_RANDOM_KEY' || $key === 'myflow_default_key')) { $warned = true; error_log('Weststar One: APP_KEY is not set in config/config.php — secrets are encrypted with a weak default key (set it: openssl rand -hex 32).'); }
    return hash('sha256', $key, true);
}
function encrypt_setting(string $value): string {
    if ($value === '') return '';
    $iv = random_bytes(12); $tag = '';
    $ct = openssl_encrypt($value, 'aes-256-gcm', mf_secret_key(), OPENSSL_RAW_DATA, $iv, $tag, '', 16);
    if ($ct === false) { error_log('encrypt_setting: openssl failed'); return ''; }
    return 'v2:' . base64_encode($iv . $tag . $ct);
}
function legacy_cbc_setting(string $v): string { $key = APP_KEY; $iv = substr(hash('sha256', $key), 0, 16); return base64_encode(openssl_decrypt(openssl_encrypt($v, 'AES-256-CBC', $key, 0, $iv), 'AES-256-CBC', $key, 0, $iv) === $v ? base64_decode(openssl_encrypt($v, 'AES-256-CBC', $key, 0, $iv)) : ''); }
$db = new mysqli('localhost', 'root', '', getenv('LEGACY_DB') ?: 'legacy');
$db->set_charset('utf8mb4');
foreach (['emp_ssn_enc','emp_bank_account_enc','emp_bank_routing_enc','emp_dob_enc','emp_address_enc','emp_pay_rate_enc'] as $c) { @$db->query("ALTER TABLE hr_employees ADD COLUMN IF NOT EXISTS $c TEXT NULL"); }
$q = function (string $sql, array $p = []) use ($db) { $st = $db->prepare($sql); if ($p) { $st->bind_param(str_repeat('s', count($p)), ...$p); } if (!$st->execute()) { fwrite(STDERR, $db->error . "\n" . $sql . "\n"); exit(1); } return $db->insert_id; };
foreach (['ticket_time_entries','ticket_replies','tickets','invoice_items','invoices','quote_items','quotes','recurring_invoice_items','recurring_invoices','client_networks','contacts','assets','domains','certificates','hr_employees','hr_pto_requests','kb_articles','vendors','expenses','contracts','projects','leads','clients','users','settings'] as $t) { @$db->query("DELETE FROM $t"); }

$u1 = $q("INSERT INTO users (user_name,user_email,user_password,user_role,user_title,user_2fa_enabled,user_totp_secret,user_hr_access) VALUES (?,?,?,?,?,?,?,?)", ['Casey Hervey','casey@weststarmsp.com', password_hash('Old-Password-123!', PASSWORD_BCRYPT, ['cost'=>10]), 'admin', 'Owner', '1', encrypt_setting('JBSWY3DPEHPK3PXP'), '1']);
$u2 = $q("INSERT INTO users (user_name,user_email,user_password,user_role,user_2fa_enabled,user_totp_secret) VALUES (?,?,?,?,?,?)", ['Tech One','tech1@weststarmsp.com', password_hash('Tech-Password-456!', PASSWORD_BCRYPT), 'tech', '1', legacy_cbc_setting('KRSXG5CTMVRXEZLU')]);
$u3 = $q("INSERT INTO users (user_name,user_email,user_password,user_role,user_archived) VALUES (?,?,?,?,?)", ['Former Tech','old@weststarmsp.com', password_hash('whatever-789', PASSWORD_BCRYPT), 'tech', '1']);

$c1 = $q("INSERT INTO clients (client_name,client_status,client_billing_type,client_phone,client_email,client_city,client_state,client_sla_response_hours,client_net_terms,client_alert_note,client_account_manager) VALUES (?,?,?,?,?,?,?,?,?,?,?)", ['Franklin Title Co.','active','managed','915-555-0100','office@franklintitle.example','El Paso','TX','1','30','Call Maria before any on-site visit', (string)$u1]);
$c2 = $q("INSERT INTO clients (client_name,client_status,client_billing_type,client_city) VALUES (?,?,?,?)", ['Desert Ridge Dental','active','hourly','Phoenix']);
$c3 = $q("INSERT INTO clients (client_name,client_status,client_archived) VALUES (?,?,?)", ['Gone Away LLC','former','1']);
$k1 = $q("INSERT INTO contacts (contact_client_id,contact_name,contact_email,contact_role,contact_primary) VALUES (?,?,?,?,?)", [(string)$c1,'Maria Lopez','maria@franklintitle.example','decision_maker','1']);
$q("INSERT INTO contacts (contact_client_id,contact_name,contact_email) VALUES (?,?,?)", [(string)$c2,'Dr. Alan Reyes','alan@desertridge.example']);
$q("INSERT INTO client_networks (network_client_id,network_domain,network_subnet,network_wifi_ssid,network_wifi_password,network_isp_name,network_isp_account) VALUES (?,?,?,?,?,?,?)", [(string)$c1,'franklin.local','10.0.10.0/24','FTC-Staff', net_secret_enc('Wifi-Pass-2026!'), 'Spectrum', net_secret_enc('ACCT-778899')]);
$q("INSERT INTO client_networks (network_client_id,network_domain,network_wifi_password) VALUES (?,?,?)", [(string)$c2,'drd.local','plaintext-old-wifi']);
$q("INSERT INTO assets (asset_client_id,asset_name,asset_type,asset_serial,asset_status) VALUES (?,?,?,?,?)", [(string)$c1,'FTC-SRV01','server','SN123','active']);
$q("INSERT INTO domains (domain_client_id,domain_name,domain_registrar,domain_expire_date) VALUES (?,?,?,?)", [(string)$c1,'franklintitle.example','Cloudflare','2027-03-01']);
$q("INSERT INTO certificates (cert_client_id,cert_domain,cert_expire_date) VALUES (?,?,?)", [(string)$c1,'franklintitle.example','2027-01-15']);
$v1 = $q("INSERT INTO vendors (vendor_name,vendor_account_number) VALUES (?,?)", ['Pax8','PAX-0042']);
$q("INSERT INTO expenses (expense_vendor_id,expense_client_id,expense_date,expense_amount,expense_description) VALUES (?,?,?,?,?)", [(string)$v1,(string)$c1,'2026-10-02','612.40','M365 licenses']);

$i1 = $q("INSERT INTO invoices (invoice_number,invoice_client_id,invoice_status,invoice_date,invoice_due_date,invoice_subtotal,invoice_tax_rate,invoice_tax_amount,invoice_total,invoice_amount_paid) VALUES (?,?,?,?,?,?,?,?,?,?)", ['INV-2291',(string)$c1,'overdue','2026-09-10','2026-10-10','1240.00','0','0','1240.00','0']);
$q("INSERT INTO invoice_items (item_invoice_id,item_description,item_qty,item_rate,item_tax,item_total) VALUES (?,?,?,?,?,?)", [(string)$i1,'Managed services — September','1','1240.00','0','1240.00']);
$i2 = $q("INSERT INTO invoices (invoice_number,invoice_client_id,invoice_status,invoice_date,invoice_due_date,invoice_total,invoice_amount_paid) VALUES (?,?,?,?,?,?,?)", ['INV-2305',(string)$c2,'paid','2026-10-01','2026-10-31','375.00','375.00']);
$q("INSERT INTO invoice_items (item_invoice_id,item_description,item_qty,item_rate,item_total) VALUES (?,?,?,?,?)", [(string)$i2,'Labor','5','75','375']);
$r1 = $q("INSERT INTO recurring_invoices (recurring_client_id,recurring_frequency,recurring_next_date,recurring_scope,recurring_subtotal,recurring_status) VALUES (?,?,?,?,?,?)", [(string)$c1,'monthly','2026-11-01','Managed Gold','2150.00','active']);
$q("INSERT INTO recurring_invoice_items (ri_recurring_id,ri_description,ri_qty,ri_rate,ri_total) VALUES (?,?,?,?,?)", [(string)$r1,'Managed Gold','1','2150','2150']);
$qt = $q("INSERT INTO quotes (quote_number,quote_client_id,quote_status,quote_date,quote_total) VALUES (?,?,?,?,?)", ['QT-0418',(string)$c2,'sent','2026-10-20','1860.00']);
$q("INSERT INTO quote_items (qi_quote_id,qi_description,qi_quantity,qi_rate,qi_amount) VALUES (?,?,?,?,?)", [(string)$qt,'Firewall','1','1860','1860']);

$t1 = $q("INSERT INTO tickets (ticket_number,ticket_client_id,ticket_contact_id,ticket_contact_name,ticket_assigned_to,ticket_subject,ticket_details,ticket_priority,ticket_status,ticket_source) VALUES (?,?,?,?,?,?,?,?,?,?)", ['T-10476',(string)$c1,(string)$k1,'Maria Lopez',(string)$u1,'Firewall alert: repeated VPN login failures','Front desk cannot get on the VPN.','critical','in_progress','email']);
$q("INSERT INTO ticket_replies (reply_ticket_id,reply_user_id,reply_type,reply_from,reply_body,reply_time_spent) VALUES (?,?,?,?,?,?)", [(string)$t1,(string)$u1,'reply','staff','Looking into it now.','0.25']);
$q("INSERT INTO ticket_replies (reply_ticket_id,reply_user_id,reply_type,reply_from,reply_body) VALUES (?,?,?,?,?)", [(string)$t1,(string)$u2,'note','staff','Blocked the two IPs on the firewall.']);
$q("INSERT INTO ticket_time_entries (tte_ticket_id,tte_user_id,tte_date,tte_hours,tte_work_type,tte_billable) VALUES (?,?,?,?,?,?)", [(string)$t1,(string)$u2,'2026-10-22','1.5','Remote Support','1']);
$t2 = $q("INSERT INTO tickets (ticket_number,ticket_client_id,ticket_subject,ticket_priority,ticket_status) VALUES (?,?,?,?,?)", ['T-10482',(string)$c2,'Outlook keeps asking for password','high','waiting_on_client']);
$q("INSERT INTO tickets (ticket_number,ticket_subject,ticket_priority,ticket_status) VALUES (?,?,?,?)", ['ZOHO-555','Imported long ago from Zoho','low','closed']);

$e1 = $q("INSERT INTO hr_employees (emp_user_id,emp_first_name,emp_last_name,emp_position,emp_status,emp_hire_date,emp_ssn_enc,emp_bank_routing_enc,emp_bank_account_enc,emp_pto_balance) VALUES (?,?,?,?,?,?,?,?,?,?)", [(string)$u2,'Tech','One','Technician','active','2024-02-01', encrypt_value('123-45-6789'), encrypt_value('021000021'), encrypt_value('000123456789'), '40']);
$q("INSERT INTO hr_pto_requests (pto_emp_id,pto_type,pto_start_date,pto_end_date,pto_hours,pto_status) VALUES (?,?,?,?,?,?)", [(string)$e1,'vacation','2026-12-22','2026-12-26','24','approved']);
$q("INSERT INTO kb_articles (kb_title,kb_content,kb_portal_visible) VALUES (?,?,?)", ['Set up MFA on your phone','Step 1…','1']);
$q("INSERT INTO projects (project_number,project_name,project_client_id,project_status) VALUES (?,?,?,?)", ['PRJ-1042','Server replacement',(string)$c1,'planning']);
$q("INSERT INTO leads (lead_company,lead_stage,lead_value) VALUES (?,?,?)", ['Canyon Vista Realty','proposal','850']);
$q("INSERT INTO contracts (contract_number,contract_client_id,contract_name,contract_type,contract_status,contract_monthly_rate) VALUES (?,?,?,?,?,?)", ['CT-0007',(string)$c1,'Managed Services Agreement','managed','active','2150']);
echo "fixture ok\n";
