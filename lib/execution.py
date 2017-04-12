#!/usr/bin/env python2
from __future__ import print_function
import paramiko

def run_remotely(host='127.0.0.1', port=22, user='root',
                  command='/bin/true', bufsize=-1, key_filename='',
                  timeout=120, pkey=None):
    """
    Excecutes a command on a remote host and returns the result.
    :param host: Host to connect
    :param port: The port number
    :param user: The username of the system
    :param command: The command to run
    :param key_filename: SSH private key file.
    :param pkey: RSAKey if we want to login with a in-memory key
    :return:
    """
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    client.connect(hostname=host, port=port,
            username=user, timeout=timeout, banner_timeout=timeout)
    chan = client.get_transport().open_session()
    chan.settimeout(timeout)
    chan.set_combine_stderr(True)
    chan.get_pty()
    chan.exec_command(command)
    stdout = chan.makefile('r', bufsize)
    stdout_text = stdout.read()
    status = int(chan.recv_exit_status())
    client.close()
    return stdout_text, status

