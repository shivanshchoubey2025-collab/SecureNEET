-- =====================================================================
-- SecureNEET — Official MySQL Database Schema
-- Production Relational Schema for NEET Examination Management Portal
-- =====================================================================

CREATE DATABASE IF NOT EXISTS `secureneet` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE `secureneet`;

SET FOREIGN_KEY_CHECKS = 0;

-- 1. USERS TABLE (Students, Question Managers, Administrators)
DROP TABLE IF EXISTS `users`;
CREATE TABLE `users` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `full_name` VARCHAR(150) NOT NULL,
    `email` VARCHAR(191) NOT NULL UNIQUE,
    `password_hash` VARCHAR(255) NOT NULL,
    `role` ENUM('admin', 'question_manager', 'student') NOT NULL DEFAULT 'student',
    `state` VARCHAR(100) DEFAULT NULL,
    `gender` VARCHAR(50) DEFAULT NULL,
    `registration_number` VARCHAR(50) UNIQUE DEFAULT NULL,
    `is_active` TINYINT(1) NOT NULL DEFAULT 1,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX `idx_users_role` (`role`),
    INDEX `idx_users_state` (`state`),
    INDEX `idx_users_gender` (`gender`),
    INDEX `idx_users_active` (`is_active`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 2. EXAMINATIONS TABLE
DROP TABLE IF EXISTS `examinations`;
CREATE TABLE `examinations` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `title` VARCHAR(200) NOT NULL,
    `description` TEXT DEFAULT NULL,
    `code` VARCHAR(50) NOT NULL UNIQUE,
    `duration_minutes` INT NOT NULL DEFAULT 180,
    `total_marks` INT NOT NULL DEFAULT 720,
    `passing_marks` INT NOT NULL DEFAULT 360,
    `positive_marks` DECIMAL(5,2) NOT NULL DEFAULT 4.00,
    `negative_marks` DECIMAL(5,2) NOT NULL DEFAULT 1.00,
    `start_time` DATETIME DEFAULT NULL,
    `end_time` DATETIME DEFAULT NULL,
    `is_published` TINYINT(1) NOT NULL DEFAULT 0,
    `created_by` INT DEFAULT NULL,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX `idx_exams_published` (`is_published`),
    INDEX `idx_exams_code` (`code`),
    CONSTRAINT `fk_exams_created_by` FOREIGN KEY (`created_by`) REFERENCES `users` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 3. QUESTIONS TABLE
DROP TABLE IF EXISTS `questions`;
CREATE TABLE `questions` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `examination_id` INT NOT NULL,
    `subject` ENUM('Physics', 'Chemistry', 'Botany', 'Zoology') NOT NULL,
    `topic` VARCHAR(150) DEFAULT NULL,
    `question_text` TEXT NOT NULL,
    `option_a` TEXT NOT NULL,
    `option_b` TEXT NOT NULL,
    `option_c` TEXT NOT NULL,
    `option_d` TEXT NOT NULL,
    `correct_option` ENUM('A', 'B', 'C', 'D') NOT NULL,
    `marks` DECIMAL(5,2) NOT NULL DEFAULT 4.00,
    `negative_marks` DECIMAL(5,2) NOT NULL DEFAULT 1.00,
    `explanation` TEXT DEFAULT NULL,
    `created_by` INT DEFAULT NULL,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX `idx_questions_exam` (`examination_id`),
    INDEX `idx_questions_subject` (`subject`),
    CONSTRAINT `fk_questions_exam` FOREIGN KEY (`examination_id`) REFERENCES `examinations` (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_questions_created_by` FOREIGN KEY (`created_by`) REFERENCES `users` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 4. EXAMINATION ATTEMPTS TABLE
DROP TABLE IF EXISTS `examination_attempts`;
CREATE TABLE `examination_attempts` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `examination_id` INT NOT NULL,
    `student_id` INT NOT NULL,
    `start_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `deadline_time` DATETIME NOT NULL,
    `submitted_at` DATETIME DEFAULT NULL,
    `status` ENUM('in_progress', 'submitted', 'evaluated', 'expired') NOT NULL DEFAULT 'in_progress',
    `total_score` DECIMAL(6,2) NOT NULL DEFAULT 0.00,
    `questions_answered` INT NOT NULL DEFAULT 0,
    `correct_answers` INT NOT NULL DEFAULT 0,
    `incorrect_answers` INT NOT NULL DEFAULT 0,
    `unanswered_count` INT NOT NULL DEFAULT 0,
    `percentage` DECIMAL(5,2) NOT NULL DEFAULT 0.00,
    `time_taken_seconds` INT NOT NULL DEFAULT 0,
    `overall_rank` INT DEFAULT NULL,
    `state_rank` INT DEFAULT NULL,
    `gender_rank` INT DEFAULT NULL,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX `idx_attempts_exam` (`examination_id`),
    INDEX `idx_attempts_student` (`student_id`),
    INDEX `idx_attempts_status` (`status`),
    INDEX `idx_attempts_score` (`total_score`),
    CONSTRAINT `fk_attempts_exam` FOREIGN KEY (`examination_id`) REFERENCES `examinations` (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_attempts_student` FOREIGN KEY (`student_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 5. STUDENT ANSWERS TABLE
DROP TABLE IF EXISTS `student_answers`;
CREATE TABLE `student_answers` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `attempt_id` INT NOT NULL,
    `question_id` INT NOT NULL,
    `selected_option` ENUM('A', 'B', 'C', 'D') DEFAULT NULL,
    `is_marked_for_review` TINYINT(1) NOT NULL DEFAULT 0,
    `is_correct` TINYINT(1) DEFAULT NULL,
    `marks_awarded` DECIMAL(5,2) NOT NULL DEFAULT 0.00,
    `answered_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY `unique_attempt_question` (`attempt_id`, `question_id`),
    INDEX `idx_answers_attempt` (`attempt_id`),
    INDEX `idx_answers_question` (`question_id`),
    CONSTRAINT `fk_answers_attempt` FOREIGN KEY (`attempt_id`) REFERENCES `examination_attempts` (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_answers_question` FOREIGN KEY (`question_id`) REFERENCES `questions` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 6. AUDIT LOGS TABLE
DROP TABLE IF EXISTS `audit_logs`;
CREATE TABLE `audit_logs` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `user_id` INT DEFAULT NULL,
    `action` VARCHAR(100) NOT NULL,
    `target_type` VARCHAR(50) DEFAULT NULL,
    `target_id` INT DEFAULT NULL,
    `ip_address` VARCHAR(45) DEFAULT NULL,
    `details` TEXT DEFAULT NULL,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX `idx_audit_user` (`user_id`),
    INDEX `idx_audit_action` (`action`),
    CONSTRAINT `fk_audit_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

SET FOREIGN_KEY_CHECKS = 1;
