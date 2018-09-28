#!/usr/bin/python
import os
import time
import datetime
import admin_db
import mydb_config

"""
audit MyDB backups. Check MyDB Admin backup logs.
verify that each data base in active state has been
backed up.

### Configure
 * Backup checking need to be performed within the 24 hour of when backups 
   begin
 * Weekly backups checks are only performed on the day when they are scheduled
 * Weekly backups need to be assigned to a day of week.
 * If your daily backups take longer than 24 hours then you have
   a problem that needs to be re-designed.
 
import mydb.backup_util as backup_util
rpt = backup_util.backup_audit()
print(rpt[1])

file: /opt/node_exporter/metrics_dump/mydb_backup_status

# TYPE mydb_backup_failure gauge
mydb_backup_failure{name="db1"} 1

# TYPE mydb_backup_duration gauge
mydb_backup_duration{name="db2"} 3600
mydb_backup_duration{name="db3"} 3600
mydb_backup_duration{name="db4"} 3600
mydb_backup_duration{name="db5"} 3600
mydb_backup_duration{name="db6"} 3600
mydb_backup_duration{name="db7"} 3600

"""

#  Day that Weekly backups are performed.  Monday =0, Sunday =6
#  The backup check runs on Saturday Morning but checks for Friday 
day_for_weekly = 5


def output_prometheus(prom, check_list):
    """ write backup status in prometheus status
        inputs: prom file pointer to Prometheus output file
        check_list list of dict('Name', 'Message', 'Status', 'Duration')

        Write output in two seccions. One for success and one for failures
    """
    report_date = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    prom.write('# TYPE mydb_backup_report_date gauge\n')
    prom.write('mydb_backup_reportdate{name="reportdate"} %s\n' % report_date)
    prom.write('\n')

    prom.write('# TYPE mydb_backup_failure gauge\n')
    prom.write('mydb_backup_failure{name="null"} 0\n')
    for state in check_list:
        if state['Status'] == 'failure':
            prom.write('mydb_backup_failure{name="%s"} 1\n' % state['Name'])
    prom.write('\n')

    prom.write('# TYPE mydb_backup_duration gauge\n')
    for state in check_list:
        if state['Status'] == 'success':
            prom.write('mydb_backup_duration{name="%s"} %d\n' % (
                        state['Name'], state['Duration']))
    prom.write('\n')

    prom.write('# TYPE mydb_backup_start gauge\n')
    for state in check_list:
        if state['Status'] == 'success':
            prom.write('mydb_backup_start{name="%s"} %s\n' % (
                        state['Name'], state['Start']))


def check_backup_logs(c_id):
    """ query backup logs
    verify that backup started and ended
    verify that backup was run within policy (Daily or Weekly)
    There are many ways to fail but only one combination for success
    default = 'failure'
    return (status, msg)
    """
    since = datetime.datetime.now() - datetime.timedelta(days=1)
    result = admin_db.backup_lastlog(c_id)
    duration = 0
    status = 'failure'
    start = ''
    start_ts = 0
    start_id = end_id = None
    out_of_policy = False
    msg = ''
    for row in result:
        if row.state == 'start':
            start_ts = row.ts
            start_id = row.backup_id
            if row.ts < since:
                out_of_policy = True
        if row.state == 'end':
            end_ts = row.ts
            end_id = row.backup_id
            url = row.url
    if start_id and end_id: 
        if start_id == end_id:   # this is good
            diff = (end_ts - start_ts)
            duration = int(diff.total_seconds())
            if duration == 0: duration = 1 
            if out_of_policy:
               msg = 'Out of Policy. Last backup: %s' % start_ts
            else:
               start = "%s" % start_ts
               status = 'success'
        else:
            msg = 'Backup Running: Started %s' % start_ts
    else:
        if out_of_policy:
            msg = 'Out of Policy. Started: %s' % start_ts
        else:
            msg = 'Error: Last: %s' % start_ts
    return (status, start, duration, msg)


def backup_audit(outfp):
    """ inspect the backup logs for every container that is running.
    get list of all "running" containers
    inspect backup logs based on backup policy for each container
    """
    check_list = []
    containers = admin_db.list_active_containers()
    day_of_week = datetime.datetime.today().weekday()
    for (c_id, con_name) in containers:
        data = admin_db.get_container_data('', c_id)
        if 'BACKUP_FREQ' in data['Info']:
            policy = data['Info']['BACKUP_FREQ']
        else:
            check_list.append({'Name': con_name, 'Status': 'failure',
                               'Message': 'Policy not defined', 'Policy': 'None'})
            continue
        if policy == 'Daily' or policy == 'Weekly':
            if policy == 'Weekly' and day_of_week != day_for_weekly:
                continue
            (status, start, duration, msg) = check_backup_logs(c_id)
            audit = dict({'Name': con_name, 'Status': status,
                          'Start': start, 'Duration': duration,
                          'Policy': policy, 'Message': msg})
            check_list.append(audit)
    output_prometheus(outfp, check_list)

if __name__ == '__main__':
    pid = os.getpid()
    prom_fp = open(mydb_config.prometheus_file + str(pid), "w") 
    backup_audit(prom_fp)
    prom_fp.close
    os.rename(mydb_config.prometheus_file + str(pid), 
              mydb_config.prometheus_file)
