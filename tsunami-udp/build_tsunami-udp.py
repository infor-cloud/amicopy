#!/usr/bin/env python
# build-tsunami.py - Build tsunami-udp binaries on an Amazon Linux instance
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
# * Neither the name of Infor nor the names of its contributors may be used
#   to endorse or promote products derived from this software without specific
#   prior written permission.
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

from boto.ec2 import connect_to_region
from argparse import ArgumentParser
from time import sleep
from urllib2 import urlopen, HTTPError, URLError
from sys import stdout, stderr

# List of AMI IDs for Amazon Linux EBS 64 instances
amazon_linux_ebs_64 = {
        'us-east-1':            'ami-1624987f',
        'us-west-2':            'ami-2a31bf1a',
        'us-west-1':            'ami-1bf9de5e',
        'eu-west-1':            'ami-c37474b7',
        'ap-southeast-1':       'ami-a6a7e7f4',
        'ap-northeast-1':       'ami-4e6cd34f',
        'sa-east-1':            'ami-1e08d103',
        'us-gov-west-1':        'ami-21a9cd02',
}

user_data = '''#!/bin/sh

yum install -y httpd
yum install -y gcc make autoconf automake cvs

service httpd start

cd /root

cvs -z3 -d:pserver:anonymous@tsunami-udp.cvs.sourceforge.net:/cvsroot/tsunami-udp co -P tsunami-udp
cd tsunami-udp
make
cp client/tsunami server/tsunamid /var/www/html
'''

def pr(s, nl = False):
    '''Write string to stdout and flush'''
    stdout.write(s)
    if nl: stdout.write('\n')
    stdout.flush()

# Handle command line arguments
parser = ArgumentParser(description = 'Build tsunami-udp for Amazon Linux')
parser.add_argument('--region', default = 'us-east-1',
                    choices = amazon_linux_ebs_64.keys(), metavar = 'REGION',
                    help = 'region in which to build tsunami' +
                           ' (default: %(default)s)')
parser.add_argument('--keypair',
                            help = 'keypair to use for the build instance')
parser.add_argument('--key',
                            help = 'AWS access key id')
parser.add_argument('--secret',
                            help = 'AWS secret key ')
args = parser.parse_args()

# Connect to EC2
pr('Connecting to EC2...')
ec2 = connect_to_region(args.region, aws_access_key_id = args.key,
        aws_secret_access_key = args.secret)
pr('done', True)

sg = None
i = None


try:
    # Set up the security group
    pr('Creating security group TsunamiUdpBuild...')
    sg = ec2.create_security_group('TsunamiUdpBuild', 'tsunami-udp Build SG')
    sg.authorize('tcp', 22, 22, '0.0.0.0/0')
    sg.authorize('tcp', 80, 80, '0.0.0.0/0')
    pr('done', True)

    pr('Starting build instance.')
    i = ec2.run_instances(amazon_linux_ebs_64[args.region],
            key_name = args.keypair,
            security_groups = ['TsunamiUdpBuild'],
            user_data = user_data,
            instance_type = 'm1.small',
            ).instances[0]
    while i.state != 'running':
        sleep(10)
        i.update()
        pr('.')
    pr('done', True)

    pr('Tagging build instance...')
    ec2.create_tags([i.id], {'Name': 'TsunamiUdpBuild'})
    pr('done', True)

    pr('Waiting for port 80 to open.')
    while True:
        try:
            tsunami = urlopen('http://%s/tsunami' % i.public_dns_name).read()
            tsunamid = urlopen('http://%s/tsunamid' % 
                    i.public_dns_name).read()
            
            pr('\nWriting tsunami to disk...')
            open('tsunami', 'wb').write(tsunami)
            pr('done', True)
            pr('Writing tsunamid to disk...')
            open('tsunamid', 'wb').write(tsunamid)
            pr('done', True)
            break
        except (URLError, HTTPError) as e:
            sleep(10)
            pr('.')

    pr('Finished building tsunami-udp', True)

finally:
    try:
        pr('Cleaning up...', True)
        if i:
            pr('Terminating build instance.')
            i.terminate()
            while i.state != 'terminated':
                sleep(10)
                i.update()
                pr('.')
            pr('done', True)

        if sg:
            pr('Deleting security group TsunamiUdpBuild...')
            sg.delete()
            pr('done', True)

    except Exception, e:
        print >> stderr, 'Exception while cleaning up: ', e

