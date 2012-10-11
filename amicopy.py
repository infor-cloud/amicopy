#!/usr/bin/env python
#
# amicopy.py - Copy AMIs from one region or account to another
#
# Copyright (c) 2012, David Lowry
# All rights reserved.
# 
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
# 
# * Redistributions of source code must retain the above copyright notice, this
#   list of conditions and the following disclaimer.
# 
# * Redistributions in binary form must reproduce the above copyright notice,
#   this list of conditions and the following disclaimer in the documentation
#   and/or other materials provided with the distribution.
# 
# * Neither the name of the <ORGANIZATION> nor the names of its contributors
#   may be used to endorse or promote products derived from this software
#   without specific prior written permission.
# 
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

import logging
import sys
from argparse import ArgumentParser
from base64 import b64encode, b64decode
from datetime import datetime
from logging import info, debug, warning, error, exception
from time import sleep
from types import MethodType

from boto.s3.connection import S3Connection
from boto.ec2 import connect_to_region
from boto.ec2.blockdevicemapping import BlockDeviceMapping, BlockDeviceType

###############################################################################
# Functions
###############################################################################
def generate_secret(length = 1024, encode = True):
    '''Generate a secret key and optionally encode it using base64'''
    assert length % 8 == 0, 'length should be divisable by 8'
    from os import urandom
    secret = urandom(length / 8)

    if encode:
        from base64 import b64encode
        secret = b64encode(secret)

    return secret

def load_file(filename, evaluate = True, base64 = False):
    '''Load a file and return the (optionally) evaluated and encoded contents'''
    f = open(filename).read()
    if evaluate:
        return eval(f)
    else:
        if base64:
            f = b64encode(f)
        return f

def check(condition, error_msg):
    '''Check a condition and raise an exception if it's not met'''
    if not condition:
        raise AmiCopyError(error_msg)

def ec2_run_instance_wait(self, *args, **kwargs):
    '''Run an EC2 instance and wait for it to change to the running state'''
    i = self.run_instances(*args, **kwargs).instances[0]
    add_method(i, 'terminate_wait', instance_terminate_wait)
    while i.state != 'running':
        sleep(30)
        i.update()
    return i

def instance_terminate_wait(self, *args, **kwargs):
    '''Terminate an EC2 instance and wait for it to change to the terminated
       state'''
    r = self.terminate(*args, **kwargs)
    while self.state != 'terminated':
        sleep(30)
        self.update()
    return r

def volume_detach_wait(self, *args, **kwargs):
    '''Detach a volume and then delete it'''
    r = self.detach(force = True)
    self.update()
    while self.status != 'available':
        sleep(10)
        self.update()
    return r

def add_method(obj, name, func):
    '''Add a function to an existing object as a method'''
    setattr(obj, name, MethodType(func, obj))

def ec2_connect(region, *args, **kwargs):
    '''Connect to a region but fail if the region was invalid'''
    info('Connecting to EC2 region: %s', region)
    ec2 = connect_to_region(region, *args, **kwargs)
    add_method(ec2, 'run_instance_wait', ec2_run_instance_wait)
    check(ec2 is not None, 'invalid region: %s' % region)
    return ec2

###############################################################################
# Constants
###############################################################################
#TODO: move this to other files?
amazon_linux_ebs_64 = load_file('src/amazon_linux_ebs_64.map')

pvgrub_kernel_ids = load_file('src/pvgrub_kernel_ids.map')

valid_block_devs = ['/dev/sdf', '/dev/sdg', '/dev/sdh', '/dev/sdi', '/dev/sdj',
                    '/dev/sdk', '/dev/sdl', '/dev/sdm', '/dev/sdn', '/dev/sdo',
                    '/dev/sdp', ]

src_data = load_file('src/source_user_data.sh', False)

dst_data = load_file('src/destination_user_data.sh', False)

tsunamid = b64decode(load_file('tsunami-udp/tsunamid', False, True))
tsunami = b64decode(load_file('tsunami-udp/tsunami', False, True))

###############################################################################
# Classes
###############################################################################
class Cleanup(object):
    '''Keep track of a list of functions to call on cleanup'''
    def __init__(self):
        self.__items = []

    def add(self, obj, func, log, ):
        self.__items.append((obj, func, log))
    
    def cleanup(self):
        info('Cleaning up temporary AWS objects')
        while self.__items:
            o, f, l = self.__items.pop()
            info(l)
            getattr(o, f)()

class AmiCopyError(Exception): pass

###############################################################################
# Command Line
###############################################################################
# Parse command line options
parser = ArgumentParser()

# Positional arguments
parser.add_argument('ami', metavar = 'AMI',
                    help = 'AMI to copy')
parser.add_argument('src_region', metavar = 'SOURCE',
                    help = 'region of source AMI')
parser.add_argument('dst_region', metavar = 'DESTINATION',
                    help = 'destination region for new AMI')

# Options
# TODO: sort options
parser.add_argument('--key-size', type = int, default = 2048,
                    help = 'length of the secret key used to encrypt the'
                           + ' image (default: %(default)s)')
parser.add_argument('--inst-type', default = 'm1.large',
                    help = 'instance type for transfer instances'
                           + ' (default: %(default)s)')
parser.add_argument('--name', default = ('amicopy' 
                        + datetime.now().strftime('%Y%m%d%H%M%S')),
                    help = 'name/tag to use for temporary object (default:'
                           + ' amicopy + timestamp)')
parser.add_argument('--kernel-id',
                    help = 'AKI to use in destination region')
parser.add_argument('--dst-ami',
                    help = 'Destination AMI to use for Windows AMIs')
parser.add_argument('--src-keypair',
                    help = 'keypair in source region')
parser.add_argument('--dst-keypair',
                    help = 'keypair in destination region')
parser.add_argument('--src-key',
                    help = 'access key id for source account')
parser.add_argument('--src-secret',
                    help = 'secret key for source account')
parser.add_argument('--dst-key',
                    help = 'access key id for destination account (default:'
                           + ' same as source account)')
parser.add_argument('--dst-secret',
                    help = 'secret key for destination account (default: '
                           + ' same as destination account)')

parser.add_argument('-d', '--debug', action = 'store_true', default = False,
                    help = 'turn on debugging output (warning: generates a lot'
                           + ' of output)')
parser.add_argument('-v', '--verbose', action = 'store_true', default = False,
                    help = 'turn on verbose output')

args = parser.parse_args()
if args.dst_key == None: args.dst_key = args.src_key
if args.dst_secret == None: args.dst_secret = args.src_secret

check(args.src_region != args.dst_region,
      'source and destination regions must be different')

###############################################################################
# Variables
###############################################################################
# Stuff to clean up when we're done
cleanup = Cleanup()

# Generate secret key
secret = generate_secret(args.key_size)

# User data variables
userdata = {'secret': secret}

###############################################################################
# Set up logging
###############################################################################
if args.debug:
    level = logging.DEBUG
elif args.verbose:
    level = logging.INFO
else:
    level = logging.WARN

logging.basicConfig(format = '%(asctime)s %(levelname)s: %(message)s',
                    datefmt = '%Y-%m-%d %H:%M:%S',
                    level = level,
                    stream = sys.stdout)

###############################################################################
# Connections
###############################################################################
# Connect to AWS
ec2src = ec2_connect(args.src_region, aws_access_key_id = args.src_key,
                     aws_secret_access_key = args.src_secret)
ec2dst = ec2_connect(args.dst_region, aws_access_key_id = args.dst_key,
                     aws_secret_access_key = args.dst_secret)

info('Connecting to S3')
s3con = S3Connection(aws_access_key_id = args.src_key,
                     aws_secret_access_key = args.src_secret)

###############################################################################
# Pre-flight Checks
###############################################################################
# Make sure AMI is valid
info('Checking source AMI')
src_ami = ec2src.get_image(args.ami)
check(src_ami is not None, 'Invalid AMI: %s' % args.ami)

# Make sure the AMI name is unique in the dest region
info('Checking if AMI name exists in destination region')
n = ec2dst.get_all_images(filters = {'name': src_ami.name})
check(len(n) == 0, 'AMI name %s already exists in destination region' %
      src_ami.name)

# Make sure the kernel id is valid
dst_kernel_id = None
if src_ami.kernel_id is not None:
    if args.kernel_id:
        dst_kernel_id = args.kernel_id
    else:
        info('Determining destination kernel id')
        if pvgrub_kernel_ids[args.src_region] == src_ami.kernel_id:
            dst_kernel_id = pvgrub_kernel_ids[args.dst_region]
        else:
            raise AmiCopyError('Could not determine destination kernel' +
                               ' id. Specify it using --kernel-id')

# Check to make sure that a dest AMI is specified for Windows
if src_ami.platform == 'windows':
    info('Checking destination AMI (Windows)')
    check(args.dst_ami,
          'Destination AMI must be specified for Windows AMIs')
    a = ec2dst.get_all_images([args.dst_ami])
    check(len(a) > 0, 'Destination AMI not found')
    check(a[0].platform == 'windows',
            'Destination AMI is not a Windows AMI')

###############################################################################
# Copy
###############################################################################
try:
    # Upload tsunami to S3
    info('Creating temporary S3 bucket: %s', args.name)
    bucket = s3con.create_bucket(args.name)
    cleanup.add(bucket, 'delete', 'Removing S3 bucket: %s' % args.name)

    # TODO: include tsunami binaries in this file
    info('Uploading tsunamid to %s', args.name)
    key = bucket.new_key('tsunamid')
    key.set_contents_from_string(tsunamid)
    cleanup.add(key, 'delete', 'Deleting tsunamid from S3')
    info('Generating temporary URL for tsunamid')
    userdata['tsunamid'] = key.generate_url(3600)
    
    info('Uploading tsunami to %s', args.name)
    key = bucket.new_key('tsunami')
    key.set_contents_from_string(tsunami)
    cleanup.add(key, 'delete', 'Deleting tsunami from S3')
    info('Generating temporary URL for tsunami')
    userdata['tsunami'] = key.generate_url(3600)

    # Create the security groups
    info('Creating source security group: %s', args.name)
    src_sg = ec2src.create_security_group(args.name, 'AMI Copy')
    cleanup.add(src_sg, 'delete',
                'Removing source security group: %s' % args.name)
    info('Allowing SSH access from 0.0.0.0/0')
    src_sg.authorize('tcp', 22, 22, '0.0.0.0/0')
   
    info('Creating destination security group: %s', args.name)
    dst_sg = ec2dst.create_security_group(args.name, 'AMI Copy')
    cleanup.add(dst_sg, 'delete',
                'Removing destination security group: %s' % args.name)
    info('Allowing SSH access from 0.0.0.0/0')
    dst_sg.authorize('tcp', 22, 22, '0.0.0.0/0')

    # Set up device mapping variables
    info('Generating a list of EBS volumes to copy')
    # Create a list of devices for the copying instances
    tmp_dev = valid_block_devs[:]
    # Grab the source AMI BDM
    src_ami_bdm = src_ami.block_device_mapping
    # Use the source AMI BDM as the base for the destination AMI BDM
    dst_ami_bdm = src_ami.block_device_mapping
    # The instance BDMs should be empty to start with
    src_inst_bdm = BlockDeviceMapping()
    dst_inst_bdm = BlockDeviceMapping()
    device_map = {}

    # Generate the instance BDMs and keep track of the mappings
    for b in src_ami_bdm.keys():
        if src_ami_bdm[b].snapshot_id:
            d = tmp_dev.pop(0)
            src_inst_bdm[d] = BlockDeviceType(
                    snapshot_id = src_ami_bdm[b].snapshot_id,
                    size = src_ami_bdm[b].size,
                    delete_on_termination = True,
                    volume_type = src_ami_bdm[b].volume_type,
                    iops = src_ami_bdm[b].iops,)
            dst_inst_bdm[d] = BlockDeviceType(
                    size = src_ami_bdm[b].size,
                    delete_on_termination = False,
                    volume_type = src_ami_bdm[b].volume_type,
                    iops = src_ami_bdm[b].iops,)
            device_map[b] = d

    # Add an ephemeral device for storing the EBS images
    src_inst_bdm['/dev/sdb'] = BlockDeviceType(ephemeral_name = 'ephemeral0')
    dst_inst_bdm['/dev/sdb'] = BlockDeviceType(ephemeral_name = 'ephemeral0')

    # Start source instance
    info('Starting EC2 source instance')
    src_inst = ec2src.run_instance_wait(amazon_linux_ebs_64[args.src_region],
            key_name = args.src_keypair,
            security_groups = [args.name],
            user_data = src_data % userdata,
            instance_type = args.inst_type,
            block_device_map = src_inst_bdm,
            instance_initiated_shutdown_behavior = 'terminate')
    cleanup.add(src_inst, 'terminate_wait', 'Terminating source instance')

    info('Tagging EC2 source instance')
    ec2src.create_tags([src_inst.id], {'Name': args.name})

    userdata['source'] = src_inst.public_dns_name

    # Start the destination instance
    info('Starting EC2 destination instance')
    dst_inst = ec2dst.run_instance_wait(amazon_linux_ebs_64[args.dst_region],
            key_name = args.dst_keypair,
            security_groups = [args.name],
            user_data = dst_data % userdata,
            instance_type = args.inst_type,
            block_device_map = dst_inst_bdm,
            instance_initiated_shutdown_behavior = 'terminate')
    
    # Clean up created volumes
    dst_inst_bdm = dst_inst.block_device_mapping
    vol_ids = []
    for b in dst_inst_bdm.keys():
        if dst_inst_bdm[b].volume_id and b != '/dev/sda1':
            vol_ids.append(dst_inst_bdm[b].volume_id)
    vols = ec2dst.get_all_volumes(vol_ids)
    for v in vols:
        cleanup.add(v, 'delete', 'Deleting destination volume')

    cleanup.add(dst_inst, 'terminate_wait', 'Terminating destination instance')
    
    info('Tagging EC2 destination instance')
    ec2dst.create_tags([dst_inst.id], {'Name': args.name})

    # Set up security groups for Tsunami
    info('Allowing TCP access to source instance for tsunamid')
    src_sg.authorize('tcp', 46224, 46224, dst_inst.ip_address + '/32')
    info('Allowing UDP access to destination instance for tsunami')
    dst_sg.authorize('udp', 46224, 46224, src_inst.ip_address + '/32')

    # Wait for copy to finish
    info('Waiting for destination instance to shutdown')
    while dst_inst.state == 'running':
        sleep(30)
        dst_inst.update()
    info('Destination instance has shut down')

    if src_ami.platform == 'windows':
        # Start Windows instance
        info('Starting Windows instance')
        win_inst = ec2dst.run_instance_wait(args.dst_ami,
                key_name = args.dst_keypair,
                security_groups = [args.name],
                instance_type = args.inst_type,
                placement = dst_inst.placement)
        cleanup.add(win_inst, 'terminate_wait', 'Terminating Windows instance')

        info('Tagging EC2 Windows instance')
        ec2dst.create_tags([win_inst.id], {'Name': 'windows' + args.name})

        # Stop the Windows instance
        info('Stopping Windows instance')
        win_inst.stop(force = True)
        while win_inst.state != 'stopped':
            sleep(30)
            win_inst.update()

        # Remove the root volume and delete it
        win_inst_bdm = win_inst.block_device_mapping
        vol_ids = []
        for b in win_inst_bdm.keys():
            if win_inst_bdm[b].volume_id:
                vol_ids.append(win_inst_bdm[b].volume_id)
        volumes = ec2dst.get_all_volumes(vol_ids)
        for v in volumes:
            info('Detaching volume %s from Windows instance', v.id)
            v.detach(force = True)
            info('Waiting for volume %s to detach', v.id)
            while v.status != 'available':
                sleep(30)
                v.update()
            info('Deleting volume %s', v.id)
            v.delete()

        # Attach the new volumes
        device_map_r = dict((v,k) for k, v in device_map.iteritems())
        for b in dst_inst_bdm.keys():
            if dst_inst_bdm[b].volume_id and b != '/dev/sda1':
                vol = ec2dst.get_all_volumes([dst_inst_bdm[b].volume_id])[0]
                info('Attaching volume %s to Windows instance', vol.id)
                vol.attach(win_inst.id, device_map_r[b])
                add_method(vol, 'detach_wait', volume_detach_wait)
                cleanup.add(vol, 'detach_wait',
                        'Detaching volume %s from Windows instance' % vol.id)

        # Create an AMI
        info('Registering new AMI')
        ami_id = ec2dst.create_image(instance_id = win_inst.id,
                name = src_ami.name,
                description = src_ami.description,
                no_reboot = True)
    else:
        # Generate snapshots for volumes
        snapshots = []
        ss_map = {}
        for b in dst_inst_bdm.keys():
            if dst_inst_bdm[b].volume_id and b != '/dev/sda1':
                vol = ec2dst.get_all_volumes([dst_inst_bdm[b].volume_id])[0]
                info('Creating snapshot in destination region for volume %s',
                     vol.id)
                ss = vol.create_snapshot(description = 'Created by amicopy (%s)' 
                        % args.name)
                snapshots.append(ss)
                ss_map[b] = ss.id

        # Wait for snapshots to finish
        info('Waiting for snapshot creation to finish')
        wait = True
        while wait:
            wait = False
            for ss in snapshots:
                ss.update()
                if ss.status != 'completed':
                    wait = True
            sleep(30)
        info('Snapshot creation complete')

        # Set up the map for the destination AMI
        for b in dst_ami_bdm.keys():
            if device_map.has_key(b):
                dst_ami_bdm[b].snapshot_id = ss_map[device_map[b]]

        # Register the AMI
        info('Registering new AMI')
        ami_id = ec2dst.register_image(name = src_ami.name,
                description = src_ami.description,
                architecture = src_ami.architecture,
                kernel_id = dst_kernel_id,
                root_device_name = src_ami.root_device_name,
                block_device_map = dst_ami_bdm) 

    info('Waiting for AMI to complete')
    ami = ec2dst.get_all_images([ami_id])[0]
    while ami.state != 'available':
        sleep(30)
        ami.update()

    # TODO: Tag AMI

except (Exception, KeyboardInterrupt) as e:
    exception('Cleaning up because of error')
    try:
        cleanup.cleanup()
    except Exception, ce:
        exception('Error during cleanup')
else:
    cleanup.cleanup()
    print 'AMI Copy Complete: %s' % ami.id


# Create the instances
# Configure the security groups

###############################################################################
# Clean up
###############################################################################
# Don't clean up if the no-cleanup flag is set

