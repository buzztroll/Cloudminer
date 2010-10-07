import datetime
import uuid
import simplejson as json
import sqlalchemy
from sqlalchemy import ForeignKey
from sqlalchemy.orm import relation, backref
from sqlalchemy.orm import mapper
from sqlalchemy.orm import sessionmaker
from sqlalchemy import Table
from sqlalchemy import Integer
from sqlalchemy import String, MetaData, Sequence
from sqlalchemy import Column
import cloudyvents.cyvents as cyvents
from sqlalchemy import and_

class _CYventExtra(object):
    def __init__(self, key, value):
        self.key = key
        self.value = value

class _CYvent(object):
    """Convenience class for a parsed event.
    """

    def __init__(self, source, name, key, timestamp, extra):

        self.source = source
        self.name = name
        self.unique_event_key = key
        self.timestamp = timestamp
        self.extra = extra

class _CYVM(object):

    def __init__(self, runname, iaasid, hostname, service_type, runlogdir, vmlogdir, events=[]):
        self.runname = runname
        self.iaasid = iaasid
        self.events = events
        self.hostname = hostname
        self.service_type = service_type
        self.vmlogdir = vmlogdir
        self.runlogdir = runlogdir

    def add_event(self, e):
        self.events.append(e)

metadata = MetaData()

vm_table = Table('vms', metadata,
    Column('id', Integer, Sequence('event_id_seq'), primary_key=True),
    Column('runname', String(50)),
    Column('iaasid', String(50), unique=True),
    Column('hostname', String(128)),
    Column('service_type', String(128)),
    Column('runlogdir', String(128)),
    Column('vmlogdir', String(128)),
    )

event_table = Table('events', metadata,
    Column('id', Integer, Sequence('event_id_seq'), primary_key=True),
    Column('source', String(50)),
    Column('name', String(50)),
    Column('unique_event_key', String(50), unique=True),
    Column('timestamp', sqlalchemy.types.Time),
    Column('vm_id', Integer, ForeignKey('vms.id'))
    )

xtra_table = Table('extras', metadata,
    Column('id', Integer, Sequence('extra_id_seq'), primary_key=True),
    Column('key', String(50)),
    Column('value', String(50)),
    Column('event_id', Integer, ForeignKey('events.id'))
    )

mapper(_CYventExtra, xtra_table)
mapper(_CYvent, event_table, properties={
    'extra': relation(_CYventExtra)})
mapper(_CYVM, vm_table, properties={
    'events': relation(_CYvent)})


class CloudMiner(object):

    def __init__(self, dburl, module=None):
        if module == None:
            self.engine = sqlalchemy.create_engine(dburl)
        else:
            self.engine = sqlalchemy.create_engine(dburl, module=module)
        metadata.create_all(self.engine) 
        self.Session = sessionmaker(bind=self.engine)
        self.session = self.Session()

    def add_cloudyvent_vm(self, runname, iaasid, hostname, service_type, runlogdir, vmlogdir):
        cyvm = self.get_by_iaasid(iaasid)
        if cyvm == None:
            cyvm = _CYVM(runname, iaasid, hostname, service_type, runlogdir, vmlogdir)
            self.session.add(cyvm)
            return True
        else:
            cyvm.hostname = hostname
            cyvm.service_type = service_type
        return False


    def add_cloudyvent(self, runname, iaasid, hostname, service_type, runlogdir, vmlogdir, cyv):

        # first see if we already have this iaasid.  if not create it
        cyvm = self.get_by_iaasid(iaasid)
        if cyvm == None:
            cyvm = _CYVM(runname, iaasid, hostname, service_type, runlogdir, vmlogdir)
            self.session.add(cyvm)
        cyvm.hostname = hostname
        cyvm.service_type = service_type

        xtras_list = []
        if cyv.extra != None:
            for k in cyv.extra.keys():
                va = cyv.extra[k]
                if type(va) != type([]):
                    va = [va,]

                for v in va:
                    e = _CYventExtra(k, v)
                    xtras_list.append(e)

        c = self.get_event_by_key(cyv.key)
        if c:
            return
        _cyv = _CYvent(cyv.source, cyv.name, cyv.key, cyv.timestamp, xtras_list)
        cyvm.add_event(_cyv) 

    def get_event_by_key(self, event_unique_key):
        cye = self.session.query(_CYvent).filter(_CYvent.unique_event_key == event_unique_key).first()
        return cye

    def get_iaas_by_runname(self, runname):
        cyvm_a = self.session.query(_CYVM).filter(_CYVM.runname == runname).all()
        return cyvm_a

    def get_events_by_runname(self, runname):
        cyvm_a = self.session.query(_CYVM).filter(_CYVM.runname == runname).all()
        e_a = []
        for cyvm in cyvm_a:
            e_a = e_a + cyvm.events

        return e_a

    def get_by_iaasid(self, iaasid):
        cyvm = self.session.query(_CYVM).filter(_CYVM.iaasid == iaasid).first()
        return cyvm

    def commit(self):
        self.session.commit()

