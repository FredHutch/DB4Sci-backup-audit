#!/usr/bin/env python
import os
import json
import datetime
import pgpasslib
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import desc
import mydb_config
from human_uptime import human_uptime


host = mydb_config.container_host
port = mydb_config.mydb_admin_port
dbname = mydb_config.admindb_name
admin_user = mydb_config.admin_user
password = pgpasslib.getpass(host, port, dbname, admin_user)

SQLALCHEMY_DATABASE_URI = "postgresql://" + admin_user + ":"
SQLALCHEMY_DATABASE_URI += password + "@"
SQLALCHEMY_DATABASE_URI += host + ":" + port + "/"
SQLALCHEMY_DATABASE_URI += dbname 

engine = create_engine(SQLALCHEMY_DATABASE_URI, convert_unicode=True)
db_session = scoped_session(sessionmaker(autocommit=False,
                                         autoflush=False,
                                         bind=engine))
Base = declarative_base()
Base.query = db_session.query_property()

from models import *


def init_db():
    import models
    Base.metadata.create_all(bind=engine)


"""ActionLog CRUD
    Log all DBaas Container events: [create, delete, restart, backup,
     maintenance]
    CREATE log messages
    READ display_containerlog()
"""


def add_container_log(c_id, name, action, description, ts=None):
    """Log event to table ActionLog
    Note: ts should be a auto fill field with current time stamp,
    but in order to generate log messages with correct histoical
    times the field has to be manually populated.
    ts: type datetime
    """
    if not ts:
        ts = datetime.datetime.now()
    u = ActionLog(c_id=c_id, name=name, action=action,
                  description=description,
                  ts=ts)
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)


def display_container_log(c_id=None, limit=None):
    """Return list of log messages
    filter by name or c_id
    limit number of rows returned
    """
    if c_id:
        result = ActionLog.query.filter(Containers.id == c_id).all()
    else:
        result = ActionLog.query.order_by(ActionLog.id.desc()).all()
    header = "%-20s %-30s %-30s %s\n" % ('TimeStamp', 'Name', 'Action',
                                         'Description')
    if not limit:
        limit = len(result)
    message = ''
    for row in result[0:limit]:
        timestamp = row.ts.strftime("%Y-%m-%d %H:%M:%S")
        message += "%-20s %-30s %-30s %s\n" % (timestamp,
                                               row.name,
                                               row.action,
                                               row.description)
    return (header, message)

"""Container State CRUD
Container State table manages active containers. New records are added when
containers are created. Records are deleted when the container is deleted.
    CREATE add_container_state()
    READ get_container_state()
    UPDATE update_container_state()
    DELETE delete_container_state():
    Note: Docker container names begin with a backslash '\' data['Name']
    retains the backslah from Docker. But the slash is removed for all other
    Tables which use 'Name' as a field.
"""


def add_container_state(c_id, Info, who=None):
    """Add new container to State table. """
    if not who:
        who = 'DBaaS'
    u = ContainerState(c_id=c_id,
                       name=Info['Name'],
                       state=Info['State'],
                       last_state='created',
                       observerd=Info['State'],
                       changed_by=who)
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)


def list_container_names():
    """Return python list of all containers in container table 
    list of tuples
    """
    containers = []
    result = ContainerState.query.all()
    for state in result:
        containers.append(state.name)
    return containers


def get_container_state(con_name=None, c_id=None):
    """Get current state of a container
    returns (state, c_id)
    """
    if c_id:
        state_info = ContainerState.query.filter(
                      ContainerState.c_id == c_id).first()
    elif con_name:
        state_info = ContainerState.query.filter(
                       ContainerState.name == con_name).first()
    else:
        state_info = ContainerState.query.all()
    return state_info


def update_container_state(c_id, state, who=None):
    """Change state of container"""
    if not who:
        who = 'DBaaS'
    state_info = ContainerState.query.filter(
                     ContainerState.c_id == c_id).first()
    a = ContainerState.query.filter(ContainerState.c_id == c_id).update(
           {'state': state,
            'last_state': state_info.state,
            'changed_by': who,
            'ts': datetime.datetime.now()})
    db_session.commit()
    add_container_log(c_id, state_info.name,
                      'change state to ' + state,
                      'updated by DBaaS')


def delete_container_state(c_id):
    """Delete record from Container_State table.
    Deleted Containers are not tracked in Container State
    """
    u = ContainerState.query.filter(ContainerState.c_id == c_id).delete()
    db_session.commit()


def list_containers():
    """Return python list of all containers in container table 
    list of tuples
    """
    containers = []
    result = Containers.query.all()
    for state in result:
        containers.append([state.id, state.name])
    return containers


def list_active_containers():
    """Return python list of all containers in state table
    list of tuples
    """
    containers = []
    state_info = ContainerState.query.all()
    for state in state_info:
        containers.append([state.c_id, state.name])
    return containers


def display_container_state():
    """List container state for all containers in Container State table"""
    fmtstring = "%4s %-30s %-12s %-12s %-15s %s\n"
    header = fmtstring % ('ID', 'Name', 'State',
                          'Last', 'Changed By',
                          'TimeStamp')
    state_info = ContainerState.query.all()
    message = ''
    for state in state_info:
        if isinstance(state.ts, datetime.datetime):
            TS = state.ts.strftime("%Y-%m-%d %H:%M:%S")
        else:
            TS = ''
        outstring = fmtstring % (str(state.c_id),
                                 state.name,
                                 state.state,
                                 state.last_state,
                                 state.changed_by,
                                 TS)
        message += outstring
    return (header, message)

"""Containers CRUD
Container table manages docker inspect <data> for containers. New records
are added when containers are created. Container <data> records are never
deleted. Data from 'Labels' can be modified; Example: Backup_freq.
Relation between <id> and <c_id between all other tables.
     CREATE add_container()
     READ get_container_data()
     UPDATE - update_container_info(c_id, info_data):
     DELETE - needed for mongodb and this is handy to use for test
              cases.
"""


def add_container(inspect, params):
        """Add new container to admin database
        input: Docker inspect from container
        Info block is added to Docker Inspect and stored as JSONB
        in the <data> column of table containers.
        """
        Info = {}
        Info['Name'] = inspect['Name'][1:]
        Info['State'] = inspect['State']['Status']
        Info['Port'] = params['port']
        Info['DBVOL'] = params['db_vol'] + '/' + params['dbname'] 
        Info['Ports'] = ', '.join(str(value[1]) for key, value in
                                  params['port_bindings'].items())
        Info['Image'] = params['image']
        ts = inspect['Created']
        started = ts[:ts.find('.')] + 'Z'
        if Info['State'] != 'running':
            print('Error: New container (%s) State incorrect: %s' % (
                             Info['Name'],
                             Info['State']))
        Info['LastState'] = 'created'
        Info.update(parse_env(inspect['Config']['Env']))
        labels = inspect['Config']['Labels']
        for label in labels.keys():
            Info[label] = labels[label]
        if 'dbengine' not in labels:
            Info['dbengine'] = 'Postgres'
        print("%s, Info:" % Info['Name']),
        print(json.dumps(Info, indent=4))
        inspect['Info'] = Info
        u = Containers(data=inspect, name=Info['Name'])
        db_session.add(u)
        db_session.commit()
        db_session.refresh(u)
        add_container_state(u.id, Info)
        return u.id


def delete_container(id):
    """Delete record from Container table.
    Remove from container_state also
    """
    delete_container_state(id)
    u = Containers.query.filter(Containers.id == id).delete()
    db_session.commit()


def get_container_data(con_name, c_id=None):
    """return list of dicts
        list of <data> field (JSONB) from containers table as dict
        data field contains 'Info'
    """
    if c_id:
        result = Containers.query.filter(Containers.id == c_id).all()
    else:
        result = Containers.query.filter(
                    Containers.data['Name'].astext == "/"+con_name).all()
    if isinstance(result, list) and len(result) > 0:
        return result[0].data
    else:
        return []


def get_container_type(con_name, c_id=None):
    """query containers table
    return list of tubles. (c_id, type)
    container type:  'Postgres', 'MariaDB', 'MongoDB', 'Neo4j' etc
    """
    if con_name:
        state = get_container_state(con_name=con_name)
    elif c_id:
        state = get_container_state(c_id=c_id)
    if state:
        data = get_container_data('', c_id=state.c_id)
        c_id = state.c_id
        dbengine = data['Info']['dbengine']
    else:
        c_id = None
        dbengine = '' 
    return (c_id, dbengine)


def update_container_info(c_id, info_data, who=None):
    """Update container info data. <data> is JSONB.
    <data['Info']> holds mutable data.
    <info_data> type: dict
    return modified container <data>
    """
    if not who:
        who = 'DBaaS'
    result = Containers.query.filter(Containers.id == c_id).one()
    result.data['Info'].update(info_data)
    a = Containers.query.filter(Containers.id == c_id).update({'data': result.data})
    db_session.commit()
    add_container_log(c_id, result.data['Name'][1:],
                      action='update info cid=' + str(c_id),
                      description='update from DBaaS')
    return result.data


def display_container_info(con_name, c_id=None):
    """Return pretty json of 'Info' from container table"""
    if con_name:
        state = get_container_state(con_name=con_name)
        c_id = state.c_id
    data = get_container_data('', c_id=c_id)
    return json.dumps(data['Info'], indent=4)


def display_containers():
    """Return summary from containers table
    Containers table has every container ever created, Container Names can be
    repeated. 
    """
    result = Containers.query.all()
    dis_format = "%3s %-22s %-15s %-22s %-30s %-8s %-6s %-30s %s\n"
    header = dis_format % ("CID", "Container", "Username", "Owner", "Contact",
                           "Status", "Port", "Image", "Created")
    body = ''
    for row in result:
        cid = row.id
        info = row.data['Info']
        started = row.data['State']['StartedAt']
        human = human_uptime(started)
        user = 'NA'
        if 'POSTGRES_USER' in info:
            user = info['POSTGRES_USER']
        elif 'DB_USER' in info:
            user = info['DB_USER']
        image = 'NA'
        if 'Image' in info:
            image = info['Image']
        body += dis_format % (str(cid), info['Name'], user, info['OWNER'],
                              info['CONTACT'], info['State'], info['Port'],
                              image, human)
    return (header, body)


def display_active_containers():
    """Return summary of running containers.
    This should be used for the GUI
    """
    dis_format = "%3s %-22s %-15s %-22s %-30s %-6s %-30s %s\n"
    header = dis_format % ("CID", "Container", "Username", "Owner", "Contact",
                           "Port", "Image", "Created")
    active = list_active_containers()
    slice = [active[c_id][0] for c_id in range(len(active))]
    body = ''
    for c_id in slice:
        data = get_container_data("", c_id)
        info = data['Info']
        started = data['State']['StartedAt']
        human = human_uptime(started)
        user = 'NA'
        if 'POSTGRES_USER' in info:
            user = info['POSTGRES_USER']
        elif 'DB_USER' in info:
            user = info['DB_USER']
        image = 'NA'
        if 'Image' in info:
            image = info['Image']
        body += dis_format % (str(c_id), info['Name'], user, info['OWNER'],
                              info['CONTACT'], info['Port'], image, human)
    return (header, body)


def parse_env(Env):
    """Convert list of strings into dict object.
    Docker Inspect ENV is a list of strings. Env strings are
    in the form of KEY=VALUE. Split strings into key=value pairs
    and return dict object. Only return keys with "good_stuff".
    """
    env = {}
    good_stuff = ['USER', 'PASS', '_DB']
    for item in Env:
        (keyval, value) = item.split('=')
        for target in good_stuff:
            if keyval.find(target) != -1:
                env[keyval] = value
    return env


def backup_log(c_id, name, state, backup_id, backup_type,
               url, command, err_msg):
    """Log event to backup log.  Every backup should be logged
    <created> TIMESTAMP
    <duration> integer
    """
    ts = datetime.datetime.now()
    u = Backups(c_id=c_id,
                name=name,
                state=state,
                backup_id=backup_id,
                backup_type=backup_type,
                url=url,
                command=command,
                err_msg=err_msg[:100])
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)

def backup_lastlog(c_id, tail=None):
    """ Query backup log for the last two log messages for a container """
    limit = 2 if not tail else tail
    result = Backups.query.filter(Backups.c_id == c_id).order_by(desc(Backups.ts)).limit(limit)
    #if len(result) != 2:
    #    print('Error: no records for: %d' % c_id)
    #    return None
    return result 

if __name__ == '__main__':
    init_db()
    print('Test Create functions - Create Containers table based on Inspect')
    print(' -> testing: add_container, add_container_state, add_container_log')

    print('Test Read functions: get_container_data, _state, _type')
    (header, output) = display_container_state()
    print('State Table\n%s' % header)
    print(output)
    output = display_container_log()
    print('Log:\n')
    print(output)

    # result = get_container_data('', con[0].c_id)
    # print(json.dumps(result[0], indent=4))
    # print(json.dumps(result[0], indent=4))
    state_list = get_container_state()
    con = state_list[0]

    print('Testing: update_container_info')
    Info = {'Backup_feq': 'AlmostNever', 'NewField': 'info Works'}
    result = update_container_info(con.c_id, Info)
    data = get_container_data('', con.c_id)
    print(json.dumps(data['Info'], indent=4))

    print('Testing: update_container_state')
    state_info = update_container_state(con.c_id, 'testing')
    result = get_container_state('', con.c_id)
    result = get_container_state('', con.c_id)
    print('New state: %s' % result.state)

    print('Testing: Delete Container_state')
    state_info = delete_container_state(2)

    output = display_container_log()
    print('Event Log:')
    print(output)

    (header, output) = display_container_state()
    print('Final State Table\n%s' % header)
    print(output)
