""" Copyright (c) Trainline Limited, 2016. All rights reserved. See LICENSE.txt in the project root for license information. """
# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4

import time
import requests
from environment_manager.utils import LogWrapper

class EMApi(object):
    """Defines all api calls and treats them like an object to give proper interfacing"""

    def __init__(self, server=None, user=None, password=None, retries=5):
        """ Initialise new API object """
        self.server = server
        self.user = user
        self.password = password
        self.retries = retries
        self.token = None
        # Sanitise input
        if server is None or user is None or password is None:
            raise ValueError('EMApi(server=SERVERNAME, user=USERNAME, password=PASSWORD, [retries=N])')
        if server == '' or user == '' or password == '':
            raise ValueError('EMApi(server=SERVERNAME, user=USERNAME, password=PASSWORD, [retries=N])')

    def _api_auth(self):
        """ Function to authenticate in Environment Manager """
        log = LogWrapper()
        log.info('Authenticating in EM with user %s' % self.user)
        # Build base url
        base_url = 'https://%s' % self.server
        # Request token
        token_payload = {'grant_type': 'password',
                         'username': self.user,
                         'password': self.password}
        token = None
        no_token = True
        retries = 0
        while no_token and retries < self.retries:
            em_token_url = '%s/api/token' % base_url
            em_token = requests.post(em_token_url, data=token_payload, timeout=5, verify=False)
            if int(str(em_token.status_code)[:1]) == 2:
                token = em_token.text
                no_token = False
            else:
                log.debug('Could not authenticate, trying again: %s' % em_token.status_code)
                time.sleep(2)
            retries += 1
        if token is not None:
            # Got token now lets get URL
            token_bearer = 'Bearer %s' % token
            return token_bearer
        else:
            raise SystemError('Could not authenticate against Environment Manager')

    def query(self, query_endpoint=None, retries=5, backoff=2):
        """ Function to querying Environment Manager """
        log = LogWrapper()
        if query_endpoint is None:
            log.info('No query endpoint specified, cant just go and query nothing')
            raise SyntaxError('No query endpoint specified, cant just go and query nothing')
        retry_num = 0
        while retry_num < retries:
            retry_num += 1
            log.debug('Going through query iteration %s out of %s' % (retry_num, retries))
            token = self._api_auth()
            log.debug('Using token %s for auth' % token)
            # Build base url
            base_url = 'https://%s' % self.server
            request_url = '%s%s' % (base_url, query_endpoint)
            log.debug('Calling URL %s' % request_url)
            request = requests.get(request_url, headers={'Accept': 'application/json', 'Content-Type': 'application/json', 'Authorization': token}, timeout=30, verify=False)
            if int(str(request.status_code)[:1]) == 2:
                return request.json()
            else:
                log.info('Got a status %s from EM, cant serve, retrying' % request.status_code)
                log.debug(request.request.headers)
                log.debug(request.__dict__)
                time.sleep(backoff)
        # General one if we exceeded our retries
        raise SystemError('Max number of retries (%s) querying Environment Manager, will abort for now' % retries)

    #######################################################
    # This is a full API implementation based on EM docs  #
    #######################################################

    ## Accounts

    ## AMI

    ## ASG
    def get_asgs(self, account='Non-Prod', **kwargs):
        """ Get list of ASGs from EM """
        request_endpoint = '/api/v1/asgs?account=%s' % account
        return self.query(request_endpoint, **kwargs)

    def get_asg_info(self, environment=None, asgname=None, **kwargs):
        """ Get details from ASG """
        if environment is None or asgname is None:
            raise SyntaxError('Either environment or asgname has not been specified')
        request_endpoint = '/api/v1/asgs/%s?environment=%s' % (asgname, environment)
        return self.query(request_endpoint, **kwargs)

    def get_asg_ips(self, environment=None, asgname=None, **kwargs):
        """ Get IPs associated with ASG """
        if environment is None or asgname is None:
            raise SyntaxError('Either environment or asgname has not been specified')
        request_endpoint = '/api/v1/asgs/%s/ips?environment=%s' % (asgname, environment)
        return self.query(request_endpoint, **kwargs)

    def get_asg_scaling_schedule(self, environment=None, asgname=None, **kwargs):
        """ Get scaling schedule associated with ASG """
        if environment is None or asgname is None:
            raise SyntaxError('Either environment or asgname has not been specified')
        request_endpoint = '/api/v1/asgs/%s/scaling-schedule?environment=%s' % (asgname, environment)
        return self.query(request_endpoint, **kwargs)

    def get_asg_launch_config(self, environment=None, asgname=None, **kwargs):
        """ Get scaling schedule associated with ASG """
        if environment is None or asgname is None:
            raise SyntaxError('Either environment or asgname has not been specified')
        request_endpoint = '/api/v1/asgs/%s/launch-config?environment=%s' % (asgname, environment)
        return self.query(request_endpoint, **kwargs)

    ## Audit

    ## Cluster

    ## Deployment

    ## Deployment Map

    ## Environment
    def get_environment_asg_servers(self, environment=None, asgname=None, **kwargs):
        """ Get list of servers belonging to an environment ASG """
        if environment is None or asgname is None:
            raise SyntaxError('Either environment or asgname has not been specified')
        request_endpoint = '/api/v1/environments/%s/servers/%s' % (environment, asgname)
        return self.query(request_endpoint, **kwargs)

    ## Environment Type

    ## Export

    ## Import

    ## Instance

    ## Load Balancers
    def get_lb_settings(self, **kwargs):
        """ Get list of Services from EM """
        request_endpoint = '/api/v1/config/lb-settings'
        return self.query(request_endpoint, **kwargs)

    ## Package

    ## Permissions

    ## Service
    def get_services(self, **kwargs):
        """ Get list of Services from EM """
        request_endpoint = '/api/v1/config/services'
        return self.query(request_endpoint, **kwargs)

    ## Status

    ## Target State

    ## Upstream
    def get_upstreams(self, **kwargs):
        """ Get list of Upstreams from EM """
        request_endpoint = '/api/v1/config/upstreams'
        return self.query(request_endpoint, **kwargs)
