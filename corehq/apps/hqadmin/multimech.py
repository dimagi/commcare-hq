# This file is pulled direclty from multi-mechanize
# https://github.com/cgoldberg/multi-mechanize

#!/usr/bin/env python
#
#  Copyright (c) 2010 Brian Knox (taotetek@gmail.com)
#  License: GNU LGPLv3
#
#  This file is part of Multi-Mechanize
#

"""a collection of functions and classes for multi-mechanize results files"""

import re
import fileinput
from datetime import datetime

try:
    from sqlalchemy.ext.declarative import declarative_base
    from sqlalchemy.orm import sessionmaker, relation
    from sqlalchemy import create_engine
    from sqlalchemy import Column, Integer, String, Float, DateTime
    from sqlalchemy import ForeignKey, UniqueConstraint
except ImportError:
    print "(optional: please install sqlalchemy to enable db logging)"


Base = declarative_base()

class GlobalConfig(Base):
    """class representing a muli-mechanize global config"""
    __tablename__ = 'mechanize_global_configs'

    id = Column(Integer, nullable=False, primary_key=True)
    run_time = Column(Integer, nullable=False)
    rampup = Column(Integer, nullable=False)
    results_ts_interval = Column(Integer, nullable=False)
    user_group_configs = relation("UserGroupConfig",
        primaryjoin="UserGroupConfig.mechanize_global_configs_id==GlobalConfig.id")
    results = relation("ResultRow",
        primaryjoin="GlobalConfig.id==ResultRow.mechanize_global_configs_id")

    def __init__(self, run_time=None, rampup=None, results_ts_interval=None):
        self.run_time = str(run_time)
        self.rampup = int(rampup)
        """rampup time for the rest run"""
        self.results_ts_interval = int(results_ts_interval)

    def __repr__(self):
        return "<GlobalConfig('%i', '%i', '%i')>" % (
                self.run_time, self.rampup, self.results_ts_interval)

class UserGroupConfig(Base):
    """class representing a multi-mechanize user group config"""
    __tablename__ = 'mechanize_user_group_configs'

    id = Column (Integer, nullable=False, primary_key=True)
    mechanize_global_configs_id = Column(Integer, ForeignKey('mechanize_global_configs.id'), nullable=False)
    user_group = Column(String(50), nullable=False)
    threads = Column(Integer, nullable=False)
    script = Column(String(50), nullable=False)

    def __init__(self, user_group=None, threads=None, script=None):
        self.user_group = str(user_group)
        self.threads = int(threads)
        self.script = str(script)

    def __repr__(self):
        return "<UserGroupConfig('%s','%s','%s')>" % (
                self.user_group, self.threads, self.script)

class ResultRow(Base):
    """class representing a multi-mechanize results.csv row"""
    __tablename__ = 'mechanize_results'
    __table_args__ = (
        UniqueConstraint('run_id','trans_count', name='uix_1'),
        )

    id = Column(Integer, nullable=False, primary_key=True)
    mechanize_global_configs_id = Column(Integer,
        ForeignKey('mechanize_global_configs.id'), nullable=False)
    project_name = Column(String(50), nullable=False, index=True)
    run_id = Column(DateTime, nullable=False, index=True)
    trans_count = Column(Integer, nullable=False, index=True)
    elapsed = Column(Float, nullable=False, index=True)
    epoch = Column(Float, nullable=False, index=True)
    user_group_name = Column(String(50), nullable=False)
    scriptrun_time = Column(Float, nullable=False)
    error = Column(String(255))
    custom_timers = Column(String(255))

    global_config = relation("GlobalConfig",
            primaryjoin="ResultRow.mechanize_global_configs_id==GlobalConfig.id")

    timers = relation("TimerRow",
        primaryjoin="ResultRow.id==TimerRow.mechanize_results_id")

    def __init__(self, project_name=None, run_id=None, trans_count=None,
            elapsed=None, epoch=None, user_group_name=None,
            scriptrun_time=None, error=None, custom_timers=None):
        self.project_name = str(project_name)
        self.run_id = run_id
        self.trans_count = int(trans_count)
        self.elapsed = float(elapsed)
        self.epoch = int(epoch)
        self.user_group_name = str(user_group_name)
        self.scriptrun_time = float(scriptrun_time)
        self.error = str(error)
        self.custom_timers = str(custom_timers)

    def __repr__(self):
        return "<ResultRow('%s','%s','%i','%.3f','%i','%s','%.3f','%s','%s')>" % (
                self.project_name, self.run_id, self.trans_count, self.elapsed,
                self.epoch, self.user_group_name, self.scriptrun_time,
                self.error, self.custom_timers)

class TimerRow(Base):
    """class representing a multi-mechanize custom timer result"""
    __tablename__ = 'mechanize_custom_timers'
    id = Column(Integer, nullable=False, primary_key=True)
    mechanize_results_id = Column(Integer,
         ForeignKey('mechanize_results.id'), nullable=False)
    timer_name = Column(String(50), nullable=False, index=True)
    elapsed = Column(Float, nullable=False, index=True)

    def __init__(self, timer_name=None, elapsed=None):
        self.timer_name = str(timer_name)
        self.elapsed = float(elapsed)

    def __repr__(self):
        return "<TimerRow('%s', '%s')>" % (self.timer_name, self.elapsed)

    result_rows = relation("ResultRow",
        primaryjoin="TimerRow.mechanize_results_id==ResultRow.id")

def load_results_database(project_name, run_localtime, results_dir,
        results_database, run_time, rampup, results_ts_interval,
        user_group_configs):
    """parse and load a multi-mechanize results csv file into a database"""

    logline_re = re.compile('(.+),(.+),(.+),(.+),(.+),(.?),(\{.+\})')

    engine = create_engine(results_database, echo=False)
    ResultRow.metadata.create_all(engine)
    TimerRow.metadata.create_all(engine)
    GlobalConfig.metadata.create_all(engine)
    UserGroupConfig.metadata.create_all(engine)

    sa_session = sessionmaker(bind=engine)
    sa_current_session = sa_session()

    run_id = datetime(run_localtime.tm_year, run_localtime.tm_mon,
        run_localtime.tm_mday, run_localtime.tm_hour, run_localtime.tm_min,
        run_localtime.tm_sec)

    results_file = results_dir + 'results.csv'

    global_config = GlobalConfig(run_time, rampup, results_ts_interval)
    sa_current_session.add(global_config)

    for i, ug_config in enumerate(user_group_configs):
        user_group_config = UserGroupConfig(ug_config.name,
                ug_config.num_threads, ug_config.script_file)
        global_config.user_group_configs.append(user_group_config)

    for line in fileinput.input([results_file]):
        line = line.rstrip()
        match = logline_re.match(line)
        if match:
            result_row = ResultRow(project_name, run_id, match.group(1),
                    match.group(2), match.group(3), match.group(4),
                    match.group(5), match.group(6), match.group(7))

            global_config.results.append(result_row)
            timer_data = eval(match.group(7))
            for index in timer_data:
                timer_row = TimerRow(index, timer_data[index])
                result_row.timers.append(timer_row)

            sa_current_session.add(result_row)

    sa_current_session.commit()
    sa_current_session.close()
