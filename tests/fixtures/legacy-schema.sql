/*M!999999\- enable the sandbox mode */ 

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;
DROP TABLE IF EXISTS `access_log`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `access_log` (
  `al_id` int(11) NOT NULL AUTO_INCREMENT,
  `al_user_id` int(11) DEFAULT NULL,
  `al_username` varchar(200) DEFAULT NULL,
  `al_ip` varchar(45) DEFAULT NULL,
  `al_user_agent` varchar(500) DEFAULT NULL,
  `al_action` varchar(50) DEFAULT 'login',
  `al_page` varchar(100) DEFAULT NULL,
  `al_created_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`al_id`),
  KEY `idx_al_user` (`al_user_id`),
  KEY `idx_al_created` (`al_created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `active_sessions`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `active_sessions` (
  `session_id_pk` int(11) NOT NULL AUTO_INCREMENT,
  `session_user_id` int(11) NOT NULL,
  `session_id` varchar(128) NOT NULL,
  `session_ip` varchar(45) DEFAULT NULL,
  `session_user_agent` varchar(255) DEFAULT NULL,
  `session_created_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`session_id_pk`),
  KEY `idx_session_user` (`session_user_id`),
  KEY `idx_session_id` (`session_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `announcements`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `announcements` (
  `ann_id` int(11) NOT NULL AUTO_INCREMENT,
  `ann_subject` varchar(255) DEFAULT NULL,
  `ann_body` text DEFAULT NULL,
  `ann_audience` varchar(40) DEFAULT NULL,
  `ann_sent_count` int(11) DEFAULT 0,
  `ann_sent_by` int(11) DEFAULT NULL,
  `ann_created_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`ann_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `api_keys`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `api_keys` (
  `api_id` int(11) NOT NULL AUTO_INCREMENT,
  `api_key` varchar(64) NOT NULL,
  `api_secret` varchar(128) NOT NULL,
  `api_name` varchar(200) NOT NULL,
  `api_user_id` int(11) DEFAULT NULL,
  `api_permissions` text DEFAULT NULL,
  `api_rate_limit` int(11) DEFAULT 60,
  `api_last_used` datetime DEFAULT NULL,
  `api_request_count` int(11) DEFAULT 0,
  `api_active` tinyint(1) DEFAULT 1,
  `api_expires_at` datetime DEFAULT NULL,
  `api_created_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`api_id`),
  UNIQUE KEY `api_key` (`api_key`),
  KEY `idx_api_key` (`api_key`),
  KEY `api_user_id` (`api_user_id`),
  CONSTRAINT `api_keys_ibfk_1` FOREIGN KEY (`api_user_id`) REFERENCES `users` (`user_id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `api_logs`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `api_logs` (
  `al_id` int(11) NOT NULL AUTO_INCREMENT,
  `al_api_id` int(11) DEFAULT NULL,
  `al_method` varchar(10) DEFAULT NULL,
  `al_endpoint` varchar(255) DEFAULT NULL,
  `al_status_code` int(11) DEFAULT NULL,
  `al_ip` varchar(45) DEFAULT NULL,
  `al_response_time_ms` int(11) DEFAULT NULL,
  `al_created_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`al_id`),
  KEY `idx_al_api` (`al_api_id`),
  KEY `idx_al_created` (`al_created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `assets`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `assets` (
  `asset_id` int(11) NOT NULL AUTO_INCREMENT,
  `asset_client_id` int(11) NOT NULL,
  `asset_location_id` int(11) DEFAULT NULL,
  `asset_contact_id` int(11) DEFAULT NULL,
  `asset_name` varchar(200) NOT NULL,
  `asset_type` enum('workstation','laptop','server','network','printer','mobile','other') DEFAULT 'workstation',
  `asset_make` varchar(100) DEFAULT NULL,
  `asset_model` varchar(100) DEFAULT NULL,
  `asset_serial` varchar(100) DEFAULT NULL,
  `asset_os` varchar(100) DEFAULT NULL,
  `asset_ip` varchar(45) DEFAULT NULL,
  `asset_mac` varchar(17) DEFAULT NULL,
  `asset_purchase_date` date DEFAULT NULL,
  `asset_warranty_expire` date DEFAULT NULL,
  `asset_install_date` date DEFAULT NULL,
  `asset_notes` text DEFAULT NULL,
  `asset_status` enum('active','retired','rma','storage') DEFAULT 'active',
  `asset_created_at` datetime DEFAULT current_timestamp(),
  `asset_updated_at` datetime DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  `asset_archived` tinyint(1) DEFAULT 0,
  `asset_warranty_expires` date DEFAULT NULL,
  `asset_vendor` varchar(255) DEFAULT NULL,
  PRIMARY KEY (`asset_id`),
  KEY `asset_client_id` (`asset_client_id`),
  KEY `asset_location_id` (`asset_location_id`),
  KEY `asset_contact_id` (`asset_contact_id`),
  CONSTRAINT `assets_ibfk_1` FOREIGN KEY (`asset_client_id`) REFERENCES `clients` (`client_id`) ON DELETE CASCADE,
  CONSTRAINT `assets_ibfk_2` FOREIGN KEY (`asset_location_id`) REFERENCES `locations` (`location_id`) ON DELETE SET NULL,
  CONSTRAINT `assets_ibfk_3` FOREIGN KEY (`asset_contact_id`) REFERENCES `contacts` (`contact_id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `audit_log`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `audit_log` (
  `log_id` int(11) NOT NULL AUTO_INCREMENT,
  `log_user_id` int(11) DEFAULT NULL,
  `log_action` varchar(255) NOT NULL,
  `log_entity` varchar(50) DEFAULT NULL,
  `log_entity_id` int(11) DEFAULT NULL,
  `log_ip` varchar(45) DEFAULT NULL,
  `log_created_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`log_id`),
  KEY `log_user_id` (`log_user_id`),
  CONSTRAINT `audit_log_ibfk_1` FOREIGN KEY (`log_user_id`) REFERENCES `users` (`user_id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `autopay_links`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `autopay_links` (
  `link_id` int(11) NOT NULL AUTO_INCREMENT,
  `link_token` varchar(64) NOT NULL,
  `link_client_id` int(11) NOT NULL,
  `link_created_by` int(11) DEFAULT NULL,
  `link_created_at` datetime DEFAULT current_timestamp(),
  `link_expires_at` datetime NOT NULL,
  `link_used_at` datetime DEFAULT NULL,
  PRIMARY KEY (`link_id`),
  UNIQUE KEY `uniq_autopay_link_token` (`link_token`),
  KEY `idx_autopay_link_client` (`link_client_id`),
  CONSTRAINT `autopay_links_ibfk_1` FOREIGN KEY (`link_client_id`) REFERENCES `clients` (`client_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `bank_accounts`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `bank_accounts` (
  `bank_id` int(11) NOT NULL AUTO_INCREMENT,
  `bank_fc_account_id` varchar(80) DEFAULT NULL,
  `bank_name` varchar(160) DEFAULT NULL,
  `bank_institution` varchar(160) DEFAULT NULL,
  `bank_last4` varchar(8) DEFAULT NULL,
  `bank_subtype` varchar(40) DEFAULT NULL,
  `bank_status` varchar(24) DEFAULT 'active',
  `bank_subscribed` tinyint(4) DEFAULT 0,
  `bank_created_at` datetime DEFAULT current_timestamp(),
  `bank_last_sync_at` datetime DEFAULT NULL,
  `bank_sync_cursor` varchar(80) DEFAULT NULL,
  `bank_last_error` varchar(255) DEFAULT NULL,
  PRIMARY KEY (`bank_id`),
  UNIQUE KEY `bank_fc_account_id` (`bank_fc_account_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `bank_rules`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `bank_rules` (
  `rule_id` int(11) NOT NULL AUTO_INCREMENT,
  `rule_pattern` varchar(120) NOT NULL,
  `rule_category` varchar(60) NOT NULL,
  `rule_vendor_id` int(11) DEFAULT NULL,
  `rule_created_by` int(11) DEFAULT NULL,
  `rule_created_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`rule_id`),
  KEY `idx_rule_pattern` (`rule_pattern`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `bank_transactions`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `bank_transactions` (
  `btxn_id` int(11) NOT NULL AUTO_INCREMENT,
  `btxn_fc_id` varchar(80) DEFAULT NULL,
  `btxn_bank_id` int(11) DEFAULT NULL,
  `btxn_amount` decimal(14,2) DEFAULT NULL,
  `btxn_currency` varchar(8) DEFAULT 'usd',
  `btxn_description` varchar(255) DEFAULT NULL,
  `btxn_date` date DEFAULT NULL,
  `btxn_status` varchar(24) DEFAULT NULL,
  `btxn_category` varchar(60) DEFAULT NULL,
  `btxn_matched_invoice_id` int(11) DEFAULT NULL,
  `btxn_matched_payment_id` int(11) DEFAULT NULL,
  `btxn_created_at` datetime DEFAULT current_timestamp(),
  `btxn_auto_matched` tinyint(1) DEFAULT 0,
  `btxn_match_note` varchar(255) DEFAULT NULL,
  `btxn_expense_id` int(11) DEFAULT NULL,
  PRIMARY KEY (`btxn_id`),
  UNIQUE KEY `btxn_fc_id` (`btxn_fc_id`),
  KEY `btxn_bank_id` (`btxn_bank_id`),
  KEY `btxn_date` (`btxn_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `bug_comments`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `bug_comments` (
  `bc_id` int(11) NOT NULL AUTO_INCREMENT,
  `bc_bug_id` int(11) NOT NULL,
  `bc_user_id` int(11) DEFAULT NULL,
  `bc_comment` text DEFAULT NULL,
  `bc_old_status` varchar(50) DEFAULT NULL,
  `bc_new_status` varchar(50) DEFAULT NULL,
  `bc_old_assigned` int(11) DEFAULT NULL,
  `bc_new_assigned` int(11) DEFAULT NULL,
  `bc_created_at` datetime DEFAULT current_timestamp(),
  `bc_message` text DEFAULT NULL,
  `bc_type` enum('comment','status_change','assignment') DEFAULT 'comment',
  PRIMARY KEY (`bc_id`),
  KEY `idx_bc_bug` (`bc_bug_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `bug_reports`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `bug_reports` (
  `bug_id` int(11) NOT NULL AUTO_INCREMENT,
  `bug_title` varchar(255) NOT NULL,
  `bug_description` text DEFAULT NULL,
  `bug_steps` text DEFAULT NULL,
  `bug_expected` text DEFAULT NULL,
  `bug_actual` text DEFAULT NULL,
  `bug_severity` enum('critical','major','minor','cosmetic') DEFAULT 'minor',
  `bug_status` enum('new','confirmed','in_progress','testing','fixed','closed','wontfix') DEFAULT 'new',
  `bug_assigned_to` int(11) DEFAULT NULL,
  `bug_reported_by` int(11) DEFAULT NULL,
  `bug_screenshot` varchar(500) DEFAULT NULL,
  `bug_created_at` datetime DEFAULT current_timestamp(),
  `bug_updated_at` datetime DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  `bug_number` varchar(20) DEFAULT NULL,
  `bug_category` varchar(100) DEFAULT NULL,
  `bug_page` varchar(100) DEFAULT NULL,
  `bug_browser` varchar(100) DEFAULT NULL,
  `bug_fixed_in` varchar(50) DEFAULT NULL,
  `bug_priority` int(11) DEFAULT 0,
  `bug_closed_at` datetime DEFAULT NULL,
  PRIMARY KEY (`bug_id`),
  KEY `idx_bug_status` (`bug_status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `calendar_events`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `calendar_events` (
  `event_id` int(11) NOT NULL AUTO_INCREMENT,
  `event_client_id` int(11) DEFAULT NULL,
  `event_title` varchar(255) NOT NULL,
  `event_description` text DEFAULT NULL,
  `event_start` datetime NOT NULL,
  `event_end` datetime DEFAULT NULL,
  `event_all_day` tinyint(1) DEFAULT 0,
  `event_color` varchar(7) DEFAULT '#3B82F6',
  `event_created_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`event_id`),
  KEY `event_client_id` (`event_client_id`),
  CONSTRAINT `calendar_events_ibfk_1` FOREIGN KEY (`event_client_id`) REFERENCES `clients` (`client_id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `call_log`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `call_log` (
  `cl_id` int(11) NOT NULL AUTO_INCREMENT,
  `cl_client_id` int(11) DEFAULT NULL,
  `cl_contact_name` varchar(200) DEFAULT NULL,
  `cl_phone` varchar(50) DEFAULT NULL,
  `cl_direction` enum('inbound','outbound','missed') DEFAULT 'inbound',
  `cl_duration` int(11) DEFAULT 0,
  `cl_notes` text DEFAULT NULL,
  `cl_call_time` datetime DEFAULT NULL,
  `cl_user_id` int(11) DEFAULT NULL,
  `cl_created_at` datetime DEFAULT current_timestamp(),
  `cl_contact_id` int(11) DEFAULT NULL,
  `cl_caller` varchar(100) DEFAULT NULL,
  `cl_callee` varchar(100) DEFAULT NULL,
  `cl_status` varchar(50) DEFAULT NULL,
  `cl_talk_duration` int(11) DEFAULT 0,
  `cl_trunk` varchar(100) DEFAULT NULL,
  `cl_recording` varchar(500) DEFAULT NULL,
  `cl_external_id` varchar(100) DEFAULT NULL,
  `cl_note_created` tinyint(1) DEFAULT 0,
  PRIMARY KEY (`cl_id`),
  KEY `idx_cl_client` (`cl_client_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `call_queue`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `call_queue` (
  `cq_id` int(11) NOT NULL AUTO_INCREMENT,
  `cq_lead_id` int(11) DEFAULT NULL,
  `cq_client_id` int(11) DEFAULT NULL,
  `cq_contact_name` varchar(200) DEFAULT NULL,
  `cq_phone` varchar(50) DEFAULT NULL,
  `cq_company` varchar(200) DEFAULT NULL,
  `cq_reason` varchar(255) DEFAULT NULL,
  `cq_priority` enum('high','normal','low') DEFAULT 'normal',
  `cq_assigned_to` int(11) DEFAULT NULL,
  `cq_status` enum('pending','in_progress','completed','skipped','no_answer','voicemail','callback') DEFAULT 'pending',
  `cq_call_outcome` text DEFAULT NULL,
  `cq_follow_up_date` date DEFAULT NULL,
  `cq_attempts` int(11) DEFAULT 0,
  `cq_last_attempt` datetime DEFAULT NULL,
  `cq_completed_at` datetime DEFAULT NULL,
  `cq_created_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`cq_id`),
  KEY `idx_cq_assigned` (`cq_assigned_to`),
  KEY `idx_cq_status` (`cq_status`),
  KEY `idx_cq_lead` (`cq_lead_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `call_scripts`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `call_scripts` (
  `script_id` int(11) NOT NULL AUTO_INCREMENT,
  `script_name` varchar(200) NOT NULL,
  `script_type` enum('cold_call','follow_up','qualification','appointment','general') DEFAULT 'cold_call',
  `script_intro` text DEFAULT NULL,
  `script_body` text DEFAULT NULL,
  `script_objections` text DEFAULT NULL,
  `script_closing` text DEFAULT NULL,
  `script_active` tinyint(1) DEFAULT 1,
  `script_created_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`script_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `campaign_recipients`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `campaign_recipients` (
  `cr_id` int(11) NOT NULL AUTO_INCREMENT,
  `cr_campaign_id` int(11) NOT NULL,
  `cr_email` varchar(200) NOT NULL,
  `cr_client_id` int(11) DEFAULT NULL,
  `cr_opened` tinyint(1) DEFAULT 0,
  `cr_opened_at` datetime DEFAULT NULL,
  `cr_sent_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`cr_id`),
  KEY `cr_campaign_id` (`cr_campaign_id`),
  CONSTRAINT `campaign_recipients_ibfk_1` FOREIGN KEY (`cr_campaign_id`) REFERENCES `email_campaigns` (`campaign_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `canned_responses`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `canned_responses` (
  `canned_id` int(11) NOT NULL AUTO_INCREMENT,
  `canned_title` varchar(200) NOT NULL,
  `canned_content` text NOT NULL,
  `canned_category` varchar(100) DEFAULT 'General',
  `canned_work_type` varchar(50) DEFAULT '',
  `canned_hours` decimal(6,2) DEFAULT 0.00,
  `canned_created_by` int(11) DEFAULT NULL,
  `canned_created_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`canned_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `certificates`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `certificates` (
  `cert_id` int(11) NOT NULL AUTO_INCREMENT,
  `cert_client_id` int(11) NOT NULL,
  `cert_domain` varchar(255) NOT NULL,
  `cert_issuer` varchar(200) DEFAULT NULL,
  `cert_expire_date` date DEFAULT NULL,
  `cert_notes` text DEFAULT NULL,
  `cert_created_at` datetime DEFAULT current_timestamp(),
  `cert_last_checked` datetime DEFAULT NULL,
  `cert_live_expiry` date DEFAULT NULL,
  `cert_live_issuer` varchar(255) DEFAULT NULL,
  `cert_live_valid` tinyint(1) DEFAULT 1,
  PRIMARY KEY (`cert_id`),
  KEY `cert_client_id` (`cert_client_id`),
  CONSTRAINT `certificates_ibfk_1` FOREIGN KEY (`cert_client_id`) REFERENCES `clients` (`client_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `checklist_templates`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `checklist_templates` (
  `template_id` int(11) NOT NULL AUTO_INCREMENT,
  `template_name` varchar(200) NOT NULL,
  `template_items` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL CHECK (json_valid(`template_items`)),
  `template_created_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`template_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `client_activities`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `client_activities` (
  `ca_id` int(11) NOT NULL AUTO_INCREMENT,
  `ca_client_id` int(11) NOT NULL,
  `ca_user_id` int(11) DEFAULT NULL,
  `ca_type` enum('call','email','meeting','note','task','qbr','onsite','check_in','escalation','contract_change') DEFAULT 'note',
  `ca_subject` varchar(255) DEFAULT NULL,
  `ca_description` text DEFAULT NULL,
  `ca_outcome` varchar(255) DEFAULT NULL,
  `ca_follow_up_date` date DEFAULT NULL,
  `ca_duration_mins` int(11) DEFAULT 0,
  `ca_created_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`ca_id`),
  KEY `idx_ca_client` (`ca_client_id`),
  KEY `idx_ca_type` (`ca_type`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `client_checklists`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `client_checklists` (
  `checklist_id` int(11) NOT NULL AUTO_INCREMENT,
  `checklist_client_id` int(11) NOT NULL,
  `checklist_name` varchar(200) NOT NULL,
  `checklist_items` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL CHECK (json_valid(`checklist_items`)),
  `checklist_completed` tinyint(1) DEFAULT 0,
  `checklist_created_by` int(11) DEFAULT NULL,
  `checklist_created_at` datetime DEFAULT current_timestamp(),
  `checklist_completed_at` datetime DEFAULT NULL,
  PRIMARY KEY (`checklist_id`),
  KEY `checklist_client_id` (`checklist_client_id`),
  CONSTRAINT `client_checklists_ibfk_1` FOREIGN KEY (`checklist_client_id`) REFERENCES `clients` (`client_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `client_crypto_keys`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `client_crypto_keys` (
  `client_id` int(11) NOT NULL,
  `wrapped_key` text DEFAULT NULL,
  `created_at` datetime DEFAULT current_timestamp(),
  `shredded_at` datetime DEFAULT NULL,
  `shredded_by` int(11) DEFAULT NULL,
  PRIMARY KEY (`client_id`),
  CONSTRAINT `client_crypto_keys_ibfk_1` FOREIGN KEY (`client_id`) REFERENCES `clients` (`client_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `client_files`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `client_files` (
  `file_id` int(11) NOT NULL AUTO_INCREMENT,
  `file_client_id` int(11) NOT NULL,
  `file_filename` varchar(255) NOT NULL,
  `file_original_name` varchar(255) NOT NULL,
  `file_mime_type` varchar(100) DEFAULT NULL,
  `file_size` int(11) DEFAULT 0,
  `file_notes` varchar(500) DEFAULT NULL,
  `file_uploaded_by` int(11) DEFAULT NULL,
  `file_created_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`file_id`),
  KEY `file_client_id` (`file_client_id`),
  CONSTRAINT `client_files_ibfk_1` FOREIGN KEY (`file_client_id`) REFERENCES `clients` (`client_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `client_networks`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `client_networks` (
  `network_id` int(11) NOT NULL AUTO_INCREMENT,
  `network_client_id` int(11) NOT NULL,
  `network_lan_range` varchar(100) DEFAULT NULL,
  `network_subnet` varchar(50) DEFAULT NULL,
  `network_gateway` varchar(50) DEFAULT NULL,
  `network_dns_primary` varchar(50) DEFAULT NULL,
  `network_dns_secondary` varchar(50) DEFAULT NULL,
  `network_dhcp_scope` varchar(100) DEFAULT NULL,
  `network_domain` varchar(100) DEFAULT NULL,
  `network_wifi_ssid` varchar(100) DEFAULT NULL,
  `network_wifi_password` varchar(200) DEFAULT NULL,
  `network_isp_name` varchar(100) DEFAULT NULL,
  `network_isp_account` varchar(100) DEFAULT NULL,
  `network_isp_speed` varchar(50) DEFAULT NULL,
  `network_isp_ip` varchar(50) DEFAULT NULL,
  `network_firewall_model` varchar(100) DEFAULT NULL,
  `network_firewall_ip` varchar(50) DEFAULT NULL,
  `network_switch_model` varchar(100) DEFAULT NULL,
  `network_switch_ip` varchar(50) DEFAULT NULL,
  `network_notes` text DEFAULT NULL,
  `network_updated_at` datetime DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  PRIMARY KEY (`network_id`),
  KEY `network_client_id` (`network_client_id`),
  CONSTRAINT `client_networks_ibfk_1` FOREIGN KEY (`network_client_id`) REFERENCES `clients` (`client_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `client_notes`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `client_notes` (
  `note_id` int(11) NOT NULL AUTO_INCREMENT,
  `note_client_id` int(11) NOT NULL,
  `note_user_id` int(11) DEFAULT NULL,
  `note_type` enum('note','call','email','meeting','task','alert','billing') DEFAULT 'note',
  `note_content` text NOT NULL,
  `note_pinned` tinyint(1) DEFAULT 0,
  `note_created_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`note_id`),
  KEY `note_client_id` (`note_client_id`),
  KEY `note_user_id` (`note_user_id`),
  CONSTRAINT `client_notes_ibfk_1` FOREIGN KEY (`note_client_id`) REFERENCES `clients` (`client_id`) ON DELETE CASCADE,
  CONSTRAINT `client_notes_ibfk_2` FOREIGN KEY (`note_user_id`) REFERENCES `users` (`user_id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `client_policies`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `client_policies` (
  `cp_id` int(11) NOT NULL AUTO_INCREMENT,
  `cp_client_id` int(11) NOT NULL,
  `cp_name` varchar(200) NOT NULL,
  `cp_status` enum('draft','sent','active','review_due','archived') NOT NULL DEFAULT 'draft',
  `cp_version` int(11) NOT NULL DEFAULT 1,
  `cp_effective_date` date DEFAULT NULL,
  `cp_review_date` date DEFAULT NULL,
  `cp_signer_name` varchar(150) DEFAULT NULL,
  `cp_signer_email` varchar(255) DEFAULT NULL,
  `cp_signer_title` varchar(150) DEFAULT NULL,
  `cp_signed_at` datetime DEFAULT NULL,
  `cp_sign_token` varchar(64) DEFAULT NULL,
  `cp_signature_data` mediumtext DEFAULT NULL,
  `cp_signer_ip` varchar(64) DEFAULT NULL,
  `cp_ack_token` varchar(64) DEFAULT NULL,
  `cp_inputs` text DEFAULT NULL,
  `cp_created_by` int(11) DEFAULT NULL,
  `cp_created_at` datetime DEFAULT current_timestamp(),
  `cp_updated_at` datetime DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  PRIMARY KEY (`cp_id`),
  KEY `idx_cp_client` (`cp_client_id`),
  KEY `idx_cp_status` (`cp_status`),
  KEY `idx_cp_sign_token` (`cp_sign_token`),
  KEY `idx_cp_ack_token` (`cp_ack_token`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `client_policy_sections`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `client_policy_sections` (
  `cps_id` int(11) NOT NULL AUTO_INCREMENT,
  `cps_policy_id` int(11) NOT NULL,
  `cps_template_key` varchar(50) DEFAULT NULL,
  `cps_policy_title` varchar(150) DEFAULT NULL,
  `cps_title` varchar(200) NOT NULL,
  `cps_body` mediumtext DEFAULT NULL,
  `cps_sort` int(11) NOT NULL DEFAULT 0,
  `cps_decision` text DEFAULT NULL,
  PRIMARY KEY (`cps_id`),
  KEY `idx_cps_policy` (`cps_policy_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `client_tags`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `client_tags` (
  `tag_id` int(11) NOT NULL AUTO_INCREMENT,
  `tag_client_id` int(11) NOT NULL,
  `tag_name` varchar(50) NOT NULL,
  `tag_color` varchar(7) DEFAULT '#6366f1',
  PRIMARY KEY (`tag_id`),
  KEY `tag_client_id` (`tag_client_id`),
  CONSTRAINT `client_tags_ibfk_1` FOREIGN KEY (`tag_client_id`) REFERENCES `clients` (`client_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `clients`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `clients` (
  `client_id` int(11) NOT NULL AUTO_INCREMENT,
  `client_name` varchar(200) NOT NULL,
  `client_type` enum('business','residential','nonprofit','government','internal') DEFAULT 'business',
  `client_status` enum('lead','active','inactive','former') DEFAULT 'active',
  `client_industry` varchar(100) DEFAULT NULL,
  `client_employee_count` int(11) DEFAULT 0,
  `client_workstation_count` int(11) DEFAULT 0,
  `client_server_count` int(11) DEFAULT 0,
  `client_referred_by` varchar(200) DEFAULT NULL,
  `client_sla_response_hours` int(11) DEFAULT 4,
  `client_sla_resolution_hours` int(11) DEFAULT 24,
  `client_last_contact` date DEFAULT NULL,
  `client_website` varchar(255) DEFAULT NULL,
  `client_phone` varchar(50) DEFAULT NULL,
  `client_phone2` varchar(50) DEFAULT NULL,
  `client_fax` varchar(50) DEFAULT NULL,
  `client_email` varchar(200) DEFAULT NULL,
  `client_address` varchar(255) DEFAULT NULL,
  `client_city` varchar(100) DEFAULT NULL,
  `client_state` varchar(50) DEFAULT NULL,
  `client_zip` varchar(20) DEFAULT NULL,
  `client_country` varchar(100) DEFAULT 'US',
  `client_billing_address` varchar(255) DEFAULT NULL,
  `client_billing_city` varchar(100) DEFAULT NULL,
  `client_billing_state` varchar(50) DEFAULT NULL,
  `client_billing_zip` varchar(20) DEFAULT NULL,
  `client_notes` text DEFAULT NULL,
  `client_rate` decimal(10,2) DEFAULT 0.00,
  `client_billing_type` varchar(30) DEFAULT 'hourly',
  `client_ar_contact_id` int(11) DEFAULT NULL,
  `client_ar_cc` varchar(255) DEFAULT NULL,
  `client_tax_rate` decimal(5,2) DEFAULT 0.00,
  `client_net_terms` int(11) DEFAULT 30,
  `client_tax_id` varchar(50) DEFAULT NULL,
  `client_account_number` varchar(100) DEFAULT NULL,
  `client_contract_type` varchar(50) DEFAULT NULL,
  `client_onboarding_date` date DEFAULT NULL,
  `client_domain` varchar(255) DEFAULT NULL,
  `client_join_code` varchar(20) DEFAULT NULL,
  `client_health_score` int(11) DEFAULT 100,
  `client_health_updated` datetime DEFAULT NULL,
  `client_mrr` decimal(10,2) DEFAULT 0.00,
  `client_contract_value` decimal(10,2) DEFAULT 0.00,
  `client_onboarded_at` date DEFAULT NULL,
  `client_next_qbr` date DEFAULT NULL,
  `client_risk_level` enum('low','medium','high','critical') DEFAULT 'low',
  `client_satisfaction` int(11) DEFAULT 0,
  `client_lifetime_value` decimal(12,2) DEFAULT 0.00,
  `client_referral_source` varchar(200) DEFAULT NULL,
  `client_account_manager` int(11) DEFAULT NULL,
  `client_tags` varchar(500) DEFAULT NULL,
  `client_created_at` datetime DEFAULT current_timestamp(),
  `client_updated_at` datetime DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  `client_archived` tinyint(1) DEFAULT 0,
  `client_review_requested_at` datetime DEFAULT NULL,
  `client_review_count` int(11) DEFAULT 0,
  `client_health_updated_at` datetime DEFAULT NULL,
  `client_tc_id` int(11) DEFAULT NULL,
  `client_is_internal` tinyint(1) NOT NULL DEFAULT 0,
  `client_late_fee_exempt` tinyint(1) DEFAULT 0,
  `client_credit_hold` tinyint(1) DEFAULT 0,
  `client_alert_note` varchar(255) DEFAULT NULL,
  `client_account_alert` varchar(20) DEFAULT 'none',
  `client_last_backup_success` date DEFAULT NULL,
  `client_last_backup_test` date DEFAULT NULL,
  `client_stripe_customer_id` varchar(100) DEFAULT NULL,
  `client_autopay_payment_method` varchar(100) DEFAULT NULL,
  `client_autopay_enabled` tinyint(1) DEFAULT 0,
  `client_autopay_card_brand` varchar(20) DEFAULT NULL,
  `client_autopay_card_last4` varchar(4) DEFAULT NULL,
  `client_autopay_enrolled_at` datetime DEFAULT NULL,
  `client_autopay_last_attempt_at` datetime DEFAULT NULL,
  `client_autopay_last_status` varchar(20) DEFAULT NULL,
  `client_autopay_last_error` varchar(255) DEFAULT NULL,
  `client_sla_custom` tinyint(1) DEFAULT 0,
  PRIMARY KEY (`client_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `company_profile`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `company_profile` (
  `company_id` int(11) NOT NULL AUTO_INCREMENT,
  `company_name` varchar(200) NOT NULL DEFAULT 'My IT Company',
  `company_legal_name` varchar(255) DEFAULT NULL,
  `company_logo` varchar(255) DEFAULT NULL,
  `company_phone` varchar(50) DEFAULT NULL,
  `company_phone2` varchar(50) DEFAULT NULL,
  `company_fax` varchar(50) DEFAULT NULL,
  `company_email` varchar(200) DEFAULT NULL,
  `company_website` varchar(255) DEFAULT NULL,
  `company_address` varchar(255) DEFAULT NULL,
  `company_city` varchar(100) DEFAULT NULL,
  `company_state` varchar(50) DEFAULT NULL,
  `company_zip` varchar(20) DEFAULT NULL,
  `company_country` varchar(100) DEFAULT 'US',
  `company_tax_id` varchar(50) DEFAULT NULL,
  `company_invoice_footer` text DEFAULT NULL,
  `company_portal_welcome` text DEFAULT NULL,
  `company_google_review_url` varchar(500) DEFAULT NULL,
  `company_updated_at` datetime DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  `company_portal_url` varchar(500) DEFAULT NULL,
  PRIMARY KEY (`company_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `competitors`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `competitors` (
  `comp_id` int(11) NOT NULL AUTO_INCREMENT,
  `comp_name` varchar(200) NOT NULL,
  `comp_website` varchar(255) DEFAULT NULL,
  `comp_strengths` text DEFAULT NULL,
  `comp_weaknesses` text DEFAULT NULL,
  `comp_pricing` text DEFAULT NULL,
  `comp_notes` text DEFAULT NULL,
  `comp_created_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`comp_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `contacts`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `contacts` (
  `contact_id` int(11) NOT NULL AUTO_INCREMENT,
  `contact_client_id` int(11) NOT NULL,
  `contact_name` varchar(200) NOT NULL,
  `contact_title` varchar(100) DEFAULT NULL,
  `contact_email` varchar(200) DEFAULT NULL,
  `contact_phone` varchar(50) DEFAULT NULL,
  `contact_mobile` varchar(50) DEFAULT NULL,
  `contact_department` varchar(100) DEFAULT NULL,
  `contact_extension` varchar(20) DEFAULT NULL,
  `contact_location` varchar(200) DEFAULT NULL,
  `contact_timezone` varchar(50) DEFAULT NULL,
  `contact_birthday` date DEFAULT NULL,
  `contact_preferred_contact` enum('email','phone','text','teams') DEFAULT 'email',
  `contact_role` enum('decision_maker','technical','billing','end_user','other') DEFAULT 'other',
  `contact_last_contacted` date DEFAULT NULL,
  `contact_linkedin` varchar(255) DEFAULT NULL,
  `contact_primary` tinyint(1) DEFAULT 0,
  `contact_notes` text DEFAULT NULL,
  `contact_created_at` datetime DEFAULT current_timestamp(),
  `contact_archived` tinyint(1) DEFAULT 0,
  PRIMARY KEY (`contact_id`),
  KEY `contact_client_id` (`contact_client_id`),
  CONSTRAINT `contacts_ibfk_1` FOREIGN KEY (`contact_client_id`) REFERENCES `clients` (`client_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `contract_signatures`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `contract_signatures` (
  `sig_id` int(11) NOT NULL AUTO_INCREMENT,
  `sig_contract_id` int(11) NOT NULL,
  `sig_signer_name` varchar(200) NOT NULL,
  `sig_signer_email` varchar(200) DEFAULT NULL,
  `sig_signer_title` varchar(100) DEFAULT NULL,
  `sig_signer_ip` varchar(45) DEFAULT NULL,
  `sig_signature_data` mediumtext DEFAULT NULL,
  `sig_signed_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`sig_id`),
  KEY `sig_contract_id` (`sig_contract_id`),
  CONSTRAINT `contract_signatures_ibfk_1` FOREIGN KEY (`sig_contract_id`) REFERENCES `contracts` (`contract_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `contracts`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `contracts` (
  `contract_id` int(11) NOT NULL AUTO_INCREMENT,
  `contract_number` varchar(50) DEFAULT NULL,
  `contract_client_id` int(11) NOT NULL,
  `contract_name` varchar(255) NOT NULL,
  `contract_title` varchar(255) DEFAULT NULL,
  `contract_type` varchar(50) DEFAULT 'managed',
  `contract_status` enum('draft','sent','active','expired','cancelled','voided') DEFAULT 'draft',
  `contract_start_date` date DEFAULT NULL,
  `contract_end_date` date DEFAULT NULL,
  `contract_auto_renew` tinyint(1) DEFAULT 1,
  `contract_value` decimal(12,2) DEFAULT 0.00,
  `contract_monthly_rate` decimal(10,2) DEFAULT 0.00,
  `contract_auto_invoice` tinyint(1) DEFAULT 0,
  `contract_last_invoiced` date DEFAULT NULL,
  `contract_setup_fee` decimal(10,2) DEFAULT 0.00,
  `contract_included_hours` decimal(6,2) DEFAULT 0.00,
  `contract_overage_rate` decimal(10,2) DEFAULT 0.00,
  `contract_remote_rate` decimal(10,2) DEFAULT 0.00,
  `contract_onsite_rate` decimal(10,2) DEFAULT 0.00,
  `contract_emergency_rate` decimal(10,2) DEFAULT 0.00,
  `contract_vendor_rate` decimal(10,2) DEFAULT 0.00,
  `contract_travel_rate` decimal(10,2) DEFAULT 0.00,
  `contract_billing_cycle` enum('monthly','quarterly','annual','one_time','per_incident') DEFAULT 'monthly',
  `contract_payment_method` varchar(50) DEFAULT 'invoice',
  `contract_scope` mediumtext DEFAULT NULL,
  `contract_sla` mediumtext DEFAULT NULL,
  `contract_terms` mediumtext DEFAULT NULL,
  `contract_notes` text DEFAULT NULL,
  `contract_nda` text DEFAULT NULL,
  `contract_company_brand` varchar(200) DEFAULT NULL,
  `contract_void_reason` text DEFAULT NULL,
  `contract_voided_at` datetime DEFAULT NULL,
  `contract_voided_by` int(11) DEFAULT NULL,
  `contract_sign_token` varchar(64) DEFAULT NULL,
  `contract_sent_at` datetime DEFAULT NULL,
  `contract_signed_at` datetime DEFAULT NULL,
  `contract_created_by` int(11) DEFAULT NULL,
  `contract_created_at` datetime DEFAULT current_timestamp(),
  `contract_updated_at` datetime DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  `contract_recurring_amount` decimal(10,2) DEFAULT NULL,
  `contract_project_total` decimal(12,2) DEFAULT 0.00,
  `contract_equipment_fee` decimal(10,2) DEFAULT 0.00,
  `contract_term_months` int(11) DEFAULT NULL,
  `contract_next_invoice_date` date DEFAULT NULL,
  `contract_bill_day` tinyint(4) DEFAULT NULL,
  `contract_signed_hash` char(64) DEFAULT NULL,
  `contract_renewed_count` int(11) DEFAULT 0,
  `contract_amends_id` int(11) DEFAULT NULL,
  `contract_reminder_60_sent` tinyint(1) DEFAULT 0,
  `contract_reminder_30_sent` tinyint(1) DEFAULT 0,
  PRIMARY KEY (`contract_id`),
  UNIQUE KEY `contract_sign_token` (`contract_sign_token`),
  KEY `idx_contract_status` (`contract_status`),
  KEY `idx_contract_client` (`contract_client_id`,`contract_status`),
  KEY `contract_created_by` (`contract_created_by`),
  CONSTRAINT `contracts_ibfk_1` FOREIGN KEY (`contract_client_id`) REFERENCES `clients` (`client_id`) ON DELETE CASCADE,
  CONSTRAINT `contracts_ibfk_2` FOREIGN KEY (`contract_created_by`) REFERENCES `users` (`user_id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `crypto_shred_log`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `crypto_shred_log` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `client_id` int(11) NOT NULL,
  `client_name` varchar(255) DEFAULT NULL,
  `performed_by` int(11) DEFAULT NULL,
  `detail` text DEFAULT NULL,
  `created_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `db_error_log`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `db_error_log` (
  `dbe_id` int(11) NOT NULL AUTO_INCREMENT,
  `dbe_kind` varchar(30) NOT NULL,
  `dbe_error` text NOT NULL,
  `dbe_sql` varchar(500) DEFAULT NULL,
  `dbe_page` varchar(255) DEFAULT NULL,
  `dbe_user_id` int(11) DEFAULT NULL,
  `dbe_created_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`dbe_id`),
  KEY `idx_dbe_created` (`dbe_created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `deploy_log`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `deploy_log` (
  `dl_id` int(11) NOT NULL AUTO_INCREMENT,
  `dl_version` varchar(50) DEFAULT NULL,
  `dl_commit` varchar(50) DEFAULT NULL,
  `dl_branch` varchar(100) DEFAULT NULL,
  `dl_message` text DEFAULT NULL,
  `dl_migrations_run` int(11) DEFAULT 0,
  `dl_status` varchar(50) DEFAULT 'success',
  `dl_created_at` datetime DEFAULT current_timestamp(),
  `dl_deployed_by` int(11) DEFAULT NULL,
  PRIMARY KEY (`dl_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `dev_notes`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `dev_notes` (
  `dn_id` int(11) NOT NULL AUTO_INCREMENT,
  `dn_type` enum('todo','idea','note','decision','changelog') DEFAULT 'note',
  `dn_title` varchar(255) DEFAULT NULL,
  `dn_content` text DEFAULT NULL,
  `dn_priority` enum('low','medium','high') DEFAULT 'medium',
  `dn_status` enum('open','in_progress','done') DEFAULT 'open',
  `dn_user_id` int(11) DEFAULT NULL,
  `dn_created_at` datetime DEFAULT current_timestamp(),
  `dn_updated_at` datetime DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  `dn_body` text DEFAULT NULL,
  `dn_category` enum('todo','idea','note','decision','changelog') DEFAULT 'note',
  PRIMARY KEY (`dn_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `documents`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `documents` (
  `doc_id` int(11) NOT NULL AUTO_INCREMENT,
  `doc_client_id` int(11) NOT NULL,
  `doc_title` varchar(255) NOT NULL,
  `doc_content` longtext DEFAULT NULL,
  `doc_folder` varchar(200) DEFAULT NULL,
  `doc_created_by` int(11) DEFAULT NULL,
  `doc_created_at` datetime DEFAULT current_timestamp(),
  `doc_updated_at` datetime DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  `doc_archived` tinyint(1) DEFAULT 0,
  PRIMARY KEY (`doc_id`),
  KEY `doc_client_id` (`doc_client_id`),
  KEY `doc_created_by` (`doc_created_by`),
  CONSTRAINT `documents_ibfk_1` FOREIGN KEY (`doc_client_id`) REFERENCES `clients` (`client_id`) ON DELETE CASCADE,
  CONSTRAINT `documents_ibfk_2` FOREIGN KEY (`doc_created_by`) REFERENCES `users` (`user_id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `domains`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `domains` (
  `domain_id` int(11) NOT NULL AUTO_INCREMENT,
  `domain_client_id` int(11) NOT NULL,
  `domain_name` varchar(255) NOT NULL,
  `domain_registrar` varchar(200) DEFAULT NULL,
  `domain_expire_date` date DEFAULT NULL,
  `domain_dns_provider` varchar(200) DEFAULT NULL,
  `domain_nameservers` text DEFAULT NULL,
  `domain_last_checked` datetime DEFAULT NULL,
  `domain_notes` text DEFAULT NULL,
  `domain_created_at` datetime DEFAULT current_timestamp(),
  `domain_whois_expiry` date DEFAULT NULL,
  `domain_status` varchar(100) DEFAULT NULL,
  PRIMARY KEY (`domain_id`),
  KEY `domain_client_id` (`domain_client_id`),
  CONSTRAINT `domains_ibfk_1` FOREIGN KEY (`domain_client_id`) REFERENCES `clients` (`client_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `email_campaigns`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `email_campaigns` (
  `campaign_id` int(11) NOT NULL AUTO_INCREMENT,
  `campaign_name` varchar(255) NOT NULL,
  `campaign_subject` varchar(255) NOT NULL,
  `campaign_body` text NOT NULL,
  `campaign_status` enum('draft','sent') DEFAULT 'draft',
  `campaign_recipients` int(11) DEFAULT 0,
  `campaign_opens` int(11) DEFAULT 0,
  `campaign_sent_at` datetime DEFAULT NULL,
  `campaign_created_by` int(11) DEFAULT NULL,
  `campaign_created_at` datetime DEFAULT current_timestamp(),
  `campaign_scheduled_at` datetime DEFAULT NULL,
  PRIMARY KEY (`campaign_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `email_log`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `email_log` (
  `elog_id` int(11) NOT NULL AUTO_INCREMENT,
  `elog_direction` enum('out','in') NOT NULL DEFAULT 'out',
  `elog_to` varchar(500) DEFAULT NULL,
  `elog_from` varchar(500) DEFAULT NULL,
  `elog_subject` varchar(500) DEFAULT NULL,
  `elog_status` varchar(20) DEFAULT 'sent',
  `elog_error` varchar(500) DEFAULT NULL,
  `elog_ticket_id` int(11) DEFAULT NULL,
  `elog_client_id` int(11) DEFAULT NULL,
  `elog_preview` varchar(1000) DEFAULT NULL,
  `elog_created_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`elog_id`),
  KEY `idx_elog_dir` (`elog_direction`),
  KEY `idx_elog_created` (`elog_created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `email_outbox`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `email_outbox` (
  `eo_id` int(11) NOT NULL AUTO_INCREMENT,
  `eo_to` varchar(255) NOT NULL,
  `eo_subject` varchar(500) DEFAULT NULL,
  `eo_body_text` mediumtext DEFAULT NULL,
  `eo_body_html` mediumtext DEFAULT NULL,
  `eo_reply_to` varchar(255) DEFAULT NULL,
  `eo_cc` text DEFAULT NULL,
  `eo_status` varchar(20) DEFAULT 'pending',
  `eo_attempts` int(11) DEFAULT 0,
  `eo_error` varchar(500) DEFAULT NULL,
  `eo_created_at` datetime DEFAULT current_timestamp(),
  `eo_sent_at` datetime DEFAULT NULL,
  `eo_attachments` longtext DEFAULT NULL,
  PRIMARY KEY (`eo_id`),
  KEY `idx_eo_status` (`eo_status`,`eo_attempts`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `email_templates`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `email_templates` (
  `template_id` int(11) NOT NULL AUTO_INCREMENT,
  `template_name` varchar(200) NOT NULL,
  `template_category` varchar(50) DEFAULT 'marketing',
  `template_subject` varchar(255) NOT NULL,
  `template_body` text NOT NULL,
  `template_created_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`template_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `expense_categories`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `expense_categories` (
  `category_id` int(11) NOT NULL AUTO_INCREMENT,
  `category_name` varchar(100) NOT NULL,
  PRIMARY KEY (`category_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `expenses`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `expenses` (
  `expense_id` int(11) NOT NULL AUTO_INCREMENT,
  `expense_category_id` int(11) DEFAULT NULL,
  `expense_vendor_id` int(11) DEFAULT NULL,
  `expense_client_id` int(11) DEFAULT NULL,
  `expense_date` date NOT NULL,
  `expense_amount` decimal(10,2) NOT NULL,
  `expense_description` varchar(255) DEFAULT NULL,
  `expense_receipt` varchar(255) DEFAULT NULL,
  `expense_created_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`expense_id`),
  KEY `expense_category_id` (`expense_category_id`),
  KEY `expense_vendor_id` (`expense_vendor_id`),
  KEY `expense_client_id` (`expense_client_id`),
  CONSTRAINT `expenses_ibfk_1` FOREIGN KEY (`expense_category_id`) REFERENCES `expense_categories` (`category_id`) ON DELETE SET NULL,
  CONSTRAINT `expenses_ibfk_2` FOREIGN KEY (`expense_vendor_id`) REFERENCES `vendors` (`vendor_id`) ON DELETE SET NULL,
  CONSTRAINT `expenses_ibfk_3` FOREIGN KEY (`expense_client_id`) REFERENCES `clients` (`client_id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `feature_comments`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `feature_comments` (
  `fc_id` int(11) NOT NULL AUTO_INCREMENT,
  `fc_feature_id` int(11) NOT NULL,
  `fc_user_id` int(11) DEFAULT NULL,
  `fc_message` text DEFAULT NULL,
  `fc_created_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`fc_id`),
  KEY `fc_feature_id` (`fc_feature_id`),
  CONSTRAINT `feature_comments_ibfk_1` FOREIGN KEY (`fc_feature_id`) REFERENCES `feature_requests` (`fr_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `feature_requests`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `feature_requests` (
  `fr_id` int(11) NOT NULL AUTO_INCREMENT,
  `fr_number` varchar(20) DEFAULT NULL,
  `fr_title` varchar(255) NOT NULL,
  `fr_description` text DEFAULT NULL,
  `fr_category` varchar(100) DEFAULT 'General',
  `fr_priority` enum('critical','high','medium','low','nice_to_have') DEFAULT 'medium',
  `fr_status` enum('idea','planned','in_progress','testing','released','declined') DEFAULT 'idea',
  `fr_requested_by` int(11) DEFAULT NULL,
  `fr_assigned_to` int(11) DEFAULT NULL,
  `fr_milestone` varchar(100) DEFAULT NULL,
  `fr_votes` int(11) DEFAULT 0,
  `fr_effort` enum('xs','s','m','l','xl') DEFAULT 'm',
  `fr_target_date` date DEFAULT NULL,
  `fr_released_in` varchar(50) DEFAULT NULL,
  `fr_notes` text DEFAULT NULL,
  `fr_created_at` datetime DEFAULT current_timestamp(),
  `fr_updated_at` datetime DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  `fr_closed_at` datetime DEFAULT NULL,
  PRIMARY KEY (`fr_id`),
  KEY `idx_fr_status` (`fr_status`),
  KEY `idx_fr_assigned` (`fr_assigned_to`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `files`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `files` (
  `file_id` int(11) NOT NULL AUTO_INCREMENT,
  `file_client_id` int(11) NOT NULL,
  `file_name` varchar(255) NOT NULL,
  `file_path` varchar(500) NOT NULL,
  `file_size` int(11) DEFAULT NULL,
  `file_ext` varchar(10) DEFAULT NULL,
  `file_uploaded_by` int(11) DEFAULT NULL,
  `file_created_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`file_id`),
  KEY `file_client_id` (`file_client_id`),
  KEY `file_uploaded_by` (`file_uploaded_by`),
  CONSTRAINT `files_ibfk_1` FOREIGN KEY (`file_client_id`) REFERENCES `clients` (`client_id`) ON DELETE CASCADE,
  CONSTRAINT `files_ibfk_2` FOREIGN KEY (`file_uploaded_by`) REFERENCES `users` (`user_id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `follow_ups`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `follow_ups` (
  `fu_id` int(11) NOT NULL AUTO_INCREMENT,
  `fu_lead_id` int(11) DEFAULT NULL,
  `fu_client_id` int(11) DEFAULT NULL,
  `fu_contact_name` varchar(200) DEFAULT NULL,
  `fu_type` enum('call','email','meeting','demo','proposal','check_in') DEFAULT 'call',
  `fu_subject` varchar(255) DEFAULT NULL,
  `fu_notes` text DEFAULT NULL,
  `fu_due_date` date NOT NULL,
  `fu_due_time` time DEFAULT NULL,
  `fu_assigned_to` int(11) DEFAULT NULL,
  `fu_status` enum('pending','completed','cancelled','rescheduled') DEFAULT 'pending',
  `fu_completed_at` datetime DEFAULT NULL,
  `fu_outcome` text DEFAULT NULL,
  `fu_created_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`fu_id`),
  KEY `idx_fu_due` (`fu_due_date`),
  KEY `idx_fu_assigned` (`fu_assigned_to`),
  KEY `idx_fu_lead` (`fu_lead_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `gchat_outbox`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `gchat_outbox` (
  `go_id` int(11) NOT NULL AUTO_INCREMENT,
  `go_queue_id` int(11) NOT NULL,
  `go_card` text NOT NULL,
  `go_status` varchar(10) DEFAULT 'pending',
  `go_error` varchar(255) DEFAULT NULL,
  `go_created_at` datetime DEFAULT current_timestamp(),
  `go_sent_at` datetime DEFAULT NULL,
  PRIMARY KEY (`go_id`),
  KEY `idx_go_status` (`go_status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `hr_certifications`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `hr_certifications` (
  `cert_id` int(11) NOT NULL AUTO_INCREMENT,
  `cert_emp_id` int(11) NOT NULL,
  `cert_name` varchar(200) NOT NULL,
  `cert_vendor` varchar(100) DEFAULT NULL,
  `cert_number` varchar(100) DEFAULT NULL,
  `cert_issued_date` date DEFAULT NULL,
  `cert_expiry_date` date DEFAULT NULL,
  `cert_status` enum('active','expired','pending') DEFAULT 'active',
  `cert_notes` text DEFAULT NULL,
  `cert_created_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`cert_id`),
  KEY `idx_cert_emp` (`cert_emp_id`),
  KEY `idx_cert_expiry` (`cert_expiry_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `hr_disciplinary`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `hr_disciplinary` (
  `hrd_id` int(11) NOT NULL AUTO_INCREMENT,
  `hrd_emp_id` int(11) NOT NULL,
  `hrd_type` enum('verbal','written','final','suspension','termination') DEFAULT 'verbal',
  `hrd_date` date DEFAULT NULL,
  `hrd_description` text DEFAULT NULL,
  `hrd_action_taken` text DEFAULT NULL,
  `hrd_issued_by` int(11) DEFAULT NULL,
  `hrd_acknowledged` tinyint(1) DEFAULT 0,
  `hrd_acknowledged_at` datetime DEFAULT NULL,
  `hrd_created_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`hrd_id`),
  KEY `hrd_emp_id` (`hrd_emp_id`),
  CONSTRAINT `hr_disciplinary_ibfk_1` FOREIGN KEY (`hrd_emp_id`) REFERENCES `hr_employees` (`emp_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `hr_documents`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `hr_documents` (
  `hrd_id` int(11) NOT NULL AUTO_INCREMENT,
  `hrd_emp_id` int(11) NOT NULL,
  `hrd_type` varchar(100) DEFAULT NULL,
  `hrd_title` varchar(255) DEFAULT NULL,
  `hrd_filename` varchar(255) DEFAULT NULL,
  `hrd_original_name` varchar(255) DEFAULT NULL,
  `hrd_uploaded_by` int(11) DEFAULT NULL,
  `hrd_notes` text DEFAULT NULL,
  `hrd_created_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`hrd_id`),
  KEY `hrd_emp_id` (`hrd_emp_id`),
  CONSTRAINT `hr_documents_ibfk_1` FOREIGN KEY (`hrd_emp_id`) REFERENCES `hr_employees` (`emp_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `hr_employee_training`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `hr_employee_training` (
  `het_id` int(11) NOT NULL AUTO_INCREMENT,
  `het_emp_id` int(11) NOT NULL,
  `het_course_key` varchar(50) NOT NULL,
  `het_enrollment_id` int(11) DEFAULT NULL,
  `het_learner_id` int(11) DEFAULT NULL,
  `het_due_date` date DEFAULT NULL,
  `het_status` enum('assigned','unassigned') NOT NULL DEFAULT 'assigned',
  `het_assigned_by` int(11) DEFAULT NULL,
  `het_assigned_at` datetime DEFAULT current_timestamp(),
  `het_unassigned_at` datetime DEFAULT NULL,
  PRIMARY KEY (`het_id`),
  UNIQUE KEY `uq_het_emp_course` (`het_emp_id`,`het_course_key`),
  KEY `idx_het_enrollment` (`het_enrollment_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `hr_employee_training_log`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `hr_employee_training_log` (
  `hel_id` int(11) NOT NULL AUTO_INCREMENT,
  `hel_emp_id` int(11) NOT NULL,
  `hel_user_id` int(11) DEFAULT NULL,
  `hel_text` varchar(500) NOT NULL,
  `hel_created_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`hel_id`),
  KEY `idx_hel_emp` (`hel_emp_id`,`hel_created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `hr_employees`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `hr_employees` (
  `emp_id` int(11) NOT NULL AUTO_INCREMENT,
  `emp_user_id` int(11) DEFAULT NULL,
  `emp_first_name` varchar(100) NOT NULL,
  `emp_last_name` varchar(100) NOT NULL DEFAULT '',
  `emp_email` varchar(255) DEFAULT NULL,
  `emp_phone` varchar(50) DEFAULT NULL,
  `emp_personal_email` varchar(255) DEFAULT NULL,
  `emp_dob` date DEFAULT NULL,
  `emp_ssn_last4` varchar(4) DEFAULT NULL,
  `emp_address` varchar(255) DEFAULT NULL,
  `emp_city` varchar(100) DEFAULT NULL,
  `emp_state` varchar(50) DEFAULT NULL,
  `emp_zip` varchar(20) DEFAULT NULL,
  `emp_hire_date` date DEFAULT NULL,
  `emp_term_date` date DEFAULT NULL,
  `emp_department` varchar(100) DEFAULT NULL,
  `emp_position` varchar(150) DEFAULT NULL,
  `emp_employment_type` enum('full-time','part-time','contract','intern') DEFAULT 'full-time',
  `emp_pay_type` enum('salary','hourly') DEFAULT 'hourly',
  `emp_pay_rate` decimal(10,2) DEFAULT 0.00,
  `emp_status` enum('active','on_leave','terminated') DEFAULT 'active',
  `emp_emergency_name` varchar(150) DEFAULT NULL,
  `emp_emergency_phone` varchar(50) DEFAULT NULL,
  `emp_emergency_relation` varchar(50) DEFAULT NULL,
  `emp_notes` text DEFAULT NULL,
  `emp_avatar` varchar(255) DEFAULT NULL,
  `emp_pto_balance` decimal(6,2) DEFAULT 0.00,
  `emp_sick_balance` decimal(6,2) DEFAULT 0.00,
  `emp_skills` text DEFAULT NULL,
  `emp_created_at` datetime DEFAULT current_timestamp(),
  `emp_updated_at` datetime DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  `emp_salary` decimal(12,2) DEFAULT 0.00,
  `emp_hourly_rate` decimal(8,2) DEFAULT 0.00,
  `emp_pto_accrual` decimal(6,2) DEFAULT 6.67,
  `emp_termination_date` date DEFAULT NULL,
  `emp_termination_reason` text DEFAULT NULL,
  `emp_next_review` date DEFAULT NULL,
  `emp_ssn_enc` text DEFAULT NULL,
  `emp_bank_account_enc` text DEFAULT NULL,
  `emp_bank_routing_enc` text DEFAULT NULL,
  `emp_dob_enc` text DEFAULT NULL,
  `emp_address_enc` text DEFAULT NULL,
  `emp_pay_rate_enc` text DEFAULT NULL,
  PRIMARY KEY (`emp_id`),
  KEY `idx_emp_user` (`emp_user_id`),
  KEY `idx_emp_status` (`emp_status`),
  CONSTRAINT `hr_employees_ibfk_1` FOREIGN KEY (`emp_user_id`) REFERENCES `users` (`user_id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `hr_equipment`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `hr_equipment` (
  `equip_id` int(11) NOT NULL AUTO_INCREMENT,
  `equip_emp_id` int(11) NOT NULL,
  `equip_name` varchar(200) NOT NULL,
  `equip_type` enum('laptop','phone','tablet','monitor','headset','keys','badge','vehicle','other') DEFAULT 'laptop',
  `equip_serial` varchar(100) DEFAULT NULL,
  `equip_asset_tag` varchar(50) DEFAULT NULL,
  `equip_issued_date` date DEFAULT NULL,
  `equip_returned_date` date DEFAULT NULL,
  `equip_condition` enum('new','good','fair','damaged') DEFAULT 'good',
  `equip_notes` varchar(255) DEFAULT NULL,
  `equip_created_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`equip_id`),
  KEY `idx_equip_emp` (`equip_emp_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `hr_incidents`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `hr_incidents` (
  `inc_id` int(11) NOT NULL AUTO_INCREMENT,
  `inc_emp_id` int(11) NOT NULL,
  `inc_type` enum('injury','safety','harassment','policy_violation','theft','other') DEFAULT 'other',
  `inc_date` date NOT NULL,
  `inc_location` varchar(255) DEFAULT NULL,
  `inc_description` text DEFAULT NULL,
  `inc_witnesses` text DEFAULT NULL,
  `inc_action_taken` text DEFAULT NULL,
  `inc_reported_by` int(11) DEFAULT NULL,
  `inc_status` enum('open','investigating','resolved','closed') DEFAULT 'open',
  `inc_created_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`inc_id`),
  KEY `idx_inc_emp` (`inc_emp_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `hr_mileage`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `hr_mileage` (
  `mile_id` int(11) NOT NULL AUTO_INCREMENT,
  `mile_emp_id` int(11) NOT NULL,
  `mile_user_id` int(11) DEFAULT NULL,
  `mile_date` date NOT NULL,
  `mile_client_id` int(11) DEFAULT NULL,
  `mile_ticket_id` int(11) DEFAULT NULL,
  `mile_from` varchar(200) DEFAULT NULL,
  `mile_to` varchar(200) DEFAULT NULL,
  `mile_start_odo` decimal(10,1) DEFAULT NULL,
  `mile_end_odo` decimal(10,1) DEFAULT NULL,
  `mile_purpose` varchar(255) DEFAULT NULL,
  `mile_distance` decimal(8,2) DEFAULT NULL,
  `mile_rate` decimal(6,4) DEFAULT 0.6700,
  `mile_amount` decimal(8,2) DEFAULT NULL,
  `mile_status` enum('pending','approved','paid') DEFAULT 'pending',
  `mile_approved_by` int(11) DEFAULT NULL,
  `mile_notes` varchar(255) DEFAULT NULL,
  `mile_created_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`mile_id`),
  KEY `idx_mile_emp` (`mile_emp_id`),
  KEY `idx_mile_user` (`mile_user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `hr_offers`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `hr_offers` (
  `offer_id` int(11) NOT NULL AUTO_INCREMENT,
  `offer_emp_id` int(11) DEFAULT NULL,
  `offer_candidate_name` varchar(150) NOT NULL,
  `offer_candidate_email` varchar(255) DEFAULT NULL,
  `offer_position` varchar(150) DEFAULT NULL,
  `offer_department` varchar(100) DEFAULT NULL,
  `offer_employment_type` enum('full-time','part-time','contract','intern') DEFAULT 'full-time',
  `offer_pay_type` enum('salary','hourly') DEFAULT 'salary',
  `offer_pay_rate` decimal(10,2) DEFAULT 0.00,
  `offer_start_date` date DEFAULT NULL,
  `offer_expires_date` date DEFAULT NULL,
  `offer_manager` varchar(150) DEFAULT NULL,
  `offer_body` text DEFAULT NULL,
  `offer_status` enum('draft','sent','accepted','declined','withdrawn') DEFAULT 'draft',
  `offer_created_by` int(11) DEFAULT NULL,
  `offer_created_at` datetime DEFAULT current_timestamp(),
  `offer_sent_at` datetime DEFAULT NULL,
  `offer_responded_at` datetime DEFAULT NULL,
  PRIMARY KEY (`offer_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `hr_oncall`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `hr_oncall` (
  `oncall_id` int(11) NOT NULL AUTO_INCREMENT,
  `oncall_emp_id` int(11) NOT NULL,
  `oncall_start_date` date NOT NULL,
  `oncall_end_date` date NOT NULL,
  `oncall_type` enum('primary','backup') DEFAULT 'primary',
  `oncall_notes` varchar(255) DEFAULT NULL,
  `oncall_created_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`oncall_id`),
  KEY `idx_oncall_emp` (`oncall_emp_id`),
  KEY `idx_oncall_dates` (`oncall_start_date`,`oncall_end_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `hr_pay_periods`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `hr_pay_periods` (
  `pp_id` int(11) NOT NULL AUTO_INCREMENT,
  `pp_start_date` date NOT NULL,
  `pp_end_date` date NOT NULL,
  `pp_status` enum('open','closed','paid') DEFAULT 'open',
  `pp_total_hours` decimal(8,2) DEFAULT 0.00,
  `pp_total_overtime` decimal(8,2) DEFAULT 0.00,
  `pp_closed_by` int(11) DEFAULT NULL,
  `pp_closed_at` datetime DEFAULT NULL,
  `pp_notes` text DEFAULT NULL,
  `pp_created_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`pp_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `hr_pto`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `hr_pto` (
  `pto_id` int(11) NOT NULL AUTO_INCREMENT,
  `pto_user_id` int(11) NOT NULL,
  `pto_type` enum('vacation','sick','personal','other') DEFAULT 'vacation',
  `pto_start_date` date DEFAULT NULL,
  `pto_end_date` date DEFAULT NULL,
  `pto_hours` decimal(6,2) DEFAULT 8.00,
  `pto_reason` text DEFAULT NULL,
  `pto_status` enum('pending','approved','denied','cancelled') DEFAULT 'pending',
  `pto_approved_by` int(11) DEFAULT NULL,
  `pto_created_at` datetime DEFAULT current_timestamp(),
  `pto_notes` text DEFAULT NULL,
  PRIMARY KEY (`pto_id`),
  KEY `idx_pto_user` (`pto_user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `hr_pto_requests`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `hr_pto_requests` (
  `pto_id` int(11) NOT NULL AUTO_INCREMENT,
  `pto_emp_id` int(11) NOT NULL,
  `pto_type` enum('vacation','sick','personal','bereavement','jury_duty','other') DEFAULT 'vacation',
  `pto_start_date` date NOT NULL,
  `pto_end_date` date NOT NULL,
  `pto_hours` decimal(5,2) DEFAULT 8.00,
  `pto_status` enum('pending','approved','denied','cancelled') DEFAULT 'pending',
  `pto_approved_by` int(11) DEFAULT NULL,
  `pto_notes` text DEFAULT NULL,
  `pto_created_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`pto_id`),
  KEY `idx_pto_emp` (`pto_emp_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `hr_reviews`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `hr_reviews` (
  `rv_id` int(11) NOT NULL AUTO_INCREMENT,
  `rv_user_id` int(11) DEFAULT NULL,
  `rv_employee_id` int(11) DEFAULT NULL,
  `rv_reviewer_id` int(11) DEFAULT NULL,
  `rv_type` enum('annual','quarterly','probation','promotion','improvement') DEFAULT 'annual',
  `rv_period` varchar(100) DEFAULT NULL,
  `rv_overall_rating` int(11) DEFAULT 0,
  `rv_quality_rating` int(11) DEFAULT 0,
  `rv_productivity_rating` int(11) DEFAULT 0,
  `rv_communication_rating` int(11) DEFAULT 0,
  `rv_teamwork_rating` int(11) DEFAULT 0,
  `rv_initiative_rating` int(11) DEFAULT 0,
  `rv_strengths` text DEFAULT NULL,
  `rv_improvements` text DEFAULT NULL,
  `rv_goals` text DEFAULT NULL,
  `rv_comments` text DEFAULT NULL,
  `rv_employee_comments` text DEFAULT NULL,
  `rv_acknowledged` tinyint(1) DEFAULT 0,
  `rv_acknowledged_at` datetime DEFAULT NULL,
  `rv_status` enum('draft','submitted','published','acknowledged') NOT NULL DEFAULT 'draft',
  `rv_created_at` datetime DEFAULT current_timestamp(),
  `rv_review_date` date DEFAULT NULL,
  `rv_rating_quality` int(11) DEFAULT 0,
  `rv_rating_productivity` int(11) DEFAULT 0,
  `rv_rating_communication` int(11) DEFAULT 0,
  `rv_rating_reliability` int(11) DEFAULT 0,
  `rv_rating_teamwork` int(11) DEFAULT 0,
  `rv_rating_overall` int(11) DEFAULT 0,
  PRIMARY KEY (`rv_id`),
  KEY `idx_rv_user` (`rv_user_id`),
  KEY `idx_rv_employee` (`rv_employee_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `hr_timeclock`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `hr_timeclock` (
  `tc_id` int(11) NOT NULL AUTO_INCREMENT,
  `tc_user_id` int(11) NOT NULL,
  `tc_employee_id` int(11) DEFAULT NULL,
  `tc_clock_in` datetime NOT NULL,
  `tc_clock_out` datetime DEFAULT NULL,
  `tc_hours` decimal(6,2) DEFAULT 0.00,
  `tc_break_minutes` int(11) DEFAULT 0,
  `tc_status` enum('clocked_in','clocked_out','approved','rejected','edited') DEFAULT 'clocked_in',
  `tc_notes` text DEFAULT NULL,
  `tc_ip_in` varchar(45) DEFAULT NULL,
  `tc_ip_out` varchar(45) DEFAULT NULL,
  `tc_type` enum('regular','overtime','holiday','oncall') DEFAULT 'regular',
  `tc_approved` tinyint(1) DEFAULT 0,
  `tc_approved_by` int(11) DEFAULT NULL,
  `tc_edited` tinyint(1) DEFAULT 0,
  `tc_edit_reason` varchar(255) DEFAULT NULL,
  `tc_client_id` int(11) DEFAULT NULL,
  `tc_ticket_id` int(11) DEFAULT NULL,
  `tc_created_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`tc_id`),
  KEY `idx_tc_user` (`tc_user_id`),
  KEY `idx_tc_status` (`tc_status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `hr_training`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `hr_training` (
  `hrt_id` int(11) NOT NULL AUTO_INCREMENT,
  `hrt_emp_id` int(11) NOT NULL,
  `hrt_title` varchar(255) DEFAULT NULL,
  `hrt_provider` varchar(200) DEFAULT NULL,
  `hrt_date_completed` date DEFAULT NULL,
  `hrt_expiry_date` date DEFAULT NULL,
  `hrt_cert_number` varchar(100) DEFAULT NULL,
  `hrt_notes` text DEFAULT NULL,
  `hrt_created_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`hrt_id`),
  KEY `hrt_emp_id` (`hrt_emp_id`),
  CONSTRAINT `hr_training_ibfk_1` FOREIGN KEY (`hrt_emp_id`) REFERENCES `hr_employees` (`emp_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `inventory_items`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `inventory_items` (
  `inv_id` int(11) NOT NULL AUTO_INCREMENT,
  `inv_name` varchar(200) NOT NULL,
  `inv_sku` varchar(100) DEFAULT NULL,
  `inv_category` varchar(100) DEFAULT NULL,
  `inv_description` text DEFAULT NULL,
  `inv_qty_on_hand` int(11) DEFAULT 0,
  `inv_qty_on_order` int(11) DEFAULT 0,
  `inv_reorder_point` int(11) DEFAULT 0,
  `inv_unit_cost` decimal(10,2) DEFAULT 0.00,
  `inv_unit_price` decimal(10,2) DEFAULT 0.00,
  `inv_location` varchar(120) DEFAULT NULL,
  `inv_vendor` varchar(160) DEFAULT NULL,
  `inv_link` varchar(500) DEFAULT NULL,
  `inv_notes` text DEFAULT NULL,
  `inv_archived` tinyint(1) DEFAULT 0,
  `inv_created_at` datetime DEFAULT current_timestamp(),
  `inv_updated_at` datetime DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  `inv_price_basis` varchar(20) DEFAULT NULL,
  PRIMARY KEY (`inv_id`),
  KEY `idx_inv_cat` (`inv_category`),
  KEY `idx_inv_archived` (`inv_archived`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `inventory_log`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `inventory_log` (
  `invlog_id` int(11) NOT NULL AUTO_INCREMENT,
  `invlog_item_id` int(11) NOT NULL,
  `invlog_user_id` int(11) DEFAULT NULL,
  `invlog_type` enum('received','used','ordered','adjusted','created') DEFAULT 'adjusted',
  `invlog_qty_change` int(11) DEFAULT 0,
  `invlog_qty_after` int(11) DEFAULT 0,
  `invlog_client_id` int(11) DEFAULT NULL,
  `invlog_ticket_id` int(11) DEFAULT NULL,
  `invlog_note` varchar(255) DEFAULT NULL,
  `invlog_created_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`invlog_id`),
  KEY `idx_invlog_item` (`invlog_item_id`),
  KEY `idx_invlog_created` (`invlog_created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `invoice_history`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `invoice_history` (
  `ih_id` int(11) NOT NULL AUTO_INCREMENT,
  `ih_invoice_id` int(11) NOT NULL,
  `ih_user_id` int(11) DEFAULT NULL,
  `ih_changed_at` datetime NOT NULL DEFAULT current_timestamp(),
  `ih_field` varchar(40) NOT NULL,
  `ih_old` varchar(255) DEFAULT NULL,
  `ih_new` varchar(255) DEFAULT NULL,
  `ih_note` varchar(255) DEFAULT NULL,
  `ih_client_visible` tinyint(1) NOT NULL DEFAULT 1,
  PRIMARY KEY (`ih_id`),
  KEY `idx_ih_invoice` (`ih_invoice_id`,`ih_changed_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `invoice_items`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `invoice_items` (
  `item_id` int(11) NOT NULL AUTO_INCREMENT,
  `item_invoice_id` int(11) NOT NULL,
  `item_description` varchar(255) NOT NULL,
  `item_qty` decimal(10,2) DEFAULT 1.00,
  `item_rate` decimal(10,2) DEFAULT 0.00,
  `item_tax` tinyint(1) DEFAULT 1,
  `item_total` decimal(10,2) DEFAULT 0.00,
  `item_sort_order` int(11) DEFAULT 0,
  PRIMARY KEY (`item_id`),
  KEY `item_invoice_id` (`item_invoice_id`),
  CONSTRAINT `invoice_items_ibfk_1` FOREIGN KEY (`item_invoice_id`) REFERENCES `invoices` (`invoice_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `invoice_templates`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `invoice_templates` (
  `template_id` int(11) NOT NULL AUTO_INCREMENT,
  `template_name` varchar(200) NOT NULL,
  `template_category` varchar(100) DEFAULT 'General',
  `template_description` varchar(500) DEFAULT NULL,
  `template_rate` decimal(10,2) DEFAULT 0.00,
  `template_quantity` decimal(8,2) DEFAULT 1.00,
  `template_unit` varchar(20) DEFAULT 'hour',
  PRIMARY KEY (`template_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `invoices`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `invoices` (
  `invoice_id` int(11) NOT NULL AUTO_INCREMENT,
  `invoice_number` varchar(50) NOT NULL,
  `invoice_client_id` int(11) NOT NULL,
  `invoice_scope` text DEFAULT NULL,
  `invoice_status` enum('draft','sent','viewed','partial','paid','overdue','cancelled','voided') DEFAULT 'draft',
  `invoice_view_count` int(11) DEFAULT 0,
  `invoice_viewed_at` datetime DEFAULT NULL,
  `invoice_last_viewed_at` datetime DEFAULT NULL,
  `invoice_date` date NOT NULL,
  `invoice_due_date` date NOT NULL,
  `invoice_subtotal` decimal(10,2) DEFAULT 0.00,
  `invoice_tax_rate` decimal(5,2) DEFAULT 0.00,
  `invoice_tax_amount` decimal(10,2) DEFAULT 0.00,
  `invoice_total` decimal(10,2) DEFAULT 0.00,
  `invoice_amount_paid` decimal(10,2) DEFAULT 0.00,
  `invoice_currency` varchar(3) DEFAULT 'USD',
  `invoice_notes` text DEFAULT NULL,
  `invoice_void_reason` text DEFAULT NULL,
  `invoice_voided_at` datetime DEFAULT NULL,
  `invoice_last_late_fee_at` date DEFAULT NULL,
  `invoice_recurring_id` int(11) DEFAULT NULL,
  `invoice_period_start` date DEFAULT NULL,
  `invoice_created_at` datetime DEFAULT current_timestamp(),
  `invoice_updated_at` datetime DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  `invoice_payment_token` varchar(64) DEFAULT NULL,
  `invoice_paid_date` date DEFAULT NULL,
  `invoice_autopay_attempted` tinyint(1) DEFAULT 0,
  `invoice_autopay_last_error` varchar(255) DEFAULT NULL,
  `invoice_autopay_attempts` int(11) DEFAULT 0,
  `invoice_autopay_next_at` datetime DEFAULT NULL,
  `invoice_autopay_hold` tinyint(1) DEFAULT 0,
  `invoice_autopay_last_attempt_at` datetime DEFAULT NULL,
  `invoice_autopay_paid_at` datetime DEFAULT NULL,
  `invoice_sent_at` datetime DEFAULT NULL,
  `invoice_sent_to` varchar(190) DEFAULT NULL,
  `invoice_sent_count` int(11) NOT NULL DEFAULT 0,
  `invoice_send_at` datetime DEFAULT NULL,
  `invoice_send_scheduled_by` int(11) DEFAULT NULL,
  PRIMARY KEY (`invoice_id`),
  UNIQUE KEY `invoice_number` (`invoice_number`),
  KEY `invoice_client_id` (`invoice_client_id`),
  CONSTRAINT `invoices_ibfk_1` FOREIGN KEY (`invoice_client_id`) REFERENCES `clients` (`client_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `ip_bans`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `ip_bans` (
  `ban_id` int(11) NOT NULL AUTO_INCREMENT,
  `ban_ip` varchar(45) NOT NULL,
  `ban_reason` varchar(255) DEFAULT NULL,
  `ban_expires_at` datetime DEFAULT NULL,
  `ban_created_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`ban_id`),
  UNIQUE KEY `ban_ip` (`ban_ip`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `kb_articles`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `kb_articles` (
  `kb_id` int(11) NOT NULL AUTO_INCREMENT,
  `kb_category_id` int(11) DEFAULT NULL,
  `kb_title` varchar(255) NOT NULL,
  `kb_slug` varchar(255) DEFAULT NULL,
  `kb_content` longtext DEFAULT NULL,
  `kb_excerpt` varchar(500) DEFAULT NULL,
  `kb_portal_visible` tinyint(1) DEFAULT 1,
  `kb_featured` tinyint(1) DEFAULT 0,
  `kb_views` int(11) DEFAULT 0,
  `kb_helpful_yes` int(11) DEFAULT 0,
  `kb_helpful_no` int(11) DEFAULT 0,
  `kb_created_by` int(11) DEFAULT NULL,
  `kb_created_at` datetime DEFAULT current_timestamp(),
  `kb_updated_at` datetime DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  `kb_archived` tinyint(1) DEFAULT 0,
  PRIMARY KEY (`kb_id`),
  KEY `kb_category_id` (`kb_category_id`),
  FULLTEXT KEY `ft_kb` (`kb_title`,`kb_content`),
  CONSTRAINT `kb_articles_ibfk_1` FOREIGN KEY (`kb_category_id`) REFERENCES `kb_categories` (`kbc_id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `kb_categories`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `kb_categories` (
  `kbc_id` int(11) NOT NULL AUTO_INCREMENT,
  `kbc_name` varchar(100) NOT NULL,
  `kbc_icon` varchar(50) DEFAULT 'bi-folder',
  `kbc_color` varchar(20) DEFAULT 'primary',
  `kbc_sort_order` int(11) DEFAULT 0,
  `kbc_portal_visible` tinyint(1) DEFAULT 1,
  PRIMARY KEY (`kbc_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `late_fee_waivers`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `late_fee_waivers` (
  `waiver_id` int(11) NOT NULL AUTO_INCREMENT,
  `waiver_client_id` int(11) NOT NULL,
  `waiver_invoice_id` int(11) NOT NULL,
  `waiver_amount` decimal(10,2) NOT NULL DEFAULT 0.00,
  `waiver_reason` varchar(255) NOT NULL,
  `waiver_user_id` int(11) DEFAULT NULL,
  `waiver_created_at` datetime NOT NULL DEFAULT current_timestamp(),
  PRIMARY KEY (`waiver_id`),
  KEY `idx_waiver_client` (`waiver_client_id`,`waiver_created_at`),
  KEY `idx_waiver_invoice` (`waiver_invoice_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `lead_activities`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `lead_activities` (
  `activity_id` int(11) NOT NULL AUTO_INCREMENT,
  `activity_lead_id` int(11) NOT NULL,
  `activity_type` enum('note','call','email','meeting','proposal','status_change') DEFAULT 'note',
  `activity_content` text DEFAULT NULL,
  `activity_created_by` int(11) DEFAULT NULL,
  `activity_created_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`activity_id`),
  KEY `activity_lead_id` (`activity_lead_id`),
  CONSTRAINT `lead_activities_ibfk_1` FOREIGN KEY (`activity_lead_id`) REFERENCES `leads` (`lead_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `leads`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `leads` (
  `lead_id` int(11) NOT NULL AUTO_INCREMENT,
  `lead_company` varchar(200) NOT NULL,
  `lead_contact_name` varchar(200) DEFAULT NULL,
  `lead_email` varchar(200) DEFAULT NULL,
  `lead_phone` varchar(50) DEFAULT NULL,
  `lead_website` varchar(255) DEFAULT NULL,
  `lead_industry` varchar(100) DEFAULT NULL,
  `lead_employee_count` int(11) DEFAULT 0,
  `lead_workstation_count` int(11) DEFAULT 0,
  `lead_source` varchar(100) DEFAULT 'manual',
  `lead_stage` enum('new','contacted','qualified','proposal','negotiation','won','lost') DEFAULT 'new',
  `lead_score` int(11) DEFAULT 0,
  `lead_value` decimal(10,2) DEFAULT 0.00,
  `lead_notes` text DEFAULT NULL,
  `lead_next_followup` date DEFAULT NULL,
  `lead_lost_reason` varchar(255) DEFAULT NULL,
  `lead_assigned_to` int(11) DEFAULT NULL,
  `lead_converted_client_id` int(11) DEFAULT NULL,
  `lead_created_by` int(11) DEFAULT NULL,
  `lead_created_at` datetime DEFAULT current_timestamp(),
  `lead_updated_at` datetime DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  `lead_temperature` enum('cold','warm','hot') DEFAULT 'cold',
  `lead_estimated_value` decimal(10,2) DEFAULT 0.00,
  `lead_probability` int(11) DEFAULT 10,
  `lead_next_action` varchar(255) DEFAULT NULL,
  `lead_next_action_date` date DEFAULT NULL,
  `lead_competitor` varchar(200) DEFAULT NULL,
  `lead_decision_maker` varchar(200) DEFAULT NULL,
  `lead_timeline` varchar(100) DEFAULT NULL,
  `lead_pain_points` text DEFAULT NULL,
  `lead_current_provider` varchar(200) DEFAULT NULL,
  `lead_server_count` int(11) DEFAULT 0,
  `lead_won_reason` varchar(255) DEFAULT NULL,
  `lead_close_notes` text DEFAULT NULL,
  `lead_priority` enum('urgent','high','medium','low') NOT NULL DEFAULT 'low',
  `lead_dnc` tinyint(1) NOT NULL DEFAULT 0,
  `lead_dnc_reason` varchar(255) DEFAULT NULL,
  `lead_dnc_at` datetime DEFAULT NULL,
  PRIMARY KEY (`lead_id`),
  KEY `lead_assigned_to` (`lead_assigned_to`),
  CONSTRAINT `leads_ibfk_1` FOREIGN KEY (`lead_assigned_to`) REFERENCES `users` (`user_id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `locations`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `locations` (
  `location_id` int(11) NOT NULL AUTO_INCREMENT,
  `location_client_id` int(11) NOT NULL,
  `location_name` varchar(200) NOT NULL,
  `location_address` varchar(255) DEFAULT NULL,
  `location_city` varchar(100) DEFAULT NULL,
  `location_state` varchar(50) DEFAULT NULL,
  `location_zip` varchar(20) DEFAULT NULL,
  `location_phone` varchar(50) DEFAULT NULL,
  `location_notes` text DEFAULT NULL,
  `location_created_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`location_id`),
  KEY `location_client_id` (`location_client_id`),
  CONSTRAINT `locations_ibfk_1` FOREIGN KEY (`location_client_id`) REFERENCES `clients` (`client_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `login_attempts`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `login_attempts` (
  `attempt_id` int(11) NOT NULL AUTO_INCREMENT,
  `attempt_ip` varchar(45) NOT NULL,
  `attempt_email` varchar(200) DEFAULT NULL,
  `attempt_success` tinyint(1) DEFAULT 0,
  `attempt_created_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`attempt_id`),
  KEY `idx_ip_time` (`attempt_ip`,`attempt_created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `migrations`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `migrations` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `migration_file` varchar(255) NOT NULL,
  `applied_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`id`),
  UNIQUE KEY `migration_file` (`migration_file`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `missed_calls`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `missed_calls` (
  `call_id` int(11) NOT NULL AUTO_INCREMENT,
  `call_client_id` int(11) DEFAULT NULL,
  `call_contact_name` varchar(200) DEFAULT NULL,
  `call_phone` varchar(50) DEFAULT NULL,
  `call_reason` varchar(255) DEFAULT NULL,
  `call_returned` tinyint(1) DEFAULT 0,
  `call_returned_at` datetime DEFAULT NULL,
  `call_returned_by` int(11) DEFAULT NULL,
  `call_created_by` int(11) DEFAULT NULL,
  `call_created_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`call_id`),
  KEY `call_client_id` (`call_client_id`),
  CONSTRAINT `missed_calls_ibfk_1` FOREIGN KEY (`call_client_id`) REFERENCES `clients` (`client_id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `mobile_tokens`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `mobile_tokens` (
  `token` varchar(64) NOT NULL,
  `user_id` int(11) DEFAULT NULL,
  `device` varchar(120) DEFAULT NULL,
  `pending` tinyint(4) DEFAULT 0,
  `created_at` datetime DEFAULT current_timestamp(),
  `last_used_at` datetime DEFAULT NULL,
  `token_fp` char(64) DEFAULT NULL,
  PRIMARY KEY (`token`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `networks`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `networks` (
  `network_id` int(11) NOT NULL AUTO_INCREMENT,
  `network_client_id` int(11) NOT NULL,
  `network_location_id` int(11) DEFAULT NULL,
  `network_name` varchar(200) NOT NULL,
  `network_subnet` varchar(18) DEFAULT NULL,
  `network_gateway` varchar(45) DEFAULT NULL,
  `network_dns1` varchar(45) DEFAULT NULL,
  `network_dns2` varchar(45) DEFAULT NULL,
  `network_dhcp_range` varchar(100) DEFAULT NULL,
  `network_vlan` int(11) DEFAULT NULL,
  `network_notes` text DEFAULT NULL,
  `network_created_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`network_id`),
  KEY `network_client_id` (`network_client_id`),
  KEY `network_location_id` (`network_location_id`),
  CONSTRAINT `networks_ibfk_1` FOREIGN KEY (`network_client_id`) REFERENCES `clients` (`client_id`) ON DELETE CASCADE,
  CONSTRAINT `networks_ibfk_2` FOREIGN KEY (`network_location_id`) REFERENCES `locations` (`location_id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `notifications`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `notifications` (
  `notif_id` int(11) NOT NULL AUTO_INCREMENT,
  `notif_user_id` int(11) NOT NULL,
  `notif_type` varchar(50) DEFAULT 'general',
  `notif_title` varchar(255) DEFAULT NULL,
  `notif_body` text DEFAULT NULL,
  `notif_message` text DEFAULT NULL,
  `notif_link` varchar(500) DEFAULT NULL,
  `notif_read` tinyint(1) DEFAULT 0,
  `notif_created_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`notif_id`),
  KEY `idx_notif_user` (`notif_user_id`),
  KEY `idx_notif_read` (`notif_read`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `payment_gateways`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `payment_gateways` (
  `gateway_id` int(11) NOT NULL AUTO_INCREMENT,
  `gateway_name` varchar(100) NOT NULL,
  `gateway_type` enum('stripe','paypal') NOT NULL,
  `gateway_enabled` tinyint(1) DEFAULT 0,
  `gateway_mode` enum('test','live') DEFAULT 'test',
  `gateway_public_key` varchar(500) DEFAULT NULL,
  `gateway_secret_key` varchar(500) DEFAULT NULL,
  `gateway_webhook_secret` varchar(500) DEFAULT NULL,
  `gateway_extra` text DEFAULT NULL,
  `gateway_created_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`gateway_id`),
  UNIQUE KEY `uq_gateway_type` (`gateway_type`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `payment_plan_installments`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `payment_plan_installments` (
  `inst_id` int(11) NOT NULL AUTO_INCREMENT,
  `inst_plan_id` int(11) NOT NULL,
  `inst_number` int(11) NOT NULL,
  `inst_amount` decimal(10,2) NOT NULL,
  `inst_due_date` date NOT NULL,
  `inst_status` varchar(20) NOT NULL DEFAULT 'scheduled',
  `inst_paid_at` datetime DEFAULT NULL,
  `inst_attempt_count` int(11) DEFAULT 0,
  `inst_last_error` varchar(255) DEFAULT NULL,
  PRIMARY KEY (`inst_id`),
  KEY `idx_inst_plan` (`inst_plan_id`),
  CONSTRAINT `payment_plan_installments_ibfk_1` FOREIGN KEY (`inst_plan_id`) REFERENCES `payment_plans` (`plan_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `payment_plans`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `payment_plans` (
  `plan_id` int(11) NOT NULL AUTO_INCREMENT,
  `plan_client_id` int(11) NOT NULL,
  `plan_total_amount` decimal(10,2) NOT NULL DEFAULT 0.00,
  `plan_installment_count` int(11) NOT NULL DEFAULT 1,
  `plan_frequency` varchar(20) NOT NULL DEFAULT 'monthly',
  `plan_start_date` date DEFAULT NULL,
  `plan_status` varchar(20) NOT NULL DEFAULT 'active',
  `plan_requested_by_portal` tinyint(1) DEFAULT 0,
  `plan_request_note` varchar(500) DEFAULT NULL,
  `plan_notes` varchar(500) DEFAULT NULL,
  `plan_strikes` int(11) DEFAULT 0,
  `plan_broken_at` datetime DEFAULT NULL,
  `plan_created_by` int(11) DEFAULT NULL,
  `plan_created_at` datetime DEFAULT current_timestamp(),
  `plan_updated_at` datetime DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  PRIMARY KEY (`plan_id`),
  KEY `idx_plan_client` (`plan_client_id`),
  CONSTRAINT `payment_plans_ibfk_1` FOREIGN KEY (`plan_client_id`) REFERENCES `clients` (`client_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `payments`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `payments` (
  `payment_id` int(11) NOT NULL AUTO_INCREMENT,
  `payment_invoice_id` int(11) NOT NULL,
  `payment_amount` decimal(10,2) NOT NULL,
  `payment_method` varchar(50) DEFAULT NULL,
  `payment_reference` varchar(255) DEFAULT NULL,
  `payment_date` date NOT NULL,
  `payment_created_at` datetime DEFAULT current_timestamp(),
  `payment_source` varchar(20) NOT NULL DEFAULT 'staff',
  `payment_recorded_by` int(11) DEFAULT NULL,
  `payment_note` varchar(255) DEFAULT NULL,
  `payment_voided_at` datetime DEFAULT NULL,
  `payment_void_reason` varchar(255) DEFAULT NULL,
  `payment_voided_by` int(11) DEFAULT NULL,
  PRIMARY KEY (`payment_id`),
  KEY `payment_invoice_id` (`payment_invoice_id`),
  CONSTRAINT `payments_ibfk_1` FOREIGN KEY (`payment_invoice_id`) REFERENCES `invoices` (`invoice_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `policy_acks`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `policy_acks` (
  `pa_id` int(11) NOT NULL AUTO_INCREMENT,
  `pa_policy_id` int(11) NOT NULL,
  `pa_name` varchar(150) NOT NULL,
  `pa_email` varchar(255) DEFAULT NULL,
  `pa_token` varchar(64) DEFAULT NULL,
  `pa_sent_at` datetime DEFAULT NULL,
  `pa_reminders` int(11) NOT NULL DEFAULT 0,
  `pa_acked_at` datetime DEFAULT NULL,
  `pa_ip` varchar(64) DEFAULT NULL,
  `pa_method` enum('link','kiosk','paper') DEFAULT NULL,
  `pa_created_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`pa_id`),
  KEY `idx_pa_policy` (`pa_policy_id`),
  KEY `idx_pa_token` (`pa_token`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `policy_templates`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `policy_templates` (
  `pt_id` int(11) NOT NULL AUTO_INCREMENT,
  `pt_key` varchar(50) NOT NULL,
  `pt_name` varchar(150) NOT NULL,
  `pt_category` enum('general','hipaa','legal','nonprofit','insurance','optional') NOT NULL DEFAULT 'general',
  `pt_description` text DEFAULT NULL,
  `pt_tags` varchar(255) DEFAULT NULL,
  `pt_recommend_for` varchar(255) DEFAULT NULL,
  `pt_requires_ack` tinyint(1) NOT NULL DEFAULT 1,
  `pt_sections` mediumtext DEFAULT NULL,
  `pt_version` int(11) NOT NULL DEFAULT 1,
  `pt_active` tinyint(1) NOT NULL DEFAULT 1,
  `pt_created_at` datetime DEFAULT current_timestamp(),
  `pt_updated_at` datetime DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  PRIMARY KEY (`pt_id`),
  UNIQUE KEY `pt_key` (`pt_key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `portal_groups`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `portal_groups` (
  `pg_id` int(11) NOT NULL AUTO_INCREMENT,
  `pg_name` varchar(200) NOT NULL,
  `pg_description` varchar(255) DEFAULT NULL,
  `pg_can_view_billing` tinyint(1) DEFAULT 0,
  `pg_can_view_contracts` tinyint(1) DEFAULT 0,
  `pg_can_view_assets` tinyint(1) DEFAULT 1,
  `pg_can_submit_tickets` tinyint(1) DEFAULT 1,
  `pg_can_view_all_tickets` tinyint(1) DEFAULT 0,
  `pg_can_send_messages` tinyint(1) DEFAULT 1,
  `pg_can_view_kb` tinyint(1) DEFAULT 1,
  `pg_created_at` datetime DEFAULT current_timestamp(),
  `pg_can_view_policies` tinyint(1) DEFAULT 1,
  PRIMARY KEY (`pg_id`),
  UNIQUE KEY `uq_pg_name` (`pg_name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `portal_users`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `portal_users` (
  `portal_user_id` int(11) NOT NULL AUTO_INCREMENT,
  `portal_client_id` int(11) NOT NULL,
  `portal_contact_id` int(11) DEFAULT NULL,
  `portal_name` varchar(200) NOT NULL,
  `portal_email` varchar(200) NOT NULL,
  `portal_password` varchar(255) NOT NULL,
  `portal_role` enum('admin','standard') DEFAULT 'standard',
  `portal_last_login` datetime DEFAULT NULL,
  `portal_active` tinyint(1) DEFAULT 1,
  `portal_disabled_reason` varchar(200) DEFAULT NULL,
  `portal_disabled_at` datetime DEFAULT NULL,
  `portal_created_at` datetime DEFAULT current_timestamp(),
  `portal_group_id` int(11) DEFAULT NULL,
  `portal_can_view_billing` tinyint(1) DEFAULT 0,
  `portal_can_view_contracts` tinyint(1) DEFAULT 0,
  `portal_can_view_assets` tinyint(1) DEFAULT 1,
  `portal_can_submit_tickets` tinyint(1) DEFAULT 1,
  `portal_can_view_all_tickets` tinyint(1) DEFAULT 0,
  `portal_can_send_messages` tinyint(1) DEFAULT 1,
  `portal_can_view_policies` tinyint(1) DEFAULT 1,
  PRIMARY KEY (`portal_user_id`),
  UNIQUE KEY `portal_email` (`portal_email`),
  KEY `portal_client_id` (`portal_client_id`),
  KEY `portal_contact_id` (`portal_contact_id`),
  CONSTRAINT `portal_users_ibfk_1` FOREIGN KEY (`portal_client_id`) REFERENCES `clients` (`client_id`) ON DELETE CASCADE,
  CONSTRAINT `portal_users_ibfk_2` FOREIGN KEY (`portal_contact_id`) REFERENCES `contacts` (`contact_id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `project_files`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `project_files` (
  `file_id` int(11) NOT NULL AUTO_INCREMENT,
  `file_project_id` int(11) NOT NULL,
  `file_filename` varchar(255) NOT NULL,
  `file_original_name` varchar(255) NOT NULL,
  `file_mime_type` varchar(120) DEFAULT NULL,
  `file_size` int(11) DEFAULT 0,
  `file_notes` varchar(500) DEFAULT NULL,
  `file_uploaded_by` int(11) DEFAULT NULL,
  `file_created_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`file_id`),
  KEY `idx_project_files_project` (`file_project_id`),
  CONSTRAINT `project_files_ibfk_1` FOREIGN KEY (`file_project_id`) REFERENCES `projects` (`project_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `project_tasks`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `project_tasks` (
  `task_id` int(11) NOT NULL AUTO_INCREMENT,
  `task_project_id` int(11) NOT NULL,
  `task_title` varchar(255) NOT NULL,
  `task_description` text DEFAULT NULL,
  `task_status` varchar(20) NOT NULL DEFAULT 'todo',
  `task_assigned_to` int(11) DEFAULT NULL,
  `task_due_date` date DEFAULT NULL,
  `task_sort_order` int(11) DEFAULT 0,
  `task_completed_by` int(11) DEFAULT NULL,
  `task_completed_at` datetime DEFAULT NULL,
  `task_created_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`task_id`),
  KEY `idx_task_project` (`task_project_id`),
  CONSTRAINT `project_tasks_ibfk_1` FOREIGN KEY (`task_project_id`) REFERENCES `projects` (`project_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `project_templates`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `project_templates` (
  `template_id` int(11) NOT NULL AUTO_INCREMENT,
  `template_name` varchar(200) NOT NULL,
  `template_description` varchar(500) DEFAULT NULL,
  `template_tasks` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL CHECK (json_valid(`template_tasks`)),
  `template_created_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`template_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `project_updates`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `project_updates` (
  `update_id` int(11) NOT NULL AUTO_INCREMENT,
  `update_project_id` int(11) NOT NULL,
  `update_user_id` int(11) DEFAULT NULL,
  `update_type` varchar(20) NOT NULL DEFAULT 'note',
  `update_body` text DEFAULT NULL,
  `update_time_spent` decimal(6,2) DEFAULT 0.00,
  `update_work_type` varchar(100) DEFAULT NULL,
  `update_billable` tinyint(1) DEFAULT 1,
  `update_invoice_id` int(11) DEFAULT NULL,
  `update_created_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`update_id`),
  KEY `idx_update_project` (`update_project_id`),
  CONSTRAINT `project_updates_ibfk_1` FOREIGN KEY (`update_project_id`) REFERENCES `projects` (`project_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `projects`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `projects` (
  `project_id` int(11) NOT NULL AUTO_INCREMENT,
  `project_number` varchar(30) NOT NULL,
  `project_name` varchar(255) NOT NULL,
  `project_description` text DEFAULT NULL,
  `project_client_id` int(11) DEFAULT NULL,
  `project_status` varchar(30) NOT NULL DEFAULT 'planning',
  `project_owner_id` int(11) DEFAULT NULL,
  `project_template_id` int(11) DEFAULT NULL,
  `project_billable` tinyint(1) DEFAULT 1,
  `project_budget_hours` decimal(8,2) DEFAULT NULL,
  `project_start_date` date DEFAULT NULL,
  `project_due_date` date DEFAULT NULL,
  `project_completed_at` datetime DEFAULT NULL,
  `project_source_ticket_id` int(11) DEFAULT NULL,
  `project_created_by` int(11) DEFAULT NULL,
  `project_created_at` datetime DEFAULT current_timestamp(),
  `project_updated_at` datetime DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  PRIMARY KEY (`project_id`),
  UNIQUE KEY `project_number` (`project_number`),
  KEY `idx_project_client` (`project_client_id`),
  KEY `idx_project_status` (`project_status`),
  CONSTRAINT `projects_ibfk_1` FOREIGN KEY (`project_client_id`) REFERENCES `clients` (`client_id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `proposals`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `proposals` (
  `prop_id` int(11) NOT NULL AUTO_INCREMENT,
  `prop_number` varchar(50) DEFAULT NULL,
  `prop_client_id` int(11) DEFAULT NULL,
  `prop_lead_id` int(11) DEFAULT NULL,
  `prop_title` varchar(255) NOT NULL,
  `prop_description` text DEFAULT NULL,
  `prop_amount` decimal(12,2) DEFAULT 0.00,
  `prop_mrr` decimal(10,2) DEFAULT 0.00,
  `prop_status` enum('draft','sent','viewed','accepted','declined','expired') DEFAULT 'draft',
  `prop_valid_until` date DEFAULT NULL,
  `prop_sent_at` datetime DEFAULT NULL,
  `prop_viewed_at` datetime DEFAULT NULL,
  `prop_accepted_at` datetime DEFAULT NULL,
  `prop_created_by` int(11) DEFAULT NULL,
  `prop_notes` text DEFAULT NULL,
  `prop_created_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`prop_id`),
  KEY `idx_prop_client` (`prop_client_id`),
  KEY `idx_prop_lead` (`prop_lead_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `public_tickets`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `public_tickets` (
  `pt_id` int(11) NOT NULL AUTO_INCREMENT,
  `pt_ticket_id` int(11) DEFAULT NULL,
  `pt_name` varchar(200) DEFAULT NULL,
  `pt_email` varchar(200) DEFAULT NULL,
  `pt_phone` varchar(50) DEFAULT NULL,
  `pt_company` varchar(200) DEFAULT NULL,
  `pt_subject` varchar(255) DEFAULT NULL,
  `pt_details` text DEFAULT NULL,
  `pt_priority` varchar(20) DEFAULT 'medium',
  `pt_status` enum('new','linked','spam') DEFAULT 'new',
  `pt_created_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`pt_id`),
  KEY `idx_pt_status` (`pt_status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `push_outbox`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `push_outbox` (
  `po_id` int(11) NOT NULL AUTO_INCREMENT,
  `po_user_ids` varchar(2000) NOT NULL,
  `po_title` varchar(250) NOT NULL,
  `po_body` varchar(500) NOT NULL,
  `po_extra` varchar(1000) DEFAULT NULL,
  `po_status` varchar(10) DEFAULT 'pending',
  `po_created_at` datetime DEFAULT current_timestamp(),
  `po_sent_at` datetime DEFAULT NULL,
  PRIMARY KEY (`po_id`),
  KEY `idx_po_status` (`po_status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `quote_items`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `quote_items` (
  `qi_id` int(11) NOT NULL AUTO_INCREMENT,
  `qi_quote_id` int(11) NOT NULL,
  `qi_description` varchar(500) DEFAULT NULL,
  `qi_quantity` decimal(10,2) DEFAULT 1.00,
  `qi_rate` decimal(10,2) DEFAULT 0.00,
  `qi_amount` decimal(10,2) DEFAULT 0.00,
  `qi_taxable` tinyint(1) DEFAULT 0,
  `qi_sort_order` int(11) DEFAULT 0,
  PRIMARY KEY (`qi_id`),
  KEY `qi_quote_id` (`qi_quote_id`),
  CONSTRAINT `quote_items_ibfk_1` FOREIGN KEY (`qi_quote_id`) REFERENCES `quotes` (`quote_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `quotes`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `quotes` (
  `quote_id` int(11) NOT NULL AUTO_INCREMENT,
  `quote_number` varchar(50) NOT NULL,
  `quote_client_id` int(11) NOT NULL,
  `quote_scope` text DEFAULT NULL,
  `quote_status` enum('draft','sent','accepted','declined','invoiced','voided') DEFAULT 'draft',
  `quote_date` date NOT NULL,
  `quote_expire_date` date DEFAULT NULL,
  `quote_subtotal` decimal(10,2) DEFAULT 0.00,
  `quote_tax_rate` decimal(5,2) DEFAULT 0.00,
  `quote_total` decimal(10,2) DEFAULT 0.00,
  `quote_notes` text DEFAULT NULL,
  `quote_void_reason` text DEFAULT NULL,
  `quote_voided_at` datetime DEFAULT NULL,
  `quote_token` varchar(64) DEFAULT NULL,
  `quote_sent_at` datetime DEFAULT NULL,
  `quote_accepted_at` datetime DEFAULT NULL,
  `quote_accepted_name` varchar(200) DEFAULT NULL,
  `quote_created_at` datetime DEFAULT current_timestamp(),
  `quote_followup_count` int(11) DEFAULT 0,
  `quote_last_followup_at` datetime DEFAULT NULL,
  `quote_view_count` int(11) NOT NULL DEFAULT 0,
  `quote_viewed_at` datetime DEFAULT NULL,
  `quote_last_viewed_at` datetime DEFAULT NULL,
  PRIMARY KEY (`quote_id`),
  UNIQUE KEY `quote_number` (`quote_number`),
  KEY `quote_client_id` (`quote_client_id`),
  CONSTRAINT `quotes_ibfk_1` FOREIGN KEY (`quote_client_id`) REFERENCES `clients` (`client_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `recurring_invoice_items`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `recurring_invoice_items` (
  `ri_item_id` int(11) NOT NULL AUTO_INCREMENT,
  `ri_recurring_id` int(11) NOT NULL,
  `ri_description` varchar(500) DEFAULT NULL,
  `ri_qty` decimal(10,2) DEFAULT 1.00,
  `ri_rate` decimal(10,2) DEFAULT 0.00,
  `ri_total` decimal(10,2) DEFAULT 0.00,
  `ri_sort` int(11) DEFAULT 0,
  PRIMARY KEY (`ri_item_id`),
  KEY `ri_recurring_id` (`ri_recurring_id`),
  CONSTRAINT `recurring_invoice_items_ibfk_1` FOREIGN KEY (`ri_recurring_id`) REFERENCES `recurring_invoices` (`recurring_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `recurring_invoices`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `recurring_invoices` (
  `recurring_id` int(11) NOT NULL AUTO_INCREMENT,
  `recurring_client_id` int(11) NOT NULL,
  `recurring_frequency` enum('monthly','quarterly','semiannual','annual') DEFAULT 'monthly',
  `recurring_next_date` date NOT NULL,
  `recurring_scope` text DEFAULT NULL,
  `recurring_subtotal` decimal(10,2) DEFAULT 0.00,
  `recurring_tax_rate` decimal(5,2) DEFAULT 0.00,
  `recurring_status` enum('active','paused') DEFAULT 'active',
  `recurring_zoho_id` varchar(50) DEFAULT NULL,
  `recurring_created_at` datetime DEFAULT current_timestamp(),
  `recurring_delivery` enum('draft','send') NOT NULL DEFAULT 'send',
  `recurring_net_days` int(11) DEFAULT NULL,
  PRIMARY KEY (`recurring_id`),
  KEY `recurring_client_id` (`recurring_client_id`),
  CONSTRAINT `recurring_invoices_ibfk_1` FOREIGN KEY (`recurring_client_id`) REFERENCES `clients` (`client_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `recurring_tasks`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `recurring_tasks` (
  `rt_id` int(11) NOT NULL AUTO_INCREMENT,
  `rt_name` varchar(255) NOT NULL,
  `rt_description` text DEFAULT NULL,
  `rt_client_id` int(11) DEFAULT NULL,
  `rt_priority` enum('low','medium','high','critical') DEFAULT 'medium',
  `rt_category` varchar(100) DEFAULT NULL,
  `rt_frequency` enum('daily','weekly','biweekly','monthly','quarterly','yearly') DEFAULT 'monthly',
  `rt_day_of_month` tinyint(4) DEFAULT 1,
  `rt_day_of_week` tinyint(4) DEFAULT 1,
  `rt_assign_to` int(11) DEFAULT NULL,
  `rt_active` tinyint(1) DEFAULT 1,
  `rt_last_generated_at` datetime DEFAULT NULL,
  `rt_next_run` date DEFAULT NULL,
  `rt_created_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`rt_id`),
  KEY `idx_rt_next` (`rt_next_run`),
  KEY `idx_rt_client` (`rt_client_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `recurring_tickets`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `recurring_tickets` (
  `recurring_id` int(11) NOT NULL AUTO_INCREMENT,
  `recurring_client_id` int(11) NOT NULL,
  `recurring_subject` varchar(255) NOT NULL,
  `recurring_details` text DEFAULT NULL,
  `recurring_priority` enum('low','medium','high','critical') DEFAULT 'medium',
  `recurring_category` varchar(100) DEFAULT 'Maintenance',
  `recurring_assigned_to` int(11) DEFAULT NULL,
  `recurring_frequency` enum('daily','weekly','biweekly','monthly','quarterly','semiannual','annual') DEFAULT 'monthly',
  `recurring_day_of_month` int(11) DEFAULT 1,
  `recurring_active` tinyint(1) DEFAULT 1,
  `recurring_last_created` date DEFAULT NULL,
  `recurring_next_due` date DEFAULT NULL,
  `recurring_created_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`recurring_id`),
  KEY `recurring_client_id` (`recurring_client_id`),
  CONSTRAINT `recurring_tickets_ibfk_1` FOREIGN KEY (`recurring_client_id`) REFERENCES `clients` (`client_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `review_requests`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `review_requests` (
  `rr_id` int(11) NOT NULL AUTO_INCREMENT,
  `rr_client_id` int(11) DEFAULT NULL,
  `rr_platform` varchar(100) DEFAULT NULL,
  `rr_token` varchar(64) DEFAULT NULL,
  `rr_clicked` tinyint(1) DEFAULT 0,
  `rr_created_at` datetime DEFAULT current_timestamp(),
  `rr_email` varchar(255) DEFAULT NULL,
  `rr_name` varchar(150) DEFAULT NULL,
  `rr_status` varchar(20) DEFAULT 'sent',
  PRIMARY KEY (`rr_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `risk_acceptances`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `risk_acceptances` (
  `risk_id` int(11) NOT NULL AUTO_INCREMENT,
  `risk_client_id` int(11) NOT NULL,
  `risk_recommendation` varchar(500) NOT NULL,
  `risk_declined_by` varchar(200) DEFAULT NULL,
  `risk_declined_via` varchar(30) DEFAULT 'email',
  `risk_notes` text DEFAULT NULL,
  `risk_staff_user_id` int(11) DEFAULT NULL,
  `risk_created_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`risk_id`),
  KEY `idx_risk_client` (`risk_client_id`),
  CONSTRAINT `risk_acceptances_ibfk_1` FOREIGN KEY (`risk_client_id`) REFERENCES `clients` (`client_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `saved_replies`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `saved_replies` (
  `sr_id` int(11) NOT NULL AUTO_INCREMENT,
  `sr_title` varchar(120) NOT NULL,
  `sr_body` text NOT NULL,
  `sr_queue_id` int(11) DEFAULT NULL,
  `sr_sort` int(11) DEFAULT 0,
  `sr_active` tinyint(1) DEFAULT 1,
  `sr_uses` int(11) DEFAULT 0,
  `sr_created_by` int(11) DEFAULT NULL,
  `sr_created_at` datetime DEFAULT current_timestamp(),
  `sr_updated_at` datetime DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  PRIMARY KEY (`sr_id`),
  KEY `idx_sr_queue` (`sr_queue_id`,`sr_active`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `secure_messages`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `secure_messages` (
  `msg_id` int(11) NOT NULL AUTO_INCREMENT,
  `msg_client_id` int(11) DEFAULT NULL,
  `msg_portal_user_id` int(11) DEFAULT NULL,
  `msg_user_id` int(11) DEFAULT NULL,
  `msg_direction` enum('inbound','outbound') DEFAULT 'inbound',
  `msg_subject` varchar(255) DEFAULT NULL,
  `msg_body` text DEFAULT NULL,
  `msg_read` tinyint(1) DEFAULT 0,
  `msg_archived` tinyint(1) DEFAULT 0,
  `msg_thread_id` int(11) DEFAULT NULL,
  `msg_created_at` datetime DEFAULT current_timestamp(),
  `msg_sealed` tinyint(1) DEFAULT 0,
  `msg_sealed_at` datetime DEFAULT NULL,
  `msg_sealed_by` int(11) DEFAULT NULL,
  `msg_staff_user_id` int(11) DEFAULT NULL,
  `msg_read_at` datetime DEFAULT NULL,
  PRIMARY KEY (`msg_id`),
  KEY `idx_msg_client` (`msg_client_id`),
  KEY `idx_msg_thread` (`msg_thread_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `sender_registrations`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `sender_registrations` (
  `sr_id` int(11) NOT NULL AUTO_INCREMENT,
  `sr_token` char(64) NOT NULL,
  `sr_email` varchar(200) NOT NULL,
  `sr_name` varchar(200) DEFAULT NULL,
  `sr_company` varchar(200) DEFAULT NULL,
  `sr_phone` varchar(50) DEFAULT NULL,
  `sr_title` varchar(100) DEFAULT NULL,
  `sr_ticket_id` int(11) DEFAULT NULL,
  `sr_status` enum('pending','submitted','approved','dismissed') DEFAULT 'pending',
  `sr_client_id` int(11) DEFAULT NULL,
  `sr_contact_id` int(11) DEFAULT NULL,
  `sr_ip` varchar(45) DEFAULT NULL,
  `sr_created_at` datetime DEFAULT current_timestamp(),
  `sr_emailed_at` datetime DEFAULT NULL,
  `sr_submitted_at` datetime DEFAULT NULL,
  `sr_reviewed_by` int(11) DEFAULT NULL,
  `sr_reviewed_at` datetime DEFAULT NULL,
  PRIMARY KEY (`sr_id`),
  UNIQUE KEY `sr_token` (`sr_token`),
  KEY `idx_sr_email` (`sr_email`),
  KEY `idx_sr_ticket` (`sr_ticket_id`),
  KEY `idx_sr_status` (`sr_status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `settings`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `settings` (
  `setting_id` int(11) NOT NULL AUTO_INCREMENT,
  `setting_key` varchar(100) NOT NULL,
  `setting_value` text DEFAULT NULL,
  PRIMARY KEY (`setting_id`),
  UNIQUE KEY `setting_key` (`setting_key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `sla_alerts`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `sla_alerts` (
  `sa_id` int(11) NOT NULL AUTO_INCREMENT,
  `sa_ticket_id` int(11) NOT NULL,
  `sa_kind` varchar(20) NOT NULL,
  `sa_due` datetime DEFAULT NULL,
  `sa_created_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`sa_id`),
  UNIQUE KEY `uq_sa` (`sa_ticket_id`,`sa_kind`,`sa_due`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `sla_policies`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `sla_policies` (
  `sla_id` int(11) NOT NULL AUTO_INCREMENT,
  `sla_name` varchar(200) NOT NULL,
  `sla_description` text DEFAULT NULL,
  `sla_response_critical` int(11) DEFAULT 30,
  `sla_response_high` int(11) DEFAULT 60,
  `sla_response_medium` int(11) DEFAULT 240,
  `sla_response_low` int(11) DEFAULT 480,
  `sla_resolve_critical` int(11) DEFAULT 240,
  `sla_resolve_high` int(11) DEFAULT 480,
  `sla_resolve_medium` int(11) DEFAULT 1440,
  `sla_resolve_low` int(11) DEFAULT 2880,
  `sla_business_hours_only` tinyint(1) DEFAULT 1,
  `sla_business_start` time DEFAULT '08:00:00',
  `sla_business_end` time DEFAULT '17:00:00',
  `sla_is_default` tinyint(1) DEFAULT 0,
  `sla_created_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`sla_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `social_posts`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `social_posts` (
  `sp_id` int(11) NOT NULL AUTO_INCREMENT,
  `sp_content` text DEFAULT NULL,
  `sp_channels` varchar(255) DEFAULT NULL,
  `sp_image_url` varchar(500) DEFAULT NULL,
  `sp_link_url` varchar(500) DEFAULT NULL,
  `sp_status` enum('draft','scheduled','published') DEFAULT 'draft',
  `sp_scheduled_at` datetime DEFAULT NULL,
  `sp_published_at` datetime DEFAULT NULL,
  `sp_created_by` int(11) DEFAULT NULL,
  `sp_created_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`sp_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `staff_offboarding_checklists`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `staff_offboarding_checklists` (
  `checklist_id` int(11) NOT NULL AUTO_INCREMENT,
  `checklist_user_id` int(11) NOT NULL,
  `checklist_items` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL CHECK (json_valid(`checklist_items`)),
  `checklist_completed` tinyint(1) DEFAULT 0,
  `checklist_completed_at` datetime DEFAULT NULL,
  `checklist_created_by` int(11) DEFAULT NULL,
  `checklist_created_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`checklist_id`),
  KEY `idx_staff_checklist_user` (`checklist_user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `stripe_webhook_events`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `stripe_webhook_events` (
  `swe_id` int(11) NOT NULL AUTO_INCREMENT,
  `swe_event_id` varchar(120) NOT NULL,
  `swe_event_type` varchar(100) DEFAULT NULL,
  `swe_created_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`swe_id`),
  UNIQUE KEY `uniq_swe_event_id` (`swe_event_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `surveys`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `surveys` (
  `sv_id` int(11) NOT NULL AUTO_INCREMENT,
  `sv_ticket_id` int(11) DEFAULT NULL,
  `sv_client_id` int(11) DEFAULT NULL,
  `sv_rating` int(11) DEFAULT NULL,
  `sv_feedback` text DEFAULT NULL,
  `sv_token` varchar(64) DEFAULT NULL,
  `sv_completed` tinyint(1) DEFAULT 0,
  `sv_created_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`sv_id`),
  KEY `idx_sv_token` (`sv_token`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `ticket_ai_log`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `ticket_ai_log` (
  `tal_id` int(11) NOT NULL AUTO_INCREMENT,
  `tal_feature` varchar(30) NOT NULL,
  `tal_ticket_id` int(11) DEFAULT NULL,
  `tal_outcome` varchar(40) NOT NULL,
  `tal_created_at` datetime DEFAULT current_timestamp(),
  `tal_ip_hash` char(32) DEFAULT NULL,
  PRIMARY KEY (`tal_id`),
  KEY `idx_tal_feature` (`tal_feature`,`tal_created_at`),
  KEY `idx_tal_ticket` (`tal_ticket_id`),
  KEY `idx_tal_ip` (`tal_ip_hash`,`tal_created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `ticket_approvals`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `ticket_approvals` (
  `approval_id` int(11) NOT NULL AUTO_INCREMENT,
  `approval_ticket_id` int(11) NOT NULL,
  `approval_description` varchar(500) NOT NULL,
  `approval_approved_by` varchar(200) DEFAULT NULL,
  `approval_via` varchar(30) DEFAULT 'email',
  `approval_staff_user_id` int(11) DEFAULT NULL,
  `approval_created_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`approval_id`),
  KEY `idx_approval_ticket` (`approval_ticket_id`),
  CONSTRAINT `ticket_approvals_ibfk_1` FOREIGN KEY (`approval_ticket_id`) REFERENCES `tickets` (`ticket_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `ticket_attachments`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `ticket_attachments` (
  `attachment_id` int(11) NOT NULL AUTO_INCREMENT,
  `attachment_ticket_id` int(11) NOT NULL,
  `attachment_reply_id` int(11) DEFAULT NULL,
  `attachment_filename` varchar(255) NOT NULL,
  `attachment_original_name` varchar(255) NOT NULL,
  `attachment_mime_type` varchar(100) DEFAULT NULL,
  `attachment_size` int(11) DEFAULT 0,
  `attachment_uploaded_by` int(11) DEFAULT NULL,
  `attachment_created_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`attachment_id`),
  KEY `attachment_ticket_id` (`attachment_ticket_id`),
  CONSTRAINT `ticket_attachments_ibfk_1` FOREIGN KEY (`attachment_ticket_id`) REFERENCES `tickets` (`ticket_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `ticket_handoffs`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `ticket_handoffs` (
  `handoff_id` int(11) NOT NULL AUTO_INCREMENT,
  `handoff_ticket_id` int(11) NOT NULL,
  `handoff_from_user_id` int(11) NOT NULL,
  `handoff_to_user_id` int(11) DEFAULT NULL,
  `handoff_note` text NOT NULL,
  `handoff_created_at` datetime DEFAULT current_timestamp(),
  `handoff_acknowledged_at` datetime DEFAULT NULL,
  `handoff_acknowledged_by` int(11) DEFAULT NULL,
  PRIMARY KEY (`handoff_id`),
  KEY `handoff_ticket_id` (`handoff_ticket_id`),
  KEY `handoff_to_user_id` (`handoff_to_user_id`,`handoff_acknowledged_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `ticket_kb_links`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `ticket_kb_links` (
  `tkl_id` int(11) NOT NULL AUTO_INCREMENT,
  `tkl_ticket_id` int(11) NOT NULL,
  `tkl_kb_id` int(11) NOT NULL,
  `tkl_added_by` int(11) DEFAULT NULL,
  `tkl_created_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`tkl_id`),
  UNIQUE KEY `uniq_ticket_kb` (`tkl_ticket_id`,`tkl_kb_id`),
  KEY `tkl_kb_id` (`tkl_kb_id`),
  CONSTRAINT `ticket_kb_links_ibfk_1` FOREIGN KEY (`tkl_ticket_id`) REFERENCES `tickets` (`ticket_id`) ON DELETE CASCADE,
  CONSTRAINT `ticket_kb_links_ibfk_2` FOREIGN KEY (`tkl_kb_id`) REFERENCES `kb_articles` (`kb_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `ticket_mentions`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `ticket_mentions` (
  `tm_id` int(11) NOT NULL AUTO_INCREMENT,
  `tm_ticket_id` int(11) NOT NULL,
  `tm_reply_id` int(11) DEFAULT NULL,
  `tm_user_id` int(11) NOT NULL,
  `tm_mentioned_by` int(11) NOT NULL,
  `tm_seen` tinyint(1) DEFAULT 0,
  `tm_created_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`tm_id`),
  KEY `idx_tm_user` (`tm_user_id`),
  KEY `idx_tm_ticket` (`tm_ticket_id`),
  KEY `idx_tm_seen` (`tm_user_id`,`tm_seen`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `ticket_presence`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `ticket_presence` (
  `tp_id` int(11) NOT NULL AUTO_INCREMENT,
  `tp_ticket_id` int(11) NOT NULL,
  `tp_user_id` int(11) NOT NULL,
  `tp_user_name` varchar(255) DEFAULT NULL,
  `tp_updated_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`tp_id`),
  UNIQUE KEY `uq_ticket_presence` (`tp_ticket_id`,`tp_user_id`),
  KEY `idx_tp_ticket` (`tp_ticket_id`,`tp_updated_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `ticket_queue_members`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `ticket_queue_members` (
  `tqm_queue_id` int(11) NOT NULL,
  `tqm_user_id` int(11) NOT NULL,
  PRIMARY KEY (`tqm_queue_id`,`tqm_user_id`),
  KEY `idx_tqm_user` (`tqm_user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `ticket_queues`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `ticket_queues` (
  `tq_id` int(11) NOT NULL AUTO_INCREMENT,
  `tq_name` varchar(80) NOT NULL,
  `tq_description` varchar(255) DEFAULT NULL,
  `tq_color` varchar(7) DEFAULT '#2c5cc5',
  `tq_sla` tinyint(1) DEFAULT 1,
  `tq_keywords` text DEFAULT NULL,
  `tq_portal_label` varchar(120) DEFAULT NULL,
  `tq_escalate_to` int(11) DEFAULT NULL,
  `tq_assign_mode` varchar(20) DEFAULT 'none',
  `tq_assign_user` int(11) DEFAULT NULL,
  `tq_notify` tinyint(1) DEFAULT 1,
  `tq_email` varchar(20) DEFAULT 'all_techs',
  `tq_is_default` tinyint(1) DEFAULT 0,
  `tq_active` tinyint(1) DEFAULT 1,
  `tq_sort` int(11) DEFAULT 0,
  `tq_created_at` datetime DEFAULT current_timestamp(),
  `tq_gchat_webhook` text DEFAULT NULL,
  `tq_gchat_events` varchar(60) DEFAULT 'new,escalated,sla',
  PRIMARY KEY (`tq_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `ticket_replies`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `ticket_replies` (
  `reply_id` int(11) NOT NULL AUTO_INCREMENT,
  `reply_ticket_id` int(11) NOT NULL,
  `reply_user_id` int(11) DEFAULT NULL,
  `reply_contact_id` int(11) DEFAULT NULL,
  `reply_type` enum('reply','note','work','resolution') DEFAULT 'reply',
  `reply_from` varchar(50) DEFAULT 'staff',
  `reply_body` text NOT NULL,
  `reply_time_spent` decimal(8,2) DEFAULT 0.00,
  `reply_work_type` varchar(50) DEFAULT '',
  `reply_billable` tinyint(1) DEFAULT 1,
  `reply_created_at` datetime DEFAULT current_timestamp(),
  `reply_invoice_id` int(11) DEFAULT NULL,
  `reply_writeoff_reason` varchar(255) DEFAULT NULL,
  `reply_writeoff_by` int(11) DEFAULT NULL,
  `reply_writeoff_at` datetime DEFAULT NULL,
  PRIMARY KEY (`reply_id`),
  KEY `reply_ticket_id` (`reply_ticket_id`),
  KEY `reply_user_id` (`reply_user_id`),
  CONSTRAINT `ticket_replies_ibfk_1` FOREIGN KEY (`reply_ticket_id`) REFERENCES `tickets` (`ticket_id`) ON DELETE CASCADE,
  CONSTRAINT `ticket_replies_ibfk_2` FOREIGN KEY (`reply_user_id`) REFERENCES `users` (`user_id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `ticket_signoffs`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `ticket_signoffs` (
  `so_id` int(11) NOT NULL AUTO_INCREMENT,
  `so_ticket_id` int(11) NOT NULL,
  `so_type` enum('completion','dropoff') NOT NULL,
  `so_signer_name` varchar(200) DEFAULT NULL,
  `so_signer_title` varchar(100) DEFAULT NULL,
  `so_signer_email` varchar(200) DEFAULT NULL,
  `so_signature` mediumtext DEFAULT NULL,
  `so_summary` text DEFAULT NULL,
  `so_items` text DEFAULT NULL,
  `so_hours` decimal(8,2) DEFAULT NULL,
  `so_rate` decimal(10,2) DEFAULT NULL,
  `so_parts_desc` varchar(255) DEFAULT NULL,
  `so_parts_amount` decimal(10,2) DEFAULT NULL,
  `so_tax_rate` decimal(5,2) DEFAULT NULL,
  `so_total` decimal(10,2) DEFAULT NULL,
  `so_statement` text DEFAULT NULL,
  `so_hash` char(64) DEFAULT NULL,
  `so_overridden` tinyint(1) DEFAULT 0,
  `so_override_reason` text DEFAULT NULL,
  `so_user_id` int(11) DEFAULT NULL,
  `so_ip` varchar(45) DEFAULT NULL,
  `so_via` varchar(20) DEFAULT 'web',
  `so_created_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`so_id`),
  KEY `idx_so_ticket` (`so_ticket_id`,`so_type`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `ticket_tasks`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `ticket_tasks` (
  `task_id` int(11) NOT NULL AUTO_INCREMENT,
  `task_ticket_id` int(11) NOT NULL,
  `task_title` varchar(255) NOT NULL,
  `task_completed` tinyint(1) DEFAULT 0,
  `task_completed_by` int(11) DEFAULT NULL,
  `task_completed_at` datetime DEFAULT NULL,
  `task_sort_order` int(11) DEFAULT 0,
  `task_created_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`task_id`),
  KEY `task_ticket_id` (`task_ticket_id`),
  CONSTRAINT `ticket_tasks_ibfk_1` FOREIGN KEY (`task_ticket_id`) REFERENCES `tickets` (`ticket_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `ticket_templates`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `ticket_templates` (
  `tt_id` int(11) NOT NULL AUTO_INCREMENT,
  `tt_name` varchar(200) DEFAULT NULL,
  `tt_subject` varchar(255) DEFAULT NULL,
  `tt_details` text DEFAULT NULL,
  `tt_priority` varchar(20) DEFAULT 'medium',
  `tt_category` varchar(100) DEFAULT NULL,
  `tt_created_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`tt_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `ticket_time_entries`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `ticket_time_entries` (
  `tte_id` int(11) NOT NULL AUTO_INCREMENT,
  `tte_ticket_id` int(11) NOT NULL,
  `tte_user_id` int(11) NOT NULL,
  `tte_date` date NOT NULL,
  `tte_hours` decimal(6,2) NOT NULL,
  `tte_work_type` varchar(100) DEFAULT 'Remote Support',
  `tte_description` text DEFAULT NULL,
  `tte_billable` tinyint(1) DEFAULT 1,
  `tte_rate` decimal(8,2) DEFAULT 0.00,
  `tte_invoiced` tinyint(1) DEFAULT 0,
  `tte_invoice_id` int(11) DEFAULT NULL,
  `tte_created_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`tte_id`),
  KEY `idx_tte_ticket` (`tte_ticket_id`),
  KEY `idx_tte_user` (`tte_user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `tickets`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `tickets` (
  `ticket_id` int(11) NOT NULL AUTO_INCREMENT,
  `ticket_number` varchar(20) NOT NULL,
  `ticket_client_id` int(11) DEFAULT NULL,
  `ticket_contact_id` int(11) DEFAULT NULL,
  `ticket_contact_name` varchar(150) DEFAULT NULL,
  `ticket_contact_email` varchar(190) DEFAULT NULL,
  `ticket_assigned_to` int(11) DEFAULT NULL,
  `ticket_subject` varchar(255) NOT NULL,
  `ticket_details` text DEFAULT NULL,
  `ticket_priority` enum('low','medium','high','critical') DEFAULT 'low',
  `ticket_status` varchar(30) DEFAULT 'new',
  `ticket_category` varchar(100) DEFAULT NULL,
  `ticket_cc` varchar(500) DEFAULT NULL,
  `ticket_source` varchar(50) DEFAULT 'manual',
  `ticket_due_date` date DEFAULT NULL,
  `ticket_billable` tinyint(1) DEFAULT 1,
  `ticket_hours` decimal(8,2) DEFAULT 0.00,
  `ticket_timer_start` datetime DEFAULT NULL,
  `ticket_timer_user_id` int(11) DEFAULT NULL,
  `ticket_closed_at` datetime DEFAULT NULL,
  `ticket_created_at` datetime DEFAULT current_timestamp(),
  `ticket_updated_at` datetime DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  `ticket_resolution` text DEFAULT NULL,
  `ticket_root_cause` varchar(255) DEFAULT NULL,
  `ticket_impact` enum('single_user','department','office','all_users','critical_system') DEFAULT 'single_user',
  `ticket_satisfaction` int(11) DEFAULT NULL,
  `ticket_first_response_at` datetime DEFAULT NULL,
  `ticket_escalated` tinyint(1) DEFAULT 0,
  `ticket_escalated_to` int(11) DEFAULT NULL,
  `ticket_escalated_at` datetime DEFAULT NULL,
  `ticket_device` varchar(200) DEFAULT NULL,
  `ticket_location` varchar(200) DEFAULT NULL,
  `ticket_tags` varchar(500) DEFAULT NULL,
  `ticket_merged_into` int(11) DEFAULT NULL,
  `ticket_sla_response_due` datetime DEFAULT NULL,
  `ticket_sla_resolve_due` datetime DEFAULT NULL,
  `ticket_sla_breached` tinyint(1) DEFAULT 0,
  `ticket_watchers` text DEFAULT NULL,
  `ticket_time_estimate` decimal(6,2) DEFAULT 0.00,
  `ticket_csat_rating` tinyint(4) DEFAULT NULL,
  `ticket_csat_comment` text DEFAULT NULL,
  `ticket_csat_token` varchar(64) DEFAULT NULL,
  `ticket_csat_sent_at` datetime DEFAULT NULL,
  `ticket_csat_responded_at` datetime DEFAULT NULL,
  `ticket_sla_resolution_due` datetime DEFAULT NULL,
  `ticket_ai_category` varchar(100) DEFAULT NULL,
  `ticket_ai_priority` varchar(20) DEFAULT NULL,
  `ticket_ai_reason` varchar(500) DEFAULT NULL,
  `ticket_converted_project_id` int(11) DEFAULT NULL,
  `ticket_queue_id` int(11) DEFAULT NULL,
  `ticket_queue_via` varchar(20) DEFAULT NULL,
  `ticket_queue_reason` varchar(255) DEFAULT NULL,
  `ticket_sla_basis` varchar(120) DEFAULT NULL,
  `ticket_sla_paused_at` datetime DEFAULT NULL,
  `ticket_sla_paused_min` int(11) DEFAULT 0,
  `ticket_waiting_since` datetime DEFAULT NULL,
  `ticket_waiting_followup_count` int(11) DEFAULT 0,
  `ticket_waiting_last_followup_at` datetime DEFAULT NULL,
  `ticket_resolved_at` datetime DEFAULT NULL,
  `ticket_resolved_by` int(11) DEFAULT NULL,
  `ticket_snoozed_until` datetime DEFAULT NULL,
  `ticket_snooze_prev_status` varchar(40) DEFAULT NULL,
  PRIMARY KEY (`ticket_id`),
  UNIQUE KEY `ticket_number` (`ticket_number`),
  KEY `ticket_client_id` (`ticket_client_id`),
  KEY `ticket_contact_id` (`ticket_contact_id`),
  KEY `ticket_assigned_to` (`ticket_assigned_to`),
  KEY `idx_ticket_queue` (`ticket_queue_id`,`ticket_status`),
  KEY `idx_ticket_sla` (`ticket_status`,`ticket_sla_response_due`,`ticket_sla_resolve_due`),
  KEY `idx_ticket_snoozed` (`ticket_snoozed_until`),
  CONSTRAINT `tickets_ibfk_1` FOREIGN KEY (`ticket_client_id`) REFERENCES `clients` (`client_id`) ON DELETE CASCADE,
  CONSTRAINT `tickets_ibfk_2` FOREIGN KEY (`ticket_contact_id`) REFERENCES `contacts` (`contact_id`) ON DELETE SET NULL,
  CONSTRAINT `tickets_ibfk_3` FOREIGN KEY (`ticket_assigned_to`) REFERENCES `users` (`user_id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `training_certificates`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `training_certificates` (
  `cert_id` int(11) NOT NULL AUTO_INCREMENT,
  `cert_learner_id` int(11) NOT NULL,
  `cert_course_key` varchar(50) NOT NULL,
  `cert_number` varchar(40) NOT NULL,
  `cert_score` int(11) NOT NULL DEFAULT 0,
  `cert_issued_at` datetime DEFAULT current_timestamp(),
  `cert_expires_at` datetime DEFAULT NULL,
  PRIMARY KEY (`cert_id`),
  UNIQUE KEY `cert_number` (`cert_number`),
  KEY `idx_cert_learner` (`cert_learner_id`),
  KEY `idx_cert_course` (`cert_course_key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `training_cloud_cache`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `training_cloud_cache` (
  `cache_key` varchar(190) NOT NULL,
  `cache_json` mediumtext DEFAULT NULL,
  `fetched_at` datetime NOT NULL,
  PRIMARY KEY (`cache_key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `training_cloud_events`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `training_cloud_events` (
  `tce_id` int(11) NOT NULL AUTO_INCREMENT,
  `tce_event_id` varchar(64) NOT NULL,
  `tce_event` varchar(40) NOT NULL,
  `tce_payload` mediumtext DEFAULT NULL,
  `tce_status` varchar(20) NOT NULL DEFAULT 'received',
  `tce_error` varchar(255) DEFAULT NULL,
  `tce_received_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`tce_id`),
  UNIQUE KEY `tce_event_id` (`tce_event_id`),
  KEY `idx_tce_event` (`tce_event`,`tce_received_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `training_courses`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `training_courses` (
  `tc_id` int(11) NOT NULL AUTO_INCREMENT,
  `tc_key` varchar(50) NOT NULL,
  `tc_name` varchar(150) NOT NULL,
  `tc_category` enum('core','hipaa','legal','nonprofit','refresher','onboarding','certification','internal') NOT NULL DEFAULT 'core',
  `tc_description` text DEFAULT NULL,
  `tc_icon` varchar(8) DEFAULT NULL,
  `tc_color` varchar(20) DEFAULT NULL,
  `tc_minutes` int(11) NOT NULL DEFAULT 15,
  `tc_recommend_for` varchar(255) DEFAULT NULL,
  `tc_pass_score` int(11) NOT NULL DEFAULT 80,
  `tc_active` tinyint(1) NOT NULL DEFAULT 1,
  `tc_created_at` datetime DEFAULT current_timestamp(),
  `tc_updated_at` datetime DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  `tc_final_quiz` mediumtext DEFAULT NULL,
  `tc_final_required` tinyint(1) NOT NULL DEFAULT 1,
  `tc_final_pass` int(11) NOT NULL DEFAULT 80,
  `tc_final_count` int(11) NOT NULL DEFAULT 10,
  `tc_exam_questions` int(11) DEFAULT NULL,
  `tc_exam_minutes` int(11) DEFAULT NULL,
  PRIMARY KEY (`tc_id`),
  UNIQUE KEY `tc_key` (`tc_key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `training_enrollments`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `training_enrollments` (
  `te_id` int(11) NOT NULL AUTO_INCREMENT,
  `te_client_id` int(11) NOT NULL,
  `te_access_code` varchar(20) NOT NULL,
  `te_courses` varchar(255) NOT NULL,
  `te_due_date` date DEFAULT NULL,
  `te_roster_only` tinyint(1) NOT NULL DEFAULT 0,
  `te_status` enum('active','closed') NOT NULL DEFAULT 'active',
  `te_renew_months` int(11) NOT NULL DEFAULT 12,
  `te_created_by` int(11) DEFAULT NULL,
  `te_created_at` datetime DEFAULT current_timestamp(),
  `te_updated_at` datetime DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  `te_cloud_id` int(11) DEFAULT NULL,
  PRIMARY KEY (`te_id`),
  UNIQUE KEY `te_access_code` (`te_access_code`),
  KEY `idx_te_client` (`te_client_id`),
  KEY `idx_te_status` (`te_status`),
  KEY `idx_te_cloud` (`te_cloud_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `training_learners`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `training_learners` (
  `tr_id` int(11) NOT NULL AUTO_INCREMENT,
  `tr_enrollment_id` int(11) NOT NULL,
  `tr_name` varchar(150) NOT NULL,
  `tr_email` varchar(255) NOT NULL,
  `tr_token` varchar(64) DEFAULT NULL,
  `tr_last_active` datetime DEFAULT NULL,
  `tr_reminders` int(11) NOT NULL DEFAULT 0,
  `tr_reminded_at` datetime DEFAULT NULL,
  `tr_created_at` datetime DEFAULT current_timestamp(),
  `tr_updated_at` datetime DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  `tr_cloud_id` int(11) DEFAULT NULL,
  PRIMARY KEY (`tr_id`),
  UNIQUE KEY `uq_tr_enrollment_email` (`tr_enrollment_id`,`tr_email`),
  KEY `idx_tr_token` (`tr_token`),
  KEY `idx_tr_cloud` (`tr_cloud_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `training_lessons`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `training_lessons` (
  `tl_id` int(11) NOT NULL AUTO_INCREMENT,
  `tl_course_id` int(11) NOT NULL,
  `tl_sort` int(11) NOT NULL DEFAULT 0,
  `tl_title` varchar(200) NOT NULL,
  `tl_icon` varchar(8) DEFAULT NULL,
  `tl_summary` varchar(255) DEFAULT NULL,
  `tl_body` mediumtext DEFAULT NULL,
  `tl_quiz` mediumtext DEFAULT NULL,
  `tl_video_url` varchar(500) DEFAULT NULL,
  `tl_video_kind` enum('none','youtube','vimeo','mp4') NOT NULL DEFAULT 'none',
  `tl_require_watch` tinyint(1) NOT NULL DEFAULT 1,
  `tl_video_minutes` decimal(5,1) DEFAULT NULL,
  PRIMARY KEY (`tl_id`),
  KEY `idx_tl_course` (`tl_course_id`,`tl_sort`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `training_progress`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `training_progress` (
  `tp_id` int(11) NOT NULL AUTO_INCREMENT,
  `tp_learner_id` int(11) NOT NULL,
  `tp_course_key` varchar(50) NOT NULL,
  `tp_lesson_id` int(11) NOT NULL,
  `tp_score` int(11) NOT NULL DEFAULT 0,
  `tp_passed` tinyint(1) NOT NULL DEFAULT 0,
  `tp_attempts` int(11) NOT NULL DEFAULT 0,
  `tp_completed_at` datetime DEFAULT NULL,
  `tp_kind` enum('lesson','final') NOT NULL DEFAULT 'lesson',
  `tp_answers` mediumtext DEFAULT NULL,
  `tp_video_watched_at` datetime DEFAULT NULL,
  PRIMARY KEY (`tp_id`),
  UNIQUE KEY `uq_tp_learner_lesson_kind` (`tp_learner_id`,`tp_lesson_id`,`tp_kind`),
  KEY `idx_tp_course` (`tp_learner_id`,`tp_course_key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `update_history`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `update_history` (
  `uh_id` int(11) NOT NULL AUTO_INCREMENT,
  `uh_from` varchar(40) DEFAULT NULL,
  `uh_to` varchar(40) DEFAULT NULL,
  `uh_mode` varchar(20) NOT NULL DEFAULT 'github',
  `uh_user_id` int(11) DEFAULT NULL,
  `uh_started_at` datetime DEFAULT NULL,
  `uh_finished_at` datetime DEFAULT NULL,
  `uh_duration_s` int(11) DEFAULT NULL,
  `uh_status` enum('success','warning','failed','rolled_back') NOT NULL DEFAULT 'success',
  `uh_backup_db` varchar(255) DEFAULT NULL,
  `uh_backup_files` varchar(255) DEFAULT NULL,
  `uh_log` mediumtext DEFAULT NULL,
  PRIMARY KEY (`uh_id`),
  KEY `uh_started_at` (`uh_started_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `user_oauth_tokens`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `user_oauth_tokens` (
  `uot_id` int(11) NOT NULL AUTO_INCREMENT,
  `uot_user_id` int(11) NOT NULL,
  `uot_provider` varchar(50) NOT NULL,
  `uot_access_token` text DEFAULT NULL,
  `uot_refresh_token` text DEFAULT NULL,
  `uot_token_expires` datetime DEFAULT NULL,
  `uot_email` varchar(200) DEFAULT NULL,
  `uot_scope` text DEFAULT NULL,
  `uot_created_at` datetime DEFAULT current_timestamp(),
  `uot_updated_at` datetime DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  PRIMARY KEY (`uot_id`),
  KEY `idx_uot_user_provider` (`uot_user_id`,`uot_provider`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `user_recovery_codes`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `user_recovery_codes` (
  `rc_id` int(11) NOT NULL AUTO_INCREMENT,
  `rc_user_id` int(11) NOT NULL,
  `rc_hash` char(64) NOT NULL,
  `rc_used_at` datetime DEFAULT NULL,
  `rc_created_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`rc_id`),
  KEY `idx_rc_user` (`rc_user_id`,`rc_used_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `users`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `users` (
  `user_id` int(11) NOT NULL AUTO_INCREMENT,
  `user_name` varchar(200) NOT NULL,
  `user_email` varchar(200) NOT NULL,
  `user_password` varchar(255) NOT NULL,
  `user_role` enum('admin','manager','tech','viewer') DEFAULT 'tech',
  `user_avatar` varchar(255) DEFAULT NULL,
  `user_phone` varchar(50) DEFAULT NULL,
  `user_title` varchar(100) DEFAULT NULL,
  `user_department` varchar(100) DEFAULT NULL,
  `user_extension` varchar(20) DEFAULT NULL,
  `user_timezone` varchar(50) DEFAULT 'America/Chicago',
  `user_hourly_rate` decimal(10,2) DEFAULT 0.00,
  `user_color` varchar(20) DEFAULT '#3b82f6',
  `user_signature` text DEFAULT NULL,
  `user_notes` text DEFAULT NULL,
  `user_last_login` datetime DEFAULT NULL,
  `user_force_password_change` tinyint(1) DEFAULT 0,
  `user_2fa_secret` varchar(64) DEFAULT NULL,
  `user_2fa_enabled` tinyint(1) DEFAULT 0,
  `user_sso_provider` varchar(20) DEFAULT NULL,
  `user_sso_linked_at` datetime DEFAULT NULL,
  `user_sso_password_ok` tinyint(1) NOT NULL DEFAULT 0,
  `user_created_at` datetime DEFAULT current_timestamp(),
  `user_updated_at` datetime DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  `user_archived` tinyint(1) DEFAULT 0,
  `user_totp_secret` text DEFAULT NULL,
  `user_totp_last_counter` bigint(20) DEFAULT NULL,
  `user_totp_enrolled_at` datetime DEFAULT NULL,
  `user_2fa_backup_codes` text DEFAULT NULL,
  `user_mfa_required` tinyint(1) DEFAULT NULL,
  `user_session_version` int(11) NOT NULL DEFAULT 0,
  `user_default_priority` varchar(20) DEFAULT 'medium',
  `user_dashboard_page` varchar(50) DEFAULT 'dashboard',
  `user_work_start` time DEFAULT '08:00:00',
  `user_work_end` time DEFAULT '16:00:00',
  `user_work_days` varchar(20) DEFAULT '1,2,3,4,5',
  `user_auto_assign` tinyint(1) DEFAULT 0,
  `user_notify_new_ticket` tinyint(1) DEFAULT 1,
  `user_notify_assigned` tinyint(1) DEFAULT 1,
  `user_notify_sla` tinyint(1) DEFAULT 1,
  `user_notify_client_reply` tinyint(1) DEFAULT 1,
  `user_notify_invoice` tinyint(1) DEFAULT 0,
  `user_notify_lead` tinyint(1) DEFAULT 0,
  `user_permissions` text DEFAULT NULL,
  `user_hr_access` tinyint(1) DEFAULT 0,
  PRIMARY KEY (`user_id`),
  UNIQUE KEY `user_email` (`user_email`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `vendor_senders`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `vendor_senders` (
  `vs_id` int(11) NOT NULL AUTO_INCREMENT,
  `vs_label` varchar(150) DEFAULT NULL,
  `vs_match` varchar(190) NOT NULL,
  `vs_match_type` enum('email','domain') DEFAULT 'email',
  `vs_client_id` int(11) DEFAULT NULL,
  `vs_priority` enum('low','medium','high','critical') DEFAULT 'high',
  `vs_category` varchar(100) DEFAULT NULL,
  `vs_suppress_autoreply` tinyint(1) DEFAULT 1,
  `vs_bypass_dedup` tinyint(1) DEFAULT 1,
  `vs_active` tinyint(1) DEFAULT 1,
  `vs_created_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`vs_id`),
  KEY `idx_vs_match` (`vs_match`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `vendors`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `vendors` (
  `vendor_id` int(11) NOT NULL AUTO_INCREMENT,
  `vendor_name` varchar(200) NOT NULL,
  `vendor_contact_name` varchar(200) DEFAULT NULL,
  `vendor_email` varchar(200) DEFAULT NULL,
  `vendor_phone` varchar(50) DEFAULT NULL,
  `vendor_website` varchar(255) DEFAULT NULL,
  `vendor_account_number` varchar(100) DEFAULT NULL,
  `vendor_notes` text DEFAULT NULL,
  `vendor_created_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`vendor_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `warranties`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `warranties` (
  `warranty_id` int(11) NOT NULL AUTO_INCREMENT,
  `warranty_client_id` int(11) NOT NULL,
  `warranty_asset_id` int(11) DEFAULT NULL,
  `warranty_type` enum('hardware','software','license','subscription','domain','ssl') DEFAULT 'hardware',
  `warranty_name` varchar(255) NOT NULL,
  `warranty_vendor` varchar(200) DEFAULT NULL,
  `warranty_serial` varchar(200) DEFAULT NULL,
  `warranty_start_date` date DEFAULT NULL,
  `warranty_end_date` date NOT NULL,
  `warranty_cost` decimal(10,2) DEFAULT 0.00,
  `warranty_recurring` tinyint(1) DEFAULT 0,
  `warranty_notes` text DEFAULT NULL,
  `warranty_alert_sent` tinyint(1) DEFAULT 0,
  `warranty_created_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`warranty_id`),
  KEY `warranty_client_id` (`warranty_client_id`),
  CONSTRAINT `warranties_ibfk_1` FOREIGN KEY (`warranty_client_id`) REFERENCES `clients` (`client_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `webhooks`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `webhooks` (
  `wh_id` int(11) NOT NULL AUTO_INCREMENT,
  `wh_url` varchar(500) NOT NULL,
  `wh_events` varchar(500) NOT NULL,
  `wh_secret` varchar(100) DEFAULT NULL,
  `wh_active` tinyint(1) DEFAULT 1,
  `wh_last_triggered` datetime DEFAULT NULL,
  `wh_last_status` int(11) DEFAULT NULL,
  `wh_fail_count` int(11) DEFAULT 0,
  `wh_created_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`wh_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `workflow_log`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `workflow_log` (
  `wl_id` int(11) NOT NULL AUTO_INCREMENT,
  `wl_rule_id` int(11) NOT NULL,
  `wl_ticket_id` int(11) DEFAULT NULL,
  `wl_action_taken` varchar(200) DEFAULT NULL,
  `wl_details` text DEFAULT NULL,
  `wl_created_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`wl_id`),
  KEY `idx_wl_rule` (`wl_rule_id`),
  KEY `idx_wl_ticket` (`wl_ticket_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `workflow_rules`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `workflow_rules` (
  `wr_id` int(11) NOT NULL AUTO_INCREMENT,
  `wr_name` varchar(200) NOT NULL,
  `wr_description` text DEFAULT NULL,
  `wr_trigger` enum('ticket_created','ticket_updated','ticket_idle','ticket_sla_warn','ticket_sla_breach','ticket_closed','time_based') NOT NULL DEFAULT 'ticket_created',
  `wr_conditions` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL CHECK (json_valid(`wr_conditions`)),
  `wr_actions` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL CHECK (json_valid(`wr_actions`)),
  `wr_priority` int(11) DEFAULT 0,
  `wr_enabled` tinyint(1) DEFAULT 1,
  `wr_run_count` int(11) DEFAULT 0,
  `wr_last_run` datetime DEFAULT NULL,
  `wr_created_by` int(11) DEFAULT NULL,
  `wr_created_at` datetime DEFAULT current_timestamp(),
  `wr_updated_at` datetime DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  PRIMARY KEY (`wr_id`),
  KEY `idx_wr_trigger` (`wr_trigger`),
  KEY `idx_wr_enabled` (`wr_enabled`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

