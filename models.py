import datetime
from sqlalchemy import Column, Integer, Sequence, Text, String, DateTime
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from admin_db import Base


class Containers(Base):
    __tablename__ = 'containers'
    id = Column(Integer, Sequence('containers_id_seq'), primary_key=True)
    name = Column(Text)
    data = Column(JSONB)
    ts = Column(TIMESTAMP, default=datetime.datetime.utcnow)


class ContainerState(Base):
    __tablename__ = 'container_state'
    id = Column(Integer, Sequence('container_state_id_seq'), primary_key=True)
    c_id = Column(Integer)
    name = Column(Text)
    state = Column(Text)
    last_state = Column(Text)
    observerd = Column(Text)
    changed_by = Column(Text)
    ts = Column(TIMESTAMP, default=datetime.datetime.utcnow)


class ActionLog(Base):
    """Note: ts should be a auto fill field, 
    but in order to generate log messages with correct histoical
    times the field has to be manually populated
    """
    __tablename__ = 'action_log'
    id = Column(Integer, Sequence('action_log_id_seq'), primary_key=True)
    c_id = Column(Integer)
    name = Column(Text)
    action = Column(Text)
    description = Column(Text)
    ts = Column(TIMESTAMP)


class Backups(Base):
    """Log every backup that if performed"""
    __tablename__ = 'backups'
    id = Column(Integer, Sequence('backups_id_seq'), primary_key=True)
    c_id = Column(Integer)
    name = Column(Text)
    state = Column(Text)
    backup_id = Column(Text)
    backup_type = Column(Text)
    url = Column(Text)
    command = Column(Text)
    err_msg = Column(Text)
    ts = Column(TIMESTAMP, default=datetime.datetime.utcnow)
