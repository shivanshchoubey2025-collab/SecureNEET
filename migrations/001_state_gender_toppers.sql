-- =====================================================================
-- Migration 001: Add State Topper and Gender Topper Fields
-- Reason:
--   Supports State Topper (#11) and Gender Topper (#12) leaderboard features.
--   Adds `state` and `gender` columns to `users`, and `state_rank` /
--   `gender_rank` columns to `examination_attempts`.
--
-- Backup Recommendation:
--   mysqldump -u root -p secureneet users examination_attempts > backup_pre_migration_001.sql
--
-- Compatibility:
--   All additions use NULL defaults. Existing rows are preserved unharmed.
--   Non-binary & undisclosed values supported.
--
-- Rollback Strategy:
--   ALTER TABLE `users` DROP COLUMN `state`, DROP COLUMN `gender`;
--   ALTER TABLE `examination_attempts` DROP COLUMN `state_rank`, DROP COLUMN `gender_rank`;
-- =====================================================================

-- 1. Modify users table if columns do not exist
ALTER TABLE `users`
    ADD COLUMN IF NOT EXISTS `state` VARCHAR(100) DEFAULT NULL AFTER `role`,
    ADD COLUMN IF NOT EXISTS `gender` VARCHAR(50) DEFAULT NULL AFTER `state`,
    ADD INDEX IF NOT EXISTS `idx_users_state` (`state`),
    ADD INDEX IF NOT EXISTS `idx_users_gender` (`gender`);

-- 2. Modify examination_attempts table if columns do not exist
ALTER TABLE `examination_attempts`
    ADD COLUMN IF NOT EXISTS `state_rank` INT DEFAULT NULL AFTER `overall_rank`,
    ADD COLUMN IF NOT EXISTS `gender_rank` INT DEFAULT NULL AFTER `state_rank`;
