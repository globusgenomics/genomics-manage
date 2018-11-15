#!/usr/bin/env python
import sys
import subprocess

##################
# Config
# check idle jobs that being idle for a certain hours
CHECK_IDLE_JOB_HOUR_WARNING = 1
CHECK_IDLE_JOB_HOUR_CRITICAL = 2

# check running jobs that being running for a certain hours
CHECK_RUNNING_JOB_HOUR_WARNING = 48
CHECK_RUNNING_JOB_HOUR_CRITICAL = 72

# check total number of running jobs
CHECK_RUNNING_JOB_NUM_WARNING = 50
##################

# convert to seconds
CHECK_IDLE_JOB_WARNING_POINT = CHECK_IDLE_JOB_HOUR_WARNING*3600
CHECK_IDLE_JOB_CRITICAL_POINT = CHECK_IDLE_JOB_HOUR_CRITICAL*3600
CHECK_RUNNING_JOB_WARNING_POINT = CHECK_RUNNING_JOB_HOUR_WARNING*3600
CHECK_RUNNING_JOB_CRITICAL_POINT = CHECK_RUNNING_JOB_HOUR_CRITICAL*3600

cmd = [ 'condor_q', '-allusers', '-format', '%s:', 'ClusterId', '-format', '%s:', 'JobStatus', '-format', '%s:', 'ServerTime', '-format', '%s\n', 'EnteredCurrentStatus' ]
output = subprocess.Popen( cmd, stdout=subprocess.PIPE ).communicate()[0]
if 'Usage: condor_q' in output:
    cmd = [ 'condor_q', '-format', '%s:', 'ClusterId', '-format', '%s:', 'JobStatus', '-format', '%s:', 'ServerTime', '-format', '%s\n', 'EnteredCurrentStatus' ]
    output = subprocess.Popen( cmd, stdout=subprocess.PIPE ).communicate()[0]

current_status = output.split("\n")
current_status = filter(None, current_status)


FAILED_CHECK_IDLE_JOB_WARNING_POINT = []
FAILED_CHECK_IDLE_JOB_CRITICAL_POINT = []
FAILED_CHECK_RUNNING_JOB_WARNING_POINT = []
FAILED_CHECK_RUNNING_JOB_CRITICAL_POINT = []
NUM_OF_RUNNING_JOB = 0

for item in current_status:
    item = item.split(":")
    if item[1] == "1":
        idle_time = int(item[2]) - int(item[3])
        if idle_time >= CHECK_IDLE_JOB_WARNING_POINT:
            FAILED_CHECK_IDLE_JOB_WARNING_POINT.append(item[0])
        if idle_time >= CHECK_IDLE_JOB_CRITICAL_POINT:
            FAILED_CHECK_IDLE_JOB_CRITICAL_POINT.append(item[0])

    elif item[1] == "2":
        NUM_OF_RUNNING_JOB = NUM_OF_RUNNING_JOB + 1
        running_time = int(item[2]) - int(item[3])
        if running_time >= CHECK_RUNNING_JOB_WARNING_POINT:
            FAILED_CHECK_RUNNING_JOB_WARNING_POINT.append(item[0])
        if running_time >= CHECK_RUNNING_JOB_CRITICAL_POINT:
            FAILED_CHECK_RUNNING_JOB_CRITICAL_POINT.append(item[0])

signal = "0"
to_print = "This is a report from Globus Genomics: "
CRITICAL = False
WARNING = False

if FAILED_CHECK_IDLE_JOB_WARNING_POINT != [] or FAILED_CHECK_RUNNING_JOB_WARNING_POINT != [] or NUM_OF_RUNNING_JOB >= CHECK_RUNNING_JOB_NUM_WARNING:
    signal = "1"
    WARNING = True

if FAILED_CHECK_IDLE_JOB_CRITICAL_POINT != [] or FAILED_CHECK_RUNNING_JOB_CRITICAL_POINT != []:
    signal = "2"
    CRITICAL = True

if CRITICAL:
    to_print = to_print + "CRITICAL: "
    if FAILED_CHECK_IDLE_JOB_CRITICAL_POINT != []:
        num = len(FAILED_CHECK_IDLE_JOB_CRITICAL_POINT)
        to_print = to_print + "- {0} job(s) being IDLE for more than {1} hour(s), job ID(s): {2} ".format(num, str(CHECK_IDLE_JOB_HOUR_CRITICAL), " ".join(FAILED_CHECK_IDLE_JOB_CRITICAL_POINT))
    if FAILED_CHECK_RUNNING_JOB_CRITICAL_POINT != []:
        num = len(FAILED_CHECK_RUNNING_JOB_CRITICAL_POINT)
        to_print = to_print + "- {0} job(s) being RUNNING for more than {1} hour(s), job ID(s): {2} ".format(num, str(CHECK_RUNNING_JOB_HOUR_CRITICAL), " ".join(FAILED_CHECK_RUNNING_JOB_CRITICAL_POINT))

if WARNING:
    to_print = to_print + "WARNING: "
    if FAILED_CHECK_IDLE_JOB_WARNING_POINT != []:
        num = len(FAILED_CHECK_IDLE_JOB_WARNING_POINT)
        to_print = to_print + "- {0} job(s) being IDLE for more than {1} hour(s), job ID(s): {2} ".format(num, str(CHECK_IDLE_JOB_HOUR_WARNING), " ".join(FAILED_CHECK_IDLE_JOB_WARNING_POINT))
    if FAILED_CHECK_RUNNING_JOB_WARNING_POINT != []:
        num = len(FAILED_CHECK_RUNNING_JOB_WARNING_POINT)
        to_print = to_print + "- {0} job(s) being RUNNING for more than {1} hour(s), job ID(s): {2} ".format(num, str(CHECK_RUNNING_JOB_HOUR_WARNING), " ".join(FAILED_CHECK_RUNNING_JOB_WARNING_POINT))
    if NUM_OF_RUNNING_JOB >= CHECK_RUNNING_JOB_NUM_WARNING:
        to_print = to_print + "- There are {0} job(s) running ".format(NUM_OF_RUNNING_JOB)

# check condor_q health
cmd = [ 'condor_q']
output = subprocess.Popen( cmd, stdout=subprocess.PIPE ).communicate()[0]
if 'jobs' in output and 'completed' in output and 'idle' in output and 'running' in output:
    pass
else:
    signal = "2"
    CRITICAL = True
    to_print = to_print + "CRITICAL: - condor_q down"

if signal == "0":
    print "This is a report from Globus Genomics: OK - job status ok"
    sys.exit(0)
elif signal == "1":
    print to_print
    sys.exit(1)
elif signal == "2":
    print to_print
    sys.exit(2)
else:
    print "This is a report from Globus Genomics: UKNOWN - job queue monitoring"
    sys.exit(3)
