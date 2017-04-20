This folder contains configuration, which needs to be set up once for the
organization, as opposite to configuration per db instance.

Functionality:

* creates AWS user `backup_configurer`, with access key, stores access key in a
  local file

Prerequisites:

* awscli installed locally, on Ubuntu `sudo apt-get install awscli`
* credentials for your AWS account as exported environment variables
