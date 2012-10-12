amicopy
=======

amicopy is a Python script that copies EBS AMIs between regions. It uses a
similar methodology to copy EBS volumes that Amigo (AWS's unsupported AMI
copy tool) does, but is much simpler to use.

It uses Tsunami UDP to do a fast transfer bet

Be aware that using amicopy will generate both transfer fees and costs
associated with running instances in both the source and destination regions
during the copy.

License
-------
amicopy is released under the BSD license. See LICENSE.txt for more details.

Prerequisites
-------------
* Python 2.7 (2.6 hasn't been tested, but should work)
* A recent version of boto (2.5.2 or 2.6.0 should work)
* An AWS account

Download
--------
Download a prebuilt copy amicopy from 
https://github.com/infor-cloud/amicopy/downloads

Running amicopy
---------------


Building amicopy
----------------
Building amicopy is not terribly hard, but you will need access to AWS to build
Tsunami UDP. Basically the build procedure builds the Tsunami binaries on AWS
and then includes them

# Make sure that boto can connect correctly without providing credentials
  directly. See http://docs.pythonboto.org/en/latest/boto_config_tut.html or
  use the AWS_CREDENTIAL_FILE variable to point to your credential file.
  You can test connectivity with the following code. If you don't get an
  exception, your connection should be working.

  ```python
  from boto.ec2.connection import EC2Connection
  e = EC2Connection()
  
  ```
# Grab the code from github
# Run make

  ```bash
  make
  ```

Future Improvements
-------------------
* Allow copy between accounts

  This should be pretty easy, since the only thing preventing it right now is
  the check that keeps you from copying to the same region.

* Rewrite the snapshot tracking code

  Right now it's way too complicated and prone to errors. It also makes things
  like adding tagging on destination snapshots quite difficult.

* Add tagging for destination snapshots
* Check to make sure that the AMI is actually an EBS AMI and not an instance
  based AMI
