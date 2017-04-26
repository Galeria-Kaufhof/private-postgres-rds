This folder contains configuration, which needs to be set up once for the
organization, as opposite to configuration per db instance.

Functionality:

* creates AWS user `backup_configurer`, with access key, stores access key in a
  local file

Prerequisites:

* awscli installed locally, on Ubuntu `sudo apt-get install awscli`
* credentials for a power user for your AWS account (root AWS user would do) as exported environment variables

To apply principle of least priveledge following user/bucket hierarchy is
used::

  \- AWS root or similar user (you need to provide AWS_SECRET_ACCESS_KEY,
      AWS_REGION, AWS_ACCESS_KEY_ID for this user before running `invoke
      organization_once`
    \- backup_configurer (created by `invoke organization_once`)
      \- backuper-<db_instance_name>-<zone> (for each db_instance and zone)
          (created by `invoke configure_cluster`)
        \- backup--<service-url-for-db_instance_name-and-zone> S3 bucket
          (created by `invoke configure_cluster`)
          \- 2017-04-20_13-28-08.055350740 (timestamp folder for each full backup)
            (created by full backup via cron)
            \- basebackup.tar.gz
            \- xlog folder with subsequent write ahead logs (continuosly uploaded
                by postgres xlog archiver process)

