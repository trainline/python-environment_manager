""" Copyright (c) Trainline Limited, 2016. All rights reserved. See LICENSE.txt in the project root for license information. """
# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4

import time
import requests
import logging
from requests.exceptions import *
from requests.packages.urllib3.exceptions import InsecureRequestWarning
from environment_manager.utils import LogWrapper, json_encode, to_list

# Remove insecure request warning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

class EMApi(object):
    """Defines all api calls and treats them like an object to give proper interfacing"""

    def __init__(self, server=None, user=None, password=None, retries=5, default_headers={}):
        """ Initialise new API object """
        self.server = server
        self.user = user
        self.password = password
        self.retries = retries
        self.default_headers = {'Accept': 'application/json', 'Content-Type': 'application/json'}
        self.default_headers.update(default_headers)
        self.token = None

        # Sanitise input
        if server is None or user is None or password is None:
            raise ValueError('EMApi(server=SERVERNAME, user=USERNAME, password=PASSWORD, [retries=N])')
        if server == '' or user == '' or password == '':
            raise ValueError('EMApi(server=SERVERNAME, user=USERNAME, password=PASSWORD, [retries=N])')

    def _api_auth(self):
        """ Function to authenticate in Environment Manager """
        log = LogWrapper()
        logging.getLogger("requests").setLevel(logging.WARNING)
        logging.getLogger("urllib3").setLevel(logging.WARNING)
        log.debug('Authenticating in EM with user %s' % self.user)
        # Build base url
        base_url = 'https://%s' % self.server
        # Request token
        token_payload = {'username': self.user,
                         'password': self.password}
        token = None
        no_token = True
        retries = 0
        while no_token and retries < self.retries:
            try:
                retries += 1
                em_token_url = '%s/api/v1/token' % base_url
                em_token = requests.post(em_token_url, data=json_encode(token_payload), headers=self.default_headers, timeout=5, verify=False)
                if int(str(em_token.status_code)[:1]) == 2:
                    token = em_token.text
                    no_token = False
                else:
                    log.debug('Could not authenticate, trying again: %s' % em_token.status_code)
                    time.sleep(2)
            except (ConnectionError, Timeout) as error:
                log.debug('There was a problem with the connection, trying again: %s' % error.message)
                time.sleep(2)
        if token is not None:
            # Got token now lets get URL
            token_bearer = 'Bearer %s' % token
            return token_bearer
        else:
            raise SystemError('Could not authenticate against Environment Manager')

    def _get_token(self):
        """ Internal function to get a new token """
        if self.token is None:
            self.token = self._api_auth()
        return self.token

    def _renew_token(self):
        """ Internal function to renew a token """
        self.token = self._api_auth()

    def query(self, query_endpoint=None, data=None, headers={}, query_type='get', retries=5, backoff=2):
        """ Function to querying Environment Manager """
        log = LogWrapper()
        logging.getLogger("requests").setLevel(logging.WARNING)
        logging.getLogger("urllib3").setLevel(logging.WARNING)
        if query_endpoint is None:
            log.info('No endpoint specified, cant just go and query nothing')
            raise SyntaxError('No endpoint specified, cant just go and query nothing')
        if query_type.lower() == 'post' and data is None:
            log.info('No data specified, we need to send data with method %s' % query_type)
            raise SyntaxError('No data specified, we need to send data with method %s' % query_type)
        retry_num = 0
        while retry_num < retries:
            retry_num += 1
            log.debug('Going through query iteration %s out of %s' % (retry_num, retries))
            token = self._get_token()
            log.debug('Using token %s for auth' % token)
            # Build base url
            base_url = 'https://%s' % self.server
            request_url = '%s%s' % (base_url, query_endpoint)
            log.debug('Calling URL %s' % request_url)
            query_headers = self.default_headers.copy()
            query_headers.update({'Authorization': token})
            if isinstance(headers, dict):
                query_headers.update(headers)

            request_values = {'url':request_url, 'headers':query_headers, 'timeout':30, 'verify':False}
            if data is not None:
                request_values['data'] = json_encode(data)

            request_method = getattr(requests, query_type.lower())
            if request_method is None:
                raise SyntaxError('Cannot process query type %s' % query_type)

            request = None
            try:
                request = request_method(**request_values)
            except (ConnectionError, Timeout) as error:
                log.debug('There was a problem with the connection, trying again')
                continue
            status_type = int(str(request.status_code)[:1])

            if status_type == 2 or status_type == 3:
                try:
                    return request.json()
                except ValueError:
                    return request.text
            elif status_type == 4:
                try:
                    error_msg = request.json()['error']
                except:
                    try:
                        error_msg = request.json()['errors']
                    except:
                        if request.text == 'jwt expired' or request.text == 'invalid token':
                            log.info('Your auth token expired or is inavlid, re-authenticating and attempting request again...')
                            self._renew_token()
                            continue
                        elif request.text:
                            error_msg = request.text
                        else:
                            error_msg = 'An unknown error occured'
                raise ValueError(error_msg)
            else:
                log.info('Got a status %s from EM, cant serve, retrying' % request.status_code)
                log.debug(request.request.headers)
                log.debug(request.__dict__)
                time.sleep(backoff)
        # General one if we exceeded our retries
        raise SystemError('Max number of retries (%s) querying Environment Manager, last http code is %s, will abort for now' % (retries, request.status_code))

    #######################################################
    # This is a full API implementation based on EM docs  #
    #######################################################

    ## Accounts
    def get_accounts_config(self, **kwargs):
        """ List the AWS Accounts that associated with Environment Manager """
        request_endpoint = '/api/v1/config/accounts'
        return self.query(query_endpoint=request_endpoint, query_type='GET', **kwargs)

    def post_accounts_config(self, data={}, **kwargs):
        """ Add an association to an AWS Account """
        request_endpoint = '/api/v1/config/accounts'
        return self.query(query_endpoint=request_endpoint, query_type='POST', data=data, **kwargs)

    def put_account_config(self, accountnumber=None, data={}, **kwargs):
        """ Update an associated AWS Account """
        if accountnumber is None:
            raise SyntaxError('acountnumber has not been specified')
        request_endpoint = '/api/v1/config/accounts/%s' % accountnumber
        return self.query(query_endpoint=request_endpoint, query_type='PUT', data=data, **kwargs)

    def delete_account_config(self, accountnumber=None, **kwargs):
        """ Remove an AWS Account association """
        if accountnumber is None:
            raise SyntaxError('Required value has not been specified')
        request_endpoint = '/api/v1/config/accounts/%s' % accountnumber
        return self.query(query_endpoint=request_endpoint, query_type='DELETE', **kwargs)

    ## AMI
    def get_images(self, account=None, **kwargs):
        """ Get the list of available AMI images. Only those that are privately published under associated accounts are included """
        if account is None:
            account_qs = ''
        else:
            account_qs = '?account=%s' % account
        request_endpoint = '/api/v1/images%s' % account_qs
        return self.query(query_endpoint=request_endpoint, query_type='GET', **kwargs)

    ## ASG
    def get_asgs(self, account='Non-Prod', **kwargs):
        """ List ASGS matching the given criteria. By default returns all ASGs across all accounts """
        request_endpoint = '/api/v1/asgs?account=%s' % account
        return self.query(query_endpoint=request_endpoint, query_type='GET', **kwargs)

    def get_asg(self, environment=None, asgname=None, **kwargs):
        """ Get a single ASG for the given environment """
        if environment is None or asgname is None:
            raise SyntaxError('Either environment or asgname has not been specified')
        request_endpoint = '/api/v1/asgs/%s?environment=%s' % (asgname, environment)
        return self.query(query_endpoint=request_endpoint, query_type='GET', **kwargs)

    def put_asg(self, environment=None, asgname=None, data={}, **kwargs):
        """ Update properties of an ASG """
        if environment is None or asgname is None:
            raise SyntaxError('Either environment or asgname has not been specified')
        request_endpoint = '/api/v1/asgs/%s?environment=%s' % (asgname, environment)
        return self.query(query_endpoint=request_endpoint, query_type='PUT', data=data, **kwargs)

    def delete_asg(self, environment=None, asgname=None, **kwargs):
        """ Delete ASG and it's target state """
        if environment is None or asgname is None:
            raise SyntaxError('Either environment or asgname has not been specified')
        request_endpoint = '/api/v1/asgs/%s?environment=%s' % (asgname, environment)
        return self.query(query_endpoint=request_endpoint, query_type='DELETE', **kwargs)

    def get_asg_ready(self, environment=None, asgname=None, **kwargs):
        """ Determine if an ASG is ready to deploy to, eg. at least one instance is present and all are "InService" """
        if environment is None or asgname is None:
            raise SyntaxError('Either environment or asgname has not been specified')
        request_endpoint = '/api/v1/asgs/%s/ready?environment=%s' % (asgname, environment)
        return self.query(query_endpoint=request_endpoint, query_type='GET', **kwargs)

    def get_asg_ips(self, environment=None, asgname=None, **kwargs):
        """ Get IPs associated with an ASG in the given environment """
        if environment is None or asgname is None:
            raise SyntaxError('Either environment or asgname has not been specified')
        request_endpoint = '/api/v1/asgs/%s/ips?environment=%s' % (asgname, environment)
        return self.query(query_endpoint=request_endpoint, query_type='GET', **kwargs)

    def get_asg_scaling_schedule(self, environment=None, asgname=None, **kwargs):
        """ Get scaling schedule actions for given ASG """
        if environment is None or asgname is None:
            raise SyntaxError('Either environment or asgname has not been specified')
        request_endpoint = '/api/v1/asgs/%s/scaling-schedule?environment=%s' % (asgname, environment)
        return self.query(query_endpoint=request_endpoint, query_type='GET', **kwargs)

    def put_asg_scaling_schedule(self, environment=None, asgname=None, data={}, **kwargs):
        """ Update scaling schedule actions for given ASG """
        if environment is None or asgname is None:
            raise SyntaxError('Either environment or asgname has not been specified')
        request_endpoint = '/api/v1/asgs/%s/scaling-schedule?environment=%s' % (asgname, environment)
        return self.query(query_endpoint=request_endpoint, query_type='PUT', data=data, **kwargs)

    def put_asg_size(self, environment=None, asgname=None, data={}, **kwargs):
        """ Resize an ASG in the given environment """
        if environment is None or asgname is None:
            raise SyntaxError('Either environment or asgname has not been specified')
        request_endpoint = '/api/v1/asgs/%s/size?environment=%s' % (asgname, environment)
        return self.query(query_endpoint=request_endpoint, query_type='PUT', data=data, **kwargs)

    def get_asg_launch_config(self, environment=None, asgname=None, **kwargs):
        """ Get the launch config associated with an ASG in the given environment """
        if environment is None or asgname is None:
            raise SyntaxError('Either environment or asgname has not been specified')
        request_endpoint = '/api/v1/asgs/%s/launch-config?environment=%s' % (asgname, environment)
        return self.query(query_endpoint=request_endpoint, query_type='GET', **kwargs)

    def put_asg_launch_config(self, environment=None, asgname=None, data={}, **kwargs):
        """ Update the launch config associated with an ASG in the given environment """
        if environment is None or asgname is None:
            raise SyntaxError('Either environment or asgname has not been specified')
        request_endpoint = '/api/v1/asgs/%s/launch-config?environment=%s' % (asgname, environment)
        return self.query(query_endpoint=request_endpoint, query_type='PUT', data=data, **kwargs)

    ## Audit
    def get_audit_config(self, since=None, until=None, **kwargs):
        """ Get Audit Logs for a given time period. Default values are 'since yesterday' and 'until now' """
        if since is None:
            since_qs = ''
        else:
            since_qs = 'since=%s' % since
        if until is None:
            until_qs = ''
        else:
            until_qs = 'until=%s' % until
        # Construct qs
        if since is None and until is not None:
            constructed_qs = '?%s' % until_qs
        elif since is not None and until is None:
            constructed_qs = '?%s' % since_qs
        elif since is not None and until is not None:
            constructed_qs = '?%s&%s' % (since_qs, until_qs)
        else:
            constructed_qs = ''
        request_endpoint = '/api/v1/config/audit%s' % constructed_qs
        return self.query(query_endpoint=request_endpoint, query_type='GET', **kwargs)

    def get_audit_key_config(self, key=None, **kwargs):
        """ Get a specific audit log """
        if key is None:
            raise SyntaxError('Key has not been specified')
        request_endpoint = '/api/v1/config/audit/%s' % key
        return self.query(query_endpoint=request_endpoint, query_type='GET', **kwargs)

    ## Cluster
    def get_clusters_config(self, **kwargs):
        """ Get all Cluster configurations """
        request_endpoint = '/api/v1/config/clusters'
        return self.query(query_endpoint=request_endpoint, query_type='GET', **kwargs)

    def post_clusters_config(self, data={}, **kwargs):
        """ Create a Cluster configuration """
        request_endpoint = '/api/v1/config/clusters'
        return self.query(query_endpoint=request_endpoint, query_type='POST', data=data, **kwargs)

    def get_cluster_config(self, cluster=None, **kwargs):
        """ Get a specific Cluster configuration """
        if cluster is None:
            raise SyntaxError('Cluster name has not been specified')
        request_endpoint = '/api/v1/config/clusters/%s' % cluster
        return self.query(query_endpoint=request_endpoint, query_type='GET', **kwargs)

    def put_cluster_config(self, cluster=None, data={}, **kwargs):
        """ Update a Cluster configuration """
        if cluster is None:
            raise SyntaxError('Cluster name has not been specified')
        request_endpoint = '/api/v1/config/clusters/%s' % cluster
        return self.query(query_endpoint=request_endpoint, query_type='PUT', data=data, **kwargs)

    def delete_cluster_config(self, cluster=None, **kwargs):
        """ Delete a Cluster configuration """
        if cluster is None:
            raise SyntaxError('Cluster name has not been specified')
        request_endpoint = '/api/v1/config/clusters/%s' % cluster
        return self.query(query_endpoint=request_endpoint, query_type='DELETE', **kwargs)

    ## Deployment
    def get_deployments(self, query_args=None, **kwargs):
        """ List all deployments matching the given criteria. If no parameters are provided, the default is 'since yesterday' """
        request_endpoint = '/api/v1/deployments'
        if query_args is not None:
            q = [ '{0}={1}'.format(key, val) for key,val in query_args.items() ]
            q = '&'.join(q)
            request_endpoint = '{0}?{1}'.format(request_endpoint, q)
        return self.query(query_endpoint=request_endpoint, query_type='GET', **kwargs)

    def post_deployments(self, dry_run=False, data={}, **kwargs):
        """ Create a new deployment. This will provision any required infrastructure and update the required target-state """
        request_endpoint = '/api/v1/deployments?dry_run=%s' % dry_run
        return self.query(query_endpoint=request_endpoint, query_type='POST', data=data, **kwargs)

    def get_deployment(self, deployment_id=None, **kwargs):
        """ Get information for a deployment """
        if deployment_id is None:
            raise SyntaxError('Deployment id has not been specified')
        request_endpoint = '/api/v1/deployments/%s' % deployment_id
        return self.query(query_endpoint=request_endpoint, query_type='GET', **kwargs)

    def patch_deployment(self, deployment_id=None, data={}, **kwargs):
        """ Modify deployment - cancel in-progress, or modify Action """
        if deployment_id is None:
            raise SyntaxError('Deployment id has not been specified')
        request_endpoint = '/api/v1/deployments/%s' % deployment_id
        return self.query(query_endpoint=request_endpoint, query_type='PATCH', data=data, **kwargs)

    def get_deployment_log(self, deployment_id=None, account='Non-Prod', instance=None, **kwargs):
        """ Retrieve logs for a particular deployment """
        if deployment_id is None:
            raise SyntaxError('Deployment id has not been specified')
        if instance is None:
            raise SyntaxError('Instance id has not been specified')
        request_endpoint = '/api/v1/deployments/%s/log?account=%s&instance=%s' % (deployment_id, account, instance)
        return self.query(query_endpoint=request_endpoint, query_type='GET', **kwargs)

    ## Deployment Map
    def get_deployment_maps(self, **kwargs):
        """ Get all deployment map configurations """
        request_endpoint = '/api/v1/config/deployments-maps'
        return self.query(query_endpoint=request_endpoint, query_type='GET', **kwargs)

    def post_deployment_maps(self, data={}, **kwargs):
        """ Create a deployment map configuration """
        request_endpoint = '/api/v1/config/deployments-maps'
        return self.query(query_endpoint=request_endpoint, query_type='POST', data=data, **kwargs)

    def get_deployment_map(self, deployment_name=None, **kwargs):
        """ Get a specific deployment map configuration """
        if deployment_name is None:
            raise SyntaxError('Deployment name has not been specified')
        request_endpoint = '/api/v1/deployment-maps/%s' % deployment_name
        return self.query(query_endpoint=request_endpoint, query_type='GET', **kwargs)

    def put_deployment_map(self, deployment_name=None, expected_version=None, data={}, **kwargs):
        """ Update a deployment map configuration """
        if deployment_name is None:
            raise SyntaxError('Deployment name has not been specified')
        if expected_version is None:
            headers = ''
        else:
            headers = {'expected-version':expected_version}
        request_endpoint = '/api/v1/deployment-maps/%s' % deployment_name
        return self.query(query_endpoint=request_endpoint, query_type='PUT', headers=headers, data=data, **kwargs)

    def delete_deployment_map(self, deployment_name=None, **kwargs):
        """ Delete a deployment map configuration """
        if deployment_name is None:
            raise SyntaxError('Deployment name has not been specified')
        request_endpoint = '/api/v1/deployment-maps/%s' % deployment_name
        return self.query(query_endpoint=request_endpoint, query_type='DELETE', **kwargs)

    ## Environment
    def get_environments(self, **kwargs):
        """ Get all environments """
        request_endpoint = '/api/v1/environments'
        return self.query(query_endpoint=request_endpoint, query_type='GET', **kwargs)

    def get_environment(self, environment=None, **kwargs):
        """ Get an environment """
        if environment is None:
            raise SyntaxError('Environment has not been specified')
        request_endpoint = '/api/v1/environments/%s' % environment
        return self.query(query_endpoint=request_endpoint, query_type='GET', **kwargs)

    def get_environment_protected(self, environment=None, action=None, **kwargs):
        """ Find if environment is protected from action """
        if environment is None or action is None:
            raise SyntaxError('Environment or Action has not been specified')
        request_endpoint = '/api/v1/environments/%s/protected?action=%s' % (environment, action)
        return self.query(query_endpoint=request_endpoint, query_type='GET', **kwargs)

    def get_environment_servers(self, environment=None, **kwargs):
        """ Get the list of servers in an environment """
        if environment is None:
            raise SyntaxError('Environment has not been specified')
        request_endpoint = '/api/v1/environments/%s/servers' % environment
        return self.query(query_endpoint=request_endpoint, query_type='GET', **kwargs)

    def get_environment_asg_servers(self, environment=None, asgname=None, **kwargs):
        """ Get a specific server in a given environment """
        if environment is None or asgname is None:
            raise SyntaxError('Either environment or asgname has not been specified')
        request_endpoint = '/api/v1/environments/%s/servers/%s' % (environment, asgname)
        return self.query(query_endpoint=request_endpoint, query_type='GET', **kwargs)

    def get_environment_schedule(self, environment=None, **kwargs):
        """ Get schedule for an environment """
        if environment is None:
            raise SyntaxError('Environment has not been specified')
        request_endpoint = '/api/v1/environments/%s/schedule' % environment
        return self.query(query_endpoint=request_endpoint, query_type='GET', **kwargs)

    def put_environment_schedule(self, environment=None, expected_version=None, data={}, **kwargs):
        """ Set the schedule for an environment """
        if environment is None:
            raise SyntaxError('Environment has not been specified')
        if expected_version is None:
            headers = None
        else:
            headers = {'expected-version':expected_version}
        request_endpoint = '/api/v1/environments/%s/schedule' % environment
        return self.query(query_endpoint=request_endpoint, query_type='PUT', headers=headers, data=data, **kwargs)

    def get_environment_account_name(self, environment=None, **kwargs):
        """ Get account name for given environment """
        if environment is None:
            raise SyntaxError('Environment has not been specified')
        request_endpoint = '/api/v1/environments/%s/accountName' % environment
        return self.query(query_endpoint=request_endpoint, query_type='GET', **kwargs)

    def get_environment_schedule_status(self, environment=None, at_time=None, **kwargs):
        """ Get the schedule status for a given environment at a given time. If no 'at' parameter is provided, the current status is returned """
        if environment is None:
            raise SyntaxError('Environment has not been specified')
        if at_time is None:
            at_qs = ''
        else:
            at_qs = '?at=%s' % at_time
        request_endpoint = '/api/v1/environments/%s/schedule-status%s' % (environment, at_qs)
        return self.query(query_endpoint=request_endpoint, query_type='GET', **kwargs)

    def get_environments_config(self, environmenttype=None, cluster=None, **kwargs):
        """ Get all environment configurations """
        if environmenttype is None:
            environmenttype_qs = ''
        else:
            environmenttype_qs = 'environmentType=%s' % environmenttype
        if cluster is None:
            cluster_qs = ''
        else:
            cluster_qs = 'cluster=%s' % cluster
        # Construct qs
        if environmenttype is None and cluster is not None:
            constructed_qs = '?%s' % cluster_qs
        elif environmenttype is not None and cluster is None:
            constructed_qs = '?%s' % environmenttype_qs
        elif environmenttype is not None and cluster is not None:
            constructed_qs = '?%s&%s' % (environmenttype_qs, cluster_qs)
        else:
            constructed_qs = ''
        request_endpoint = '/api/v1/config/environments%s' % constructed_qs
        return self.query(query_endpoint=request_endpoint, query_type='GET', **kwargs)

    def post_environments_config(self, data={}, **kwargs):
        """ Create a new environment configuration """
        request_endpoint = '/api/v1/config/environments'
        return self.query(query_endpoint=request_endpoint, query_type='POST', data=data, **kwargs)

    def get_environment_config(self, environment=None, **kwargs):
        """ Get a specific environment configuration """
        if environment is None:
            raise SyntaxError('Environment has not been specified')
        request_endpoint = '/api/v1/config/environments/%s' % environment
        return self.query(query_endpoint=request_endpoint, query_type='GET', **kwargs)

    def put_environment_config(self, environment=None, expected_version=None, data={}, **kwargs):
        """ Update an environment configuration """
        if environment is None:
            raise SyntaxError('Environment has not been specified')
        if expected_version is None:
            headers = ''
        else:
            headers = {'expected-version':expected_version}
        request_endpoint = '/api/v1/config/environments/%s' % environment
        return self.query(query_endpoint=request_endpoint, query_type='PUT', headers=headers, data=data, **kwargs)

    def delete_environment_config(self, environment=None, **kwargs):
        """ Delete an environment configuration """
        if environment is None:
            raise SyntaxError('Environment has not been specified')
        request_endpoint = '/api/v1/config/environments/%s' % environment
        return self.query(query_endpoint=request_endpoint, query_type='DELETE', **kwargs)

    ## Environment Type
    def get_environmenttypes_config(self, **kwargs):
        """ Get all environment type configurations """
        request_endpoint = '/api/v1/config/environment-types'
        return self.query(query_endpoint=request_endpoint, query_type='GET', **kwargs)

    def post_environmenttypes_config(self, data={}, **kwargs):
        """ Create an Environment Type configuration """
        request_endpoint = '/api/v1/config/environment-types'
        return self.query(query_endpoint=request_endpoint, query_type='POST', data=data, **kwargs)

    def get_environmenttype_config(self, environmenttype=None, **kwargs):
        """ Get an specific environment type configuration """
        if environmenttype is None:
            raise SyntaxError('Environment type has not been specified')
        request_endpoint = '/api/v1/config/environment-types/%s' % environmenttype
        return self.query(query_endpoint=request_endpoint, query_type='GET', **kwargs)

    def put_environmenttype_config(self, environmenttype=None, expected_version=None, data={}, **kwargs):
        """ Update an environment type configuration """
        if environmenttype is None:
            raise SyntaxError('Environment type has not been specified')
        if expected_version is None:
            headers = ''
        else:
            headers = {'expected-version':expected_version}
        request_endpoint = '/api/v1/config/environment-types/%s' % environmenttype
        return self.query(query_endpoint=request_endpoint, query_type='PUT', headers=headers, data=data, **kwargs)

    def delete_environmenttype_config(self, environmenttype=None, **kwargs):
        """ Delete an environment type """
        if environmenttype is None:
            raise SyntaxError('Environment type has not been specified')
        request_endpoint = '/api/v1/config/environment-types/%s' % environmenttype
        return self.query(query_endpoint=request_endpoint, query_type='DELETE', **kwargs)

    ## Export
    def export_resource(self, resource=None, account=None, **kwargs):
        """ Export a configuration resources dynamo table """
        if resource is None or account is None:
            raise SyntaxError('Resource or account has not been specified')
        request_endpoint = '/api/v1/config/export/%s?account=%s' % (resource, account)
        return self.query(query_endpoint=request_endpoint, query_type='GET', **kwargs)

    ## Import
    def import_resource(self, resource=None, account=None, mode=None, data={}, **kwargs):
        """ Import a configuration resources dynamo table """
        if resource is None or account is None or mode is None:
            raise SyntaxError('Resource or account has not been specified')
        request_endpoint = '/api/v1/config/import/%s?account=%s&mode=%s' % (resource, account, mode)
        return self.query(query_endpoint=request_endpoint, query_type='PUT', data=data, **kwargs)

    ## Instance
    def get_instances(self, environment=None, cluster=None, account=None, **kwargs):
        """ Get all instances matching the given criteria """
        request_endpoint = '/api/v1/instances'
        queries = []
        if environment is not None:
            queries.append('environment={0}'.format(environment))
        if cluster is not None:
            queries.append('cluster={0}'.format(cluster))
        if account is not None:
            queries.append('account={0}'.format(account))
        if queries:
            request_endpoint += '?{0}'.format('&'.join(queries))
        return self.query(query_endpoint=request_endpoint, query_type='GET', **kwargs)

    def get_instance(self, instance_id=None, **kwargs):
        """ Get a specific instance """
        if instance_id is None:
            raise SyntaxError('Instance id has not been specified')
        request_endpoint = '/api/v1/instances/%s' % instance_id
        return self.query(query_endpoint=request_endpoint, query_type='GET', **kwargs)

    def get_instance_connect(self, instance_id=None, **kwargs):
        """ Connect to the instance via remote desktop """
        if instance_id is None:
            raise SyntaxError('Instance id has not been specified')
        request_endpoint = '/api/v1/instances/%s/connect' % instance_id
        return self.query(query_endpoint=request_endpoint, query_type='GET', **kwargs)

    def put_instance_maintenance(self, instance_id=None, data={}, **kwargs):
        """ Update the ASG standby-state of a given instance """
        if instance_id is None:
            raise SyntaxError('Instance id has not been specified')
        request_endpoint = '/api/v1/instances/%s/maintenance' % instance_id
        return self.query(query_endpoint=request_endpoint, query_type='PUT', **kwargs)

    ## Load Balancers
    def get_loadbalancer(self, id=id, **kwargs):
        """ Get load balancer data """
        if id is None:
            raise SyntaxError('Load Balancer ID has not been specified')
        request_endpoint = '/api/v1/load-balancer/%s' % id
        return self.query(query_endpoint=request_endpoint, query_type='GET', **kwargs)

    def get_lbsettings_config(self, query_type=None, query_value=None, **kwargs):
        """ List all load balancer settings """
        if query_type and query_value:
            if query_type.lower() not in ['environment', 'load-balancer-group']:
                raise SyntaxError('query_type must be either environment or load-balancer-group')
            query_value = to_list(query_value)
            if not isinstance(query_value, list):
                raise SyntaxError('query_value must be an array')
            request_endpoint = '/api/v1/config/lb-settings?qa=%s&qv=%s' % (query_type.lower(), ','.join(query_value))
        else:
            request_endpoint = '/api/v1/config/lb-settings'
        return self.query(query_endpoint=request_endpoint, query_type='GET', **kwargs)

    def post_lbsettings_config(self, data={}, **kwargs):
        """ Create a load balancer setting """
        request_endpoint = '/api/v1/config/lb-settings'
        return self.query(query_endpoint=request_endpoint, query_type='POST', data=data, **kwargs)

    def get_lbsettings_vhost_config(self, environment=None, vhostname=None, **kwargs):
        """ Get a specific load balancer setting """
        if environment is None:
            raise SyntaxError('Environment has not been specified')
        if vhostname is None:
            raise SyntaxError('Virtual Host Name (vhostname) has not been specified')
        request_endpoint = '/api/v1/config/lb-settings/%s/%s' % (environment, vhostname)
        return self.query(query_endpoint=request_endpoint, query_type='GET', **kwargs)

    def put_lbsettings_vhost_config(self, environment=None, vhostname=None, expected_version=None, data={}, **kwargs):
        """ Update a load balancer setting """
        if environment is None:
            raise SyntaxError('Environment has not been specified')
        if vhostname is None:
            raise SyntaxError('Virtual Host Name (vhostname) has not been specified')
        if expected_version is None:
            headers = ''
        else:
            headers = {'expected-version':expected_version}
        request_endpoint = '/api/v1/config/lb-settings/%s/%s' % (environment, vhostname)
        return self.query(query_endpoint=request_endpoint, query_type='PUT', headers=headers, data=data, **kwargs)

    def delete_lbsettings_vhost_config(self, environment=None, vhostname=None, **kwargs):
        """ Delete an load balancer setting """
        if environment is None:
            raise SyntaxError('Environment has not been specified')
        if vhostname is None:
            raise SyntaxError('Virtual Host Name (vhostname) has not been specified')
        request_endpoint = '/api/v1/config/lb-settings/%s/%s' % (environment, vhostname)
        return self.query(query_endpoint=request_endpoint, query_type='DELETE', **kwargs)

    ## Notifications
    def get_notificationsettings_config(self, **kwargs):
        """ List Notification settings """
        request_endpoint = '/api/v1/config/notification-settings'
        return self.query(query_endpoint=request_endpoint, query_type='GET', **kwargs)

    def post_notificationsettings_config(self, data={}, **kwargs):
        """ Post new Notification settings """
        request_endpoint = '/api/v1/config/notification-settings'
        return self.query(query_endpoint=request_endpoint, query_type='POST', data=data, **kwargs)

    def get_notificationsetting_config(self, notification_id=None, **kwargs):
        """ Get Notification settings """
        if notification_id is None:
            raise SyntaxError('Notification id has not been specified')
        request_endpoint = '/api/v1/notification-settings/%s' % notification_id
        return self.query(query_endpoint=request_endpoint, query_type='GET', **kwargs)

    def put_notificationsetting_config(self, notification_id=None, expected_version=None, data={}, **kwargs):
        """ Update an associated AWS Account """
        if notification_id is None:
            raise SyntaxError('Notification id has not been specified')
        if expected_version is None:
            headers = ''
        else:
            headers = {'expected-version':expected_version}
        request_endpoint = '/api/v1/notification-settings/%s' % notification_id
        return self.query(query_endpoint=request_endpoint, query_type='PUT', headers=headers, data=data, **kwargs)

    def delete_notificationsetting_config(self, notification_id=None, **kwargs):
        """ Remove Notification settings """
        if notification_id is None:
            raise SyntaxError('Notification id has not been specified')
        request_endpoint = '/api/v1/notification-settings/%s' % notification_id
        return self.query(query_endpoint=request_endpoint, query_type='DELETE', **kwargs)

    ## Upload Package
    # TODO Slice
    def get_package_upload_url_environment(self, service=None, version=None, environment=None, **kwargs):
        """ Upload an environment-specific package """
        if service is None or version is None or environment is None:
            raise SyntaxError('Parameter has not been specified')
        request_endpoint = '/api/v1/package-upload-url/%s/%s/%s' % (service, version, environment)
        return self.query(query_endpoint=request_endpoint, query_type='GET', **kwargs)

    def get_package_upload_url(self, service=None, version=None, **kwargs):
        """ Upload an environment-independent package """
        if service is None or version is None:
            raise SyntaxError('Parameter has not been specified')
        request_endpoint = '/api/v1/package-upload-url/%s/%s' % (service, version)
        return self.query(query_endpoint=request_endpoint, query_type='GET', **kwargs)

    ## Permissions
    def get_permissions_config(self, **kwargs):
        """ Get all permission configurations """
        request_endpoint = '/api/v1/config/permissions'
        return self.query(query_endpoint=request_endpoint, query_type='GET', **kwargs)

    def post_permissions_config(self, data={}, **kwargs):
        """ Create a new permission configuration"""
        request_endpoint = '/api/v1/config/permissions'
        return self.query(query_endpoint=request_endpoint, query_type='POST', data=data, **kwargs)

    def get_permission_config(self, name=None, **kwargs):
        """ Get a specific permission configuration """
        if name is None:
            raise SyntaxError('Permission name has not been specified')
        request_endpoint = '/api/v1/config/permissions/%s' % name
        return self.query(query_endpoint=request_endpoint, query_type='GET', **kwargs)

    def put_permission_config(self, name=None, expected_version=None, data={}, **kwargs):
        """ Update a permission configuration """
        if name is None:
            raise SyntaxError('Permission name has not been specified')
        if expected_version is None:
            headers = ''
        else:
            headers = {'expected-version':expected_version}
        request_endpoint = '/api/v1/config/permissions/%s' % name
        return self.query(query_endpoint=request_endpoint, query_type='PUT', headers=headers, data=data, **kwargs)

    def delete_permission_config(self, name=None, **kwargs):
        """ Delete a permissions configuration """
        if name is None:
            raise SyntaxError('Permission name has not been specified')
        request_endpoint = '/api/v1/config/permissions/%s' % name
        return self.query(query_endpoint=request_endpoint, query_type='DELETE', **kwargs)

    ## Service
    def get_services(self, **kwargs):
        """ Get the list of currently deployed services """
        request_endpoint = '/api/v1/services'
        return self.query(query_endpoint=request_endpoint, query_type='GET', **kwargs)

    def get_service(self, service=None, **kwargs):
        """ Get a currently deployed service """
        if service is None:
            raise SyntaxError('Service has not been specified')
        request_endpoint = '/api/v1/services/%s' % service
        return self.query(query_endpoint=request_endpoint, query_type='GET', **kwargs)

    def get_service_asgs(self, service=None, environment=None, slice=None, **kwargs):
        """ Get the ASGs to which a service is deployed """
        if service is None:
            raise SyntaxError('Service has not been specified')
        if environment is None:
            raise SyntaxError('Environment has not been specified')
        if slice is None:
            slice_qs = ''
        else:
            slice_qs = '&slice=%s' % slice
        request_endpoint = '/api/v1/services/%s/asgs?environment=%s%s' % (service, environment, slice_qs)
        return self.query(query_endpoint=request_endpoint, query_type='GET', **kwargs)

    def get_service_overall_health(self, service=None, environment=None, **kwargs):
        """ Get a overall health for a deployed service """
        if service is None:
            raise SyntaxError('Service has not been specified')
        if environment is None:
            raise SyntaxError('Environment has not been specified')
        request_endpoint = '/api/v1/services/%s/health?environment=%s' % (service, environment)
        return self.query(query_endpoint=request_endpoint, query_type='GET', **kwargs)

    def get_service_health(self, service=None, environment=None, slice=None, server_role=None, **kwargs):
        """ Get health for a specific service """
        if service is None:
            raise SyntaxError('Service has not been specified')
        if environment is None:
            raise SyntaxError('Environment has not been specified')
        if slice is None:
            raise SyntaxError('Slice has not been specified')
        request_endpoint = '/api/v1/services/%s/health/%s?environment=%s' % (service, slice, environment)
        if server_role is not None:
            request_endpoint = '%s&serverRole=%s' % (request_endpoint, server_role)
        return self.query(query_endpoint=request_endpoint, query_type='GET', **kwargs)

    def get_service_slices(self, service=None, environment=None, active=None, **kwargs):
        """ Get slices for a deployed service """
        if service is None:
            raise SyntaxError('Service has not been specified')
        if environment is None:
            raise SyntaxError('Environment has not been specified')
        request_endpoint = '/api/v1/services/%s/slices?environment=%s' % (service, environment)
        if active is not None:
            request_endpoint = '%s&active=%s' % (request_endpoint, active)
        return self.query(query_endpoint=request_endpoint, query_type='GET', **kwargs)

    def put_service_slices_toggle(self, service=None, environment=None, **kwargs):
        """ Toggle the slices for a deployed service """
        if service is None:
            raise SyntaxError('Service has not been specified')
        if environment is None:
            raise SyntaxError('Environment has not been specified')
        request_endpoint = '/api/v1/services/%s/slices/toggle?environment=%s' % (service, environment)
        return self.query(query_endpoint=request_endpoint, query_type='PUT', **kwargs)

    def get_services_config(self, **kwargs):
        """ Get all service configurations """
        request_endpoint = '/api/v1/config/services'
        return self.query(query_endpoint=request_endpoint, query_type='GET', **kwargs)

    def post_services_config(self, data={}, **kwargs):
        """ Create a service configuration """
        request_endpoint = '/api/v1/config/services'
        return self.query(query_endpoint=request_endpoint, query_type='POST', data=data, **kwargs)

    def get_service_config(self, service=None, cluster=None, **kwargs):
        """ Get a specific service configuration """
        if service is None:
            raise SyntaxError('Service has not been specified')
        if cluster is None:
            raise SyntaxError('Cluster name (team) has not been specified')
        request_endpoint = '/api/v1/config/services/%s/%s' % (service, cluster)
        return self.query(query_endpoint=request_endpoint, query_type='GET', **kwargs)

    def put_service_config(self, service=None, cluster=None, expected_version=None, data={}, **kwargs):
        """ Update a service configuration """
        if service is None:
            raise SyntaxError('Service has not been specified')
        if cluster is None:
            raise SyntaxError('Cluster name (team) has not been specified')
        if expected_version is None:
            headers = ''
        else:
            headers = {'expected-version':expected_version}
        request_endpoint = '/api/v1/config/services/%s/%s' % (service, cluster)
        return self.query(query_endpoint=request_endpoint, query_type='POST', data=data, headers=headers, **kwargs)

    def delete_service_config(self, service=None, cluster=None, **kwargs):
        """ Delete a service configuration """
        if service is None:
            raise SyntaxError('Service has not been specified')
        if cluster is None:
            raise SyntaxError('Cluster name (team) has not been specified')
        request_endpoint = '/api/v1/config/services/%s/%s' % (service, cluster)
        return self.query(query_endpoint=request_endpoint, query_type='DELETE', **kwargs)

    ## Status
    def get_status(self, **kwargs):
        """ Get version and status information """
        request_endpoint = '/api/v1/diagnostics/healthcheck'
        return self.query(query_endpoint=request_endpoint, query_type='GET', **kwargs)

    ## Target State
    def get_target_state(self, environment=None, **kwargs):
        """ Get the target state for a given environment """
        if environment is None:
            raise SyntaxError('Environment has not been specified')
        request_endpoint = '/api/v1/target-state/%s' % environment
        return self.query(query_endpoint=request_endpoint, query_type='GET', **kwargs)

    def delete_target_state(self, environment=None, **kwargs):
        """ Remove the target state for all services in a given environment """
        if environment is None:
            raise SyntaxError('Environment has not been specified')
        request_endpoint = '/api/v1/target-state/%s' % environment
        return self.query(query_endpoint=request_endpoint, query_type='DELETE', **kwargs)

    def delete_target_state_service(self, environment=None, service=None, **kwargs):
        """ Remove the target state for all versions of a service """
        if environment is None or service is None:
            raise SyntaxError('Environment or Service has not been specified')
        request_endpoint = '/api/v1/target-state/%s/%s' % (environment, service)
        return self.query(query_endpoint=request_endpoint, query_type='DELETE', **kwargs)

    def delete_target_state_service_version(self, environment=None, service=None, version=None, **kwargs):
        """ Remove the target state for a specific version of a service """
        if environment is None or service is None or version is None:
            raise SyntaxError('Environment or Service has not been specified')
        request_endpoint = '/api/v1/target-state/%s/%s/%s' % (environment, service, version)
        return self.query(query_endpoint=request_endpoint, query_type='DELETE', **kwargs)

    ## Upstream
    def get_upstream_slices(self, upstream=None, environment=None, **kwargs):
        """ Get slices for a given upstream """
        if upstream is None or environment is None:
            raise SyntaxError('You must provide an upstream and environment')
        request_endpoint = '/api/v1/upstreams/%s/slices?environment=%s' % (upstream, environment)
        return self.query(query_endpoint=request_endpoint, query_type='GET', **kwargs)

    def put_upstream_slices_toggle(self, upstream=None, environment=None, **kwargs):
        """ Toggle the slices for a given upstream """
        if upstream is None or environment is None:
            raise SyntaxError('Upstream name or Service name has not been specified')
        request_endpoint = '/api/v1/upstreams/%s/slices/toggle?environment=%s' % (upstream, environment)
        return self.query(query_endpoint=request_endpoint, query_type='PUT', **kwargs)

    def get_upstreams_config(self, query_type=None, query_value=None, **kwargs):
        """ Get all upstream configurations """
        if query_type and query_value:
            if query_type.lower() not in ['environment', 'load-balancer-group']:
                raise SyntaxError('query_type must be either environment or load-balancer-group')
            query_value = to_list(query_value)
            if not isinstance(query_value, list):
                raise SyntaxError('query_value must be an array')
            request_endpoint = '/api/v1/config/upstreams?qa=%s&qv=%s' % (query_type.lower(), ','.join(query_value))
        else:
            request_endpoint = '/api/v1/config/upstreams'
        return self.query(query_endpoint=request_endpoint, query_type='GET', **kwargs)

    def post_upstreams_config(self, data={}, **kwargs):
        """ Create an upstream configuration """
        request_endpoint = '/api/v1/config/upstreams'
        return self.query(query_endpoint=request_endpoint, query_type='POST', data=data, **kwargs)

    def get_upstream_config(self, upstream=None, account='Non-Prod', **kwargs):
        """ Get an a specific upstream configuration """
        if upstream is None:
            raise SyntaxError('Upstream name has not been specified')
        request_endpoint = '/api/v1/config/upstreams/%s?account=%s' % (upstream, account)
        return self.query(query_endpoint=request_endpoint, query_type='GET', **kwargs)

    def put_upstream_config(self, upstream=None, expected_version=None, data={}, **kwargs):
        """ Update an upstream configuration """
        if upstream is None:
            raise SyntaxError('Upstream name has not been specified')
        if expected_version is None:
            headers = ''
        else:
            headers = {'expected-version':expected_version}
        request_endpoint = '/api/v1/config/upstreams/%s' % upstream
        return self.query(query_endpoint=request_endpoint, query_type='PUT', headers=headers, data=data, **kwargs)

    def delete_upstream_config(self, upstream=None, account='Non-Prod', **kwargs):
        """ Delete an upstream configuration """
        if upstream is None:
            raise SyntaxError('Upstream name has not been specified')
        request_endpoint = '/api/v1/config/upstreams/%s?account=%s' % (upstream, account)
        return self.query(query_endpoint=request_endpoint, query_type='DELETE', **kwargs)
