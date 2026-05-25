CREATE DATABASE IF NOT EXISTS stable_hire
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE stable_hire;

CREATE TABLE IF NOT EXISTS users (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  username VARCHAR(128) NOT NULL UNIQUE,
  password_hash VARCHAR(255) NOT NULL,
  role ENUM('worker', 'employer', 'admin') NOT NULL,
  linked_entity_id VARCHAR(255),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS workers (
  id VARCHAR(255) PRIMARY KEY,
  name VARCHAR(255) NOT NULL,
  entity_type ENUM('human_student', 'ai_worker') NOT NULL DEFAULT 'human_student',
  capability_signal DOUBLE NOT NULL,
  skills DOUBLE NOT NULL,
  internship_history DOUBLE NOT NULL,
  personality DOUBLE NOT NULL,
  soft_skills DOUBLE NOT NULL,
  trust_score DOUBLE DEFAULT 0.75,
  verification_status ENUM('unverified', 'pending', 'verified', 'flagged') DEFAULT 'unverified'
);

CREATE TABLE IF NOT EXISTS employers (
  id VARCHAR(255) PRIMARY KEY,
  name VARCHAR(255) NOT NULL,
  entity_type ENUM('human_company', 'ai_employer') NOT NULL DEFAULT 'human_company',
  salary_reward DOUBLE NOT NULL,
  location_remote DOUBLE NOT NULL,
  growth_opportunity DOUBLE NOT NULL,
  reputation DOUBLE NOT NULL,
  skill_fit_meaning DOUBLE NOT NULL,
  trust_score DOUBLE DEFAULT 0.75,
  verification_status ENUM('unverified', 'pending', 'verified', 'flagged') DEFAULT 'unverified'
);

CREATE TABLE IF NOT EXISTS worker_profiles (
  worker_id VARCHAR(255) PRIMARY KEY,
  school_text TEXT,
  gpa_text TEXT,
  major_text TEXT,
  course_text TEXT,
  education_text TEXT,
  internship_text TEXT,
  skills_text TEXT,
  personality_text TEXT,
  soft_text TEXT,
  preference_text TEXT,
  FOREIGN KEY (worker_id) REFERENCES workers(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS employer_profiles (
  employer_id VARCHAR(255) PRIMARY KEY,
  salary_text TEXT,
  location_text TEXT,
  career_text TEXT,
  reputation_text TEXT,
  meaning_text TEXT,
  candidate_text TEXT,
  FOREIGN KEY (employer_id) REFERENCES employers(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS worker_preferences (
  worker_id VARCHAR(255) PRIMARY KEY,
  salary_reward DOUBLE NOT NULL,
  location_remote DOUBLE NOT NULL,
  growth_opportunity DOUBLE NOT NULL,
  reputation DOUBLE NOT NULL,
  skill_fit_meaning DOUBLE NOT NULL,
  FOREIGN KEY (worker_id) REFERENCES workers(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS employer_preferences (
  employer_id VARCHAR(255) PRIMARY KEY,
  capability_signal DOUBLE NOT NULL,
  skills DOUBLE NOT NULL,
  internship_history DOUBLE NOT NULL,
  personality DOUBLE NOT NULL,
  soft_skills DOUBLE NOT NULL,
  FOREIGN KEY (employer_id) REFERENCES employers(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS utility_scores (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  worker_id VARCHAR(255) NOT NULL,
  employer_id VARCHAR(255) NOT NULL,
  worker_to_employer_utility DOUBLE NOT NULL,
  employer_to_worker_utility DOUBLE NOT NULL,
  UNIQUE KEY unique_pair (worker_id, employer_id),
  FOREIGN KEY (worker_id) REFERENCES workers(id) ON DELETE CASCADE,
  FOREIGN KEY (employer_id) REFERENCES employers(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS matching_results (
  employer_id VARCHAR(255) PRIMARY KEY,
  worker_id VARCHAR(255),
  worker_utility DOUBLE,
  employer_utility DOUBLE,
  matched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (worker_id) REFERENCES workers(id) ON DELETE SET NULL,
  FOREIGN KEY (employer_id) REFERENCES employers(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS algorithm_rounds (
  round_no INT PRIMARY KEY,
  payload JSON NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS audit_records (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  entity_id VARCHAR(255) NOT NULL,
  entity_role ENUM('worker', 'employer') NOT NULL,
  audit_probability DOUBLE NOT NULL,
  deposit_amount DOUBLE NOT NULL,
  penalty_amount DOUBLE NOT NULL,
  audit_status ENUM('not_selected', 'selected', 'passed', 'failed') DEFAULT 'not_selected',
  notes TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
