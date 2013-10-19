RHEL/CentOS Installation Considerations
=========

Some hosting providers only support Redhat/CentOS flavors for a server installation.

While CommCareHQ supports running on these platforms, it does take some additional steps to get fully set up on the.

Installing Pillow Imaging Library
-------------------------------------------

Pillow is a fork of the popular Python Imaging Libary (PIL) that makes installation easier.

Pillow is included as part of the requirements for HQ.

In order to install it with full jpeg support, ensure that you have run:

`yum install -y libjpeg-devel libjepeg`

The telltale sign of no jpeg support is this error message when trying to encode or decode a jpeg image:

`IOError: encoder jpeg not available`

After that, the building and installation of Pillow should include jpeg support.

Verifying manually involves downloading the right Pillow version, and running python setup.py build

The output should show this line:

`--- JPEG support available`


Once you see that, you'll be ready to install Pillow again with jpeg support configured!
