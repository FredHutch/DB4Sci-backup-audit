# DB4Sci Backup Audit 

## Overview
DB4Sci is a containerized database provisioning application. DB4Sci can provision many different types and versions of containerized databases. DB4Sci allows users at your site to create databases with less effort than it takes to fill out a help desk ticket. 
Metadata for each container is kept in an administrative database. Users can select to have their database
backed up and the frequency of the backups.  

## Backup Monitor
DB4Sci performs database backups daily on the containers. Database backup
results are logged to an administrative database. Backup Audit analyzes
the backup logs and creates Prometheus data files for Grafana. Backup Audit
should be installed independently from DB4Sci. Backup Audit makes a network
connection to the admin database and can be run from a system separate from DB4Sci.

## Scheduling
DB4Sci performs daily backups. Backup Audit should also be run once per day to
ensure that all backups have been performed.  Schedule Backup Audit to run
after backups have been performed but within a 24 window of the backup start.
Backup Audits window for checking is based on hours so it is not necessary
to run the backups and the audit within the same day. DB4Sci backups and
Backup Audit both run from cron.

## Configuration
A configuration file is used to setup Backup Audit. 

    cp mydb_config.example mydb_config.py

Edit **mydb_config.py** to configure Backup Audit.
Connection information for the administrative database is needed. Backup
Audit expects the database password to be kept in .pgpass file. The location
of the file is specified in the configuration file. Backup Audit needs to be
configured to know which day of the week for Weekly backups.  

## Programming Notes
Backup  Audit uses Python, SQLAlchemy, and PostgreSQL. Backup Audit can be
used as a template to start your own project that requires PostgreSQL and
Python.

#### Program Files
* **admin_db.py** Contains all SQLAlchemy routines for CRUD, Create, Read, Update and Delete
* **models.py** Defines multi-table  database schema
* **backup_audit.py** Main logic 
