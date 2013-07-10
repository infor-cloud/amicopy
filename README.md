


Deprecation Notice
==================
Since AWS has added the ability to copy AMIs between regions directly to the
API, this project is being deprecated. It will probably be archived and removed
in the near future.




amicopy
=======
amicopy is a Python script that copies EBS AMIs between regions. It uses a
similar methodology to copy EBS volumes that Amigo (AWS's unsupported AMI
copy tool) does, but is much simpler to use.

It uses Tsunami UDP to do a fast transfer.

Be aware that using amicopy will generate both transfer fees and costs
associated with running instances in both the source and destination regions
during the copy.

*Note:* amicopy is still in beta and may not copy AMIs succuessfully. Please
report any bugs you find.

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
Running amicopy differs slightly depending on the OS you are using. The basic
syntax is:

UNIX: ```./amicopy SOURCEAMI SOURCEREGION DESTINATIONREGION```
Windows: ```c:\Python\Python.exe amicopy SOURCEAMI SOURCEREGION 
DESTINATIONREGION```

Note: Examples will show be shown on a UNIX version, but the actual command
line syntax applies to both.

Example:
```bash
./amicopy -v ami-123456 us-east-1 us-west-1
```

### Windows AMIs
Because of how Amazon charges for Windows AMIs, the process for copying the
AMI requires a couple extra steps. amicopy handles these steps for you, but
it requires an extra parameter, the destination AMI.

To determine the destination AMI, find an AMI in the destination region that
matches the AMI you're trying to copy. For example, if you're trying to copy
an AMI runing Windows 2008 R2 Base, you'll look for the AMI ID of the 
Amazon-provided Windows 2008 R2 Base AMI.

**The destination AMI architecture (32 or 64 bit) must match the source AMI
  architecture.**

Use the ```--dst-ami``` command line option to specify the destination AMI.

Example:
```bash
./amicopy ami-123456 us-east-1 us-west-1 --dst-ami ami-635d7926 
```

### Other Command Line Options
* ```-v```, ```--verbose``` Turns on verbose output. This option is highly 
  recommended.
* ```--dst-ami``` Specifies the Windows AMI to use in the destination region
  to generate the new AMI.
* ```--src-key``` AWS access key id for source account
* ```--src-secret``` AWS secret key for source account
* ```--dst-key``` AWS access key id for destination account
* ```--dst-secret``` AWS secret key for destination account
* ```--key-size``` Length of the key to use to encrypt the EBS volumes during
  the transfer. Default: 2048.
* ```--inst-type``` Type of instance to use. **Note**: Using an instance type
   smaller thatn m1.large (the default) will slow down the
   transfer, since smaller instance types have lower network throttle values.
* ```--name``` Tag and/or name to use for temporary AWS objects. Default: 
  amicopy + timestamp
* ```--kernel-id``` AKI to use for destination AMI
* ```--src-keypair``` Keypair to use for source instance. Typically only need 
  to debug.
* ```--dst-keypair``` Keypair to use for destination instance. Typically only
  need to debug.
* ```-d```, ```--debug``` turns on debugging output. This generates a **lot** 
  of output.
  Be sure to redirect it to a file.

Troubleshooting
---------------
The most likely problem is that the copy will appear to hang. This is because
amicopy is dependent on the source and destination instances to complete
the EBS volume copy successfully before continuing. If the process gets stuck,
CTRL-C will cancel the copy and the script will clean up any temporary objects.

Here are some further tips for troubleshooting:
* Always run in verbose (```--verbose``` or ```-v```) mode in order to be
  able to see what the script is doing.
* If amicopy gets stuck at this message, ```Waiting for destination instance 
  to shutdown```, you will need to log into the instances and check the user
  data script logs.
* Use ```--src-keypair``` and  ```--dst-keypair``` to specify SSH keypairs
  to allow you to log into the source and destination images.
* Check the amicopy logs. They are located at
  ```/media/ephemeral0/amicopy.log``` on each server.
* If amicopy fails with an unexpected error, use ```--debug``` to turn on extra
  boto and AWS API information. Be sure to redirect the output to a file,
  since this option will generate *a lot* of information.

Building amicopy
----------------
Building amicopy is not terribly hard, but you will need access to AWS to build
Tsunami UDP. Basically the build procedure builds the Tsunami binaries on AWS
and then includes them

1. Make sure that boto can connect correctly without providing credentials
   directly. See http://docs.pythonboto.org/en/latest/boto_config_tut.html or
   use the AWS_CREDENTIAL_FILE variable to point to your credential file.
   You can test connectivity with the following code. If you don't get an
   exception, your connection should be working.

   ```python
   from boto.ec2.connection import EC2Connection
   e = EC2Connection()
   
   ```
2. Grab the code from github
3. Run make

   ```bash
   make
   ```

Future Improvements
-------------------
* Rewrite the snapshot tracking code

  Right now it's way too complicated and prone to errors. It also makes things
  like adding tagging on destination snapshots quite difficult.

* Add tagging for destination snapshots
* Check to make sure that the AMI is actually an EBS AMI and not an instance
  based AMI
