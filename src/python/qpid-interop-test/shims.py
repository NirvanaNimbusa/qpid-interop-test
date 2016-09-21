"""
Module containing worker thread classes and shims
"""
#
# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
#

from json import loads
from os import getenv, path
from subprocess import check_output, CalledProcessError
from threading import Thread


THREAD_TIMEOUT = 15.0 # seconds to complete before join is forced


class ShimWorkerThread(Thread):
    """Parent class for shim worker threads and return a string once the thread has ended"""
    def __init__(self, thread_name):
        super(ShimWorkerThread, self).__init__(name=thread_name)
        self.arg_list = []
        self.return_obj = None

    def get_return_object(self):
        """Get the return object from the completed thread"""
        return self.return_obj


class Sender(ShimWorkerThread):
    """Sender class for multi-threaded send"""
    def __init__(self, use_shell_flag, send_shim_args, broker_addr, queue_name, type, json_test_str):
        super(Sender, self).__init__('sender_thread')
        if send_shim_args is None:
            print 'ERROR: Sender: send_shim_args == None'
        self.use_shell_flag = use_shell_flag
        self.arg_list.extend(send_shim_args)
        self.arg_list.extend([broker_addr, queue_name, type, json_test_str])

    def run(self):
        """Thread starts here"""
        try:
            #print '\n>>>', self.arg_list # DEBUG - useful to see command-line sent to shim
            return_str = check_output(self.arg_list, shell=self.use_shell_flag)
            if len(return_str) > 0:
                self.return_obj = return_str
        except CalledProcessError as exc:
            self.return_obj = str(exc) + '\n\nOutput:\n' + exc.output


class Receiver(ShimWorkerThread):
    """Receiver class for multi-threaded receive"""
    def __init__(self, receive_shim_args, broker_addr, queue_name, type, json_test_str):
        super(Receiver, self).__init__('receiver_thread')
        if receive_shim_args is None:
            print 'ERROR: Receiver: receive_shim_args == None'
        self.arg_list.extend(receive_shim_args)
        self.arg_list.extend([broker_addr, queue_name, type, json_test_str])

    def run(self):
        """Thread starts here"""
        try:
            #print '\n>>>', self.arg_list # DEBUG - useful to see command-line sent to shim
            output = check_output(self.arg_list)
            #print '<<<', output # DEBUG - useful to see text received from shim
            str_tvl = output.split('\n')[0:-1] # remove trailing \n
            #if len(str_tvl) == 1:
            #    self.return_obj = output
            if len(str_tvl) == 2: # AMQP type test return
                self.return_obj = loads(str_tvl[1])
            elif len(str_tvl) == 4: # JMS test return
                self.return_obj = (str_tvl[0], loads(str_tvl[1]), loads(str_tvl[2]), loads(str_tvl[3]))
            else: # Make a single line of all the bits and return that
                #self.return_obj = loads("".join(str_tvl[1:]))
                self.return_obj = output
        except CalledProcessError as exc:
            self.return_obj = str(exc) + '\n\n' + exc.output

class Shim(object):
    """Abstract shim class, parent of all shims."""
    NAME = None
    def __init__(self, sender_shim, receiver_shim):
        self.sender_shim = sender_shim
        self.receiver_shim = receiver_shim
        self.send_params = None
        self.receive_params = None
        self.use_shell_flag = False

    def create_sender(self, broker_addr, queue_name, type, json_test_str):
        """Create a new sender instance"""
        return Sender(self.use_shell_flag, self.send_params, broker_addr, queue_name, type, json_test_str)

    def create_receiver(self, broker_addr, queue_name, type, json_test_str):
        """Create a new receiver instance"""
        return Receiver(self.receive_params, broker_addr, queue_name, type, json_test_str)

class ProtonPythonShim(Shim):
    """Shim for qpid-proton Python client"""
    NAME = 'ProtonPython'
    def __init__(self, sender_shim, receiver_shim):
        super(ProtonPythonShim, self).__init__(sender_shim, receiver_shim)
        self.send_params = [self.sender_shim]
        self.receive_params = [self.receiver_shim]


class ProtonCppShim(Shim):
    """Shim for qpid-proton C++ client"""
    NAME = 'ProtonCpp'
    def __init__(self, sender_shim, receiver_shim):
        super(ProtonCppShim, self).__init__(sender_shim, receiver_shim)
        self.send_params = [self.sender_shim]
        self.receive_params = [self.receiver_shim]


class QpidJmsShim(Shim):
    """Shim for qpid-jms JMS client"""
    NAME = 'QpidJms'

    # Installed versions
    # TODO: Automate this - it gets out of date quickly
    # Maven works out all the deps, should use that
    QPID_JMS_SHIM_VER = '0.1.0-SNAPSHOT'
    QPID_JMS_VER = '0.20.0-SNAPSHOT'
    QPID_PROTON_J_VER = '0.15.0-SNAPSHOT'
    JMS_API_VER = '1.1.1'
    LOGGER_API_VER = '1.7.21'
    LOGGER_IMPL_VER = '1.7.21'
    NETTY_VER = '4.0.40.Final'

    # Classpath components
    #QPID_INTEROP_TEST_SHIM_JAR = path.join(QPID_INTEROP_TEST_HOME, 'shims', 'qpid-jms', 'target', 'qpid-jms-shim.jar')
    MAVEN_REPO_PATH = path.join(getenv('HOME'), '.m2', 'repository')
    JMS_API_JAR = path.join(MAVEN_REPO_PATH, 'org', 'apache', 'geronimo', 'specs', 'geronimo-jms_1.1_spec', JMS_API_VER,
                            'geronimo-jms_1.1_spec-%s.jar' % JMS_API_VER)
    JMS_IMPL_JAR = path.join(MAVEN_REPO_PATH, 'org', 'apache', 'qpid', 'qpid-jms-client', QPID_JMS_VER,
                             'qpid-jms-client-%s.jar' % QPID_JMS_VER)
    LOGGER_API_JAR = path.join(MAVEN_REPO_PATH, 'org', 'slf4j', 'slf4j-api', LOGGER_API_VER,
                               'slf4j-api-%s.jar' % LOGGER_API_VER)
    LOGGER_IMPL_JAR = path.join(MAVEN_REPO_PATH, 'org', 'slf4j', 'slf4j-nop', LOGGER_IMPL_VER,
                                'slf4j-nop-%s.jar' % LOGGER_IMPL_VER)
    PROTON_J_JAR = path.join(MAVEN_REPO_PATH, 'org', 'apache', 'qpid', 'proton-j', QPID_PROTON_J_VER,
                             'proton-j-%s.jar' % QPID_PROTON_J_VER)
    NETTY_JAR = path.join(MAVEN_REPO_PATH, 'io', 'netty', 'netty-all', NETTY_VER, 'netty-all-%s.jar' % NETTY_VER)
    QPID_JMS_SHIM_JAR = path.join(MAVEN_REPO_PATH, 'org', 'apache', 'qpid', 'qpid-interop-test-jms-shim',
                                  QPID_JMS_SHIM_VER, 'qpid-interop-test-jms-shim-%s.jar' % QPID_JMS_SHIM_VER)

    JAVA_HOME = getenv('JAVA_HOME', '/usr/bin') # Default only works in Linux
    JAVA_EXEC = path.join(JAVA_HOME, 'java')

    def __init__(self, dependency_class_path, sender_shim, receiver_shim):
        super(QpidJmsShim, self).__init__(sender_shim, receiver_shim)
        self.dependency_class_path = dependency_class_path
        self.send_params = [self.JAVA_EXEC, '-cp', self.get_java_class_path(), self.sender_shim]
        self.receive_params = [self.JAVA_EXEC, '-cp', self.get_java_class_path(), self.receiver_shim]

    def get_java_class_path(self):
        """Method to construct and return the Java class path necessary to run the shim"""
        return ':'.join([self.QPID_JMS_SHIM_JAR, self.dependency_class_path])
    #                     self.JMS_API_JAR,
    #                     self.JMS_IMPL_JAR,
    #                     self.LOGGER_API_JAR,
    #                     self.LOGGER_IMPL_JAR,
    #                     self.PROTON_J_JAR,
    #                     self.NETTY_JAR])