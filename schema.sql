-- Q5 schema (the application creates the database and table automatically;
-- this file is kept for reference / manual set-up:  mysql -u root -p < schema.sql)
CREATE DATABASE IF NOT EXISTS contact_db;
USE contact_db;

CREATE TABLE IF NOT EXISTS Contact (
    id        INT AUTO_INCREMENT PRIMARY KEY,
    name      VARCHAR(100) NOT NULL,
    email     VARCHAR(150) NOT NULL,
    phone     VARCHAR(20)  NOT NULL DEFAULT '',
    category  VARCHAR(30)  NOT NULL DEFAULT 'Other',
    notes     TEXT,
    UNIQUE KEY uq_contact_email (email),      -- duplicate e-mail is rejected by the DB too
    KEY idx_contact_name  (name),             -- prefix search / sort in O(log n)
    KEY idx_contact_phone (phone)
);
