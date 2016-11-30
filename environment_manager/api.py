""" Copyright (c) Trainline Limited, 2016. All rights reserved. See LICENSE.txt in the project root for license information. """
# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4

import time
import requests
from environment_manager.utils import LogWrapper, json_encode

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

    def query(self, query_endpoint=None, data=None, query_type='get', retries=5, backoff=2):
        """ Function to querying Environment Manager """
        log = LogWrapper()
        if query_endpoint is None:
            log.info('No endpoint specified, cant just go and query nothing')
            raise SyntaxError('No endpoint specified, cant just go and query nothing')
        if query_type.lower() == 'put' or query_type.lower() == 'post':
            if data is None:
                log.info('No data specified, we need to send data with method %s' % query_type)
                raise SyntaxError('No data specified, we need to send data with method %s' % query_type)
            else:
                json_data = json_encode(data)
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
            query_headers = {'Accept': 'application/json', 'Content-Type': 'application/json', 'Authorization': token}
            if query_type.lower() == 'get':
                request = requests.get(request_url, headers=query_headers, timeout=30, verify=False)
            if query_type.lower() == 'post':
                request = requests.post(request_url, headers=query_headers, data=json_data, timeout=30, verify=False)
            if query_type.lower() == 'put':
                request = requests.put(request_url, headers=query_headers, data=json_data, timeout=30, verify=False)
            if query_type.lower() == 'delete':
                request = requests.delete(request_url, headers=query_headers, timeout=30, verify=False)
            else:
                raise SyntaxError('Cannot process query type %s' % query_type)
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
    def get_accounts_config(self, **kwargs):
        """ Get config of accounts associated with EM """
        request_endpoint = '/api/v1/config/accounts'
        return self.query(query_endpoint=request_endpoint, query_type='GET', **kwargs)

    ## AMI
    def get_images_config(self, account=None, **kwargs):
        """ Get config of AMI images registered in EM """
        if account is None:
            account_qs = ''
        else:
            account_qs = '?account=%s' % account
        request_endpoint = '/api/v1/config/images%s' % account_qs
        return self.query(query_endpoint=request_endpoint, query_type='GET', **kwargs)

    ## ASG
    def get_asgs(self, account='Non-Prod', **kwargs):
        """ Get list of ASGs from EM """
        request_endpoint = '/api/v1/asgs?account=%s' % account
        return self.query(query_endpoint=request_endpoint, query_type='GET', **kwargs)

    def get_asg_info(self, environment=None, asgname=None, **kwargs):
        """ Get details from ASG """
        if environment is None or asgname is None:
            raise SyntaxError('Either environment or asgname has not been specified')
        request_endpoint = '/api/v1/asgs/%s?environment=%s' % (asgname, environment)
        return self.query(query_endpoint=request_endpoint, query_type='GET', **kwargs)

    def get_asg_ips(self, environment=None, asgname=None, **kwargs):
        """ Get IPs associated with ASG """
        if environment is None or asgname is None:
            raise SyntaxError('Either environment or asgname has not been specified')
        request_endpoint = '/api/v1/asgs/%s/ips?environment=%s' % (asgname, environment)
        return self.query(query_endpoint=request_endpoint, query_type='GET', **kwargs)

    def get_asg_scaling_schedule(self, environment=None, asgname=None, **kwargs):
        """ Get scaling schedule associated with ASG """
        if environment is None or asgname is None:
            raise SyntaxError('Either environment or asgname has not been specified')
        request_endpoint = '/api/v1/asgs/%s/scaling-schedule?environment=%s' % (asgname, environment)
        return self.query(query_endpoint=request_endpoint, query_type='GET', **kwargs)

    def get_asg_launch_config(self, environment=None, asgname=None, **kwargs):
        """ Get scaling schedule associated with ASG """
        if environment is None or asgname is None:
            raise SyntaxError('Either environment or asgname has not been specified')
        request_endpoint = '/api/v1/asgs/%s/launch-config?environment=%s' % (asgname, environment)
        return self.query(query_endpoint=request_endpoint, query_type='GET', **kwargs)

    ## Audit
    def get_audit_config(self, since=None, until=None, **kwargs):
        """ Get audit config from EM """
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
        if since is not None and until is None:
            constructed_qs = '?%s' % since_qs
        if since is not None and until is not None:
            constructed_qs = '?%s,%s' % (since_qs, until_qs)
        if since is None and until is None:
            constructed_qs = ''
        request_endpoint = '/api/v1/config/audit%s' % constructed_qs
        return self.query(query_endpoint=request_endpoint, query_type='GET', **kwargs)

    def get_audit_key_config(self, key=None, **kwargs):
        """ Get audit config for specific key """
        if key is None:
            raise SyntaxError('Key has not been specified')
        request_endpoint = '/api/v1/config/audit/%s' % key
        return self.query(query_endpoint=request_endpoint, query_type='GET', **kwargs)

    ## Cluster
    def get_clusters_config(self, **kwargs):
        """ Get config of clusters (teams) registered in EM """
        request_endpoint = '/api/v1/config/clusters'
        return self.query(query_endpoint=request_endpoint, query_type='GET', **kwargs)

    def get_cluster_config(self, cluster=None, **kwargs):
        """ Get EM config for cluster (team) """
        if cluster is None:
            raise SyntaxError('Cluster name has not been specified')
        request_endpoint = '/api/v1/config/clusters/%s' % cluster
        return self.query(query_endpoint=request_endpoint, query_type='GET', **kwargs)

    ## Deployment
    def get_deployments(self, **kwargs):
        """ Get list of deployments registered in EM """
        request_endpoint = '/api/v1/deployments'
        return self.query(query_endpoint=request_endpoint, query_type='GET', **kwargs)

    def get_deployment(self, deployment_id=None, **kwargs):
        """ Get deployment information for one deployment """
        if deployment_id is None:
            raise SyntaxError('Deployment id has not been specified')
        request_endpoint = '/api/v1/deployments/%s' % deployment_id
        return self.query(query_endpoint=request_endpoint, query_type='GET', **kwargs)

    def get_deployment_log(self, deployment_id=None, account='Non-Prod', instance=None, **kwargs):
        """ Get deployment log for one deployment """
        if deployment_id is None:
            raise SyntaxError('Deployment id has not been specified')
        if instance is None:
            raise SyntaxError('Instance id has not been specified')
        request_endpoint = '/api/v1/deployments/%s/log?account=%s,instance=%s' % (deployment_id, account, instance)
        return self.query(query_endpoint=request_endpoint, query_type='GET', **kwargs)

    ## Deployment Map
    def get_deployment_maps(self, **kwargs):
        """ Get list of deployments maps in EM """
        request_endpoint = '/api/v1/config/deployments-maps'
        return self.query(query_endpoint=request_endpoint, query_type='GET', **kwargs)

    def get_deployment_map(self, deployment_name=None, **kwargs):
        """ Get deployment map config for one deployment """
        if deployment_name is None:
            raise SyntaxError('Deployment name has not been specified')
        request_endpoint = '/api/v1/deployment-maps/%s' % deployment_name
        return self.query(query_endpoint=request_endpoint, query_type='GET', **kwargs)

    ## Environment
    def get_environments(self, **kwargs):
        """ Get list of environments available in EM """
        request_endpoint = '/api/v1/environments'
        return self.query(query_endpoint=request_endpoint, query_type='GET', **kwargs)

    def get_environment(self, environment=None, **kwargs):
        """ Get config for environment """
        if environment is None:
            raise SyntaxError('Environment has not been specified')
        request_endpoint = '/api/v1/environments/%s' % environment
        return self.query(query_endpoint=request_endpoint, query_type='GET', **kwargs)

    def get_environment_servers(self, environment=None, **kwargs):
        """ Get list of servers in environment """
        if environment is None:
            raise SyntaxError('Environment has not been specified')
        request_endpoint = '/api/v1/environments/%s/servers' % environment
        return self.query(query_endpoint=request_endpoint, query_type='GET', **kwargs)

    def get_environment_asg_servers(self, environment=None, asgname=None, **kwargs):
        """ Get list of servers belonging to an environment ASG """
        if environment is None or asgname is None:
            raise SyntaxError('Either environment or asgname has not been specified')
        request_endpoint = '/api/v1/environments/%s/servers/%s' % (environment, asgname)
        return self.query(query_endpoint=request_endpoint, query_type='GET', **kwargs)

    def get_environment_schedule(self, environment=None, **kwargs):
        """ Get schedule for environment """
        if environment is None:
            raise SyntaxError('Environment has not been specified')
        request_endpoint = '/api/v1/environments/%s/schedule' % environment
        return self.query(query_endpoint=request_endpoint, query_type='GET', **kwargs)

    def get_environment_account_name(self, environment=None, **kwargs):
        """ Get account name for environment """
        if environment is None:
            raise SyntaxError('Environment has not been specified')
        request_endpoint = '/api/v1/environments/%s/accountName' % environment
        return self.query(query_endpoint=request_endpoint, query_type='GET', **kwargs)

    def get_environment_schedule_status(self, environment=None, at_time=None, **kwargs):
        """ Get schedule status for environment """
        if environment is None:
            raise SyntaxError('Environment has not been specified')
        if at_time is None:
            at_qs = ''
        else:
            at_qs = '?at=%s' % at_time
        request_endpoint = '/api/v1/environments/%s/schedule-status%s' % (environment, at_qs)
        return self.query(query_endpoint=request_endpoint, query_type='GET', **kwargs)

    def get_environments_config(self, environmenttype=None, cluster=None, **kwargs):
        """ Get config for all environments """
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
        if environmenttype is not None and cluster is None:
            constructed_qs = '?%s' % environmenttype_qs
        if environmenttype is not None and cluster is not None:
            constructed_qs = '?%s,%s' % (environmenttype_qs, cluster_qs)
        if environmenttype is None and cluster is None:
            constructed_qs = ''
        request_endpoint = '/api/v1/config/environments%s' % constructed_qs
        return self.query(query_endpoint=request_endpoint, query_type='GET', **kwargs)

    def get_environment_config(self, environment=None, **kwargs):
        """ Get environment config for specific environment """
        if environment is None:
            raise SyntaxError('Environment has not been specified')
        request_endpoint = '/api/v1/config/environments/%s' % environment
        return self.query(query_endpoint=request_endpoint, query_type='GET', **kwargs)

    ## Environment Type
    def get_environmenttypes_config(self, **kwargs):
        """ Get config for available environmentTypes in EM """
        request_endpoint = '/api/v1/config/environment-types'
        return self.query(query_endpoint=request_endpoint, query_type='GET', **kwargs)

    def get_environmenttype_config(self, environmenttype=None, **kwargs):
        """ Get config for one specific environmentType """
        if environmenttype is None:
            raise SyntaxError('Environment type has not been specified')
        request_endpoint = '/api/v1/config/environment-types/%s' % environmenttype
        return self.query(query_endpoint=request_endpoint, query_type='GET', **kwargs)

    ## Instance
    def get_instances(self, **kwargs):
        """ Get available environmentTypes in EM """
        request_endpoint = '/api/v1/instances'
        return self.query(query_endpoint=request_endpoint, query_type='GET', **kwargs)

    def get_instance(self, instance_id=None, **kwargs):
        """ Get config for one specific environmentType """
        if instance_id is None:
            raise SyntaxError('Instance id has not been specified')
        request_endpoint = '/api/v1/instances/%s' % instance_id
        return self.query(query_endpoint=request_endpoint, query_type='GET', **kwargs)

    ## Load Balancers
    def get_lbsettings_config(self, **kwargs):
        """ Get config of Load Balancer Services from EM """
        request_endpoint = '/api/v1/config/lb-settings'
        return self.query(query_endpoint=request_endpoint, query_type='GET', **kwargs)

    def get_lbsettings_vhost_config(self, environment=None, vhostname=None, **kwargs):
        """ Get Load Balancer vhostname config """
        if environment is None:
            raise SyntaxError('Environment has not been specified')
        if vhostname is None:
            raise SyntaxError('Virtual Host Name (vhostname) has not been specified')
        request_endpoint = '/api/v1/config/lb-settings/%s/%s' % (environment, vhostname)
        return self.query(query_endpoint=request_endpoint, query_type='GET', **kwargs)

    ## Permissions
    def get_permissions_config(self, **kwargs):
        """ Get permissions config from EM """
        request_endpoint = '/api/v1/config/permissions'
        return self.query(query_endpoint=request_endpoint, query_type='GET', **kwargs)

    def get_permission_config(self, name=None, **kwargs):
        """ Get specific permission config """
        if name is None:
            raise SyntaxError('Permission name has not been specified')
        request_endpoint = '/api/v1/config/permissions/%s' % name
        return self.query(query_endpoint=request_endpoint, query_type='GET', **kwargs)

    ## Service
    def get_services(self, **kwargs):
        """ Get list of Services from EM """
        request_endpoint = '/api/v1/services'
        return self.query(query_endpoint=request_endpoint, query_type='GET', **kwargs)

    def get_service(self, service=None, **kwargs):
        """ Get a currently deployed service """
        if service is None:
            raise SyntaxError('Service has not been specified')
        request_endpoint = '/api/v1/services/%s' % service
        return self.query(query_endpoint=request_endpoint, query_type='GET', **kwargs)

    def get_service_slices(self, service=None, **kwargs):
        """ Get a currently deployed service slices """
        if service is None:
            raise SyntaxError('Service has not been specified')
        request_endpoint = '/api/v1/services/%s/slices' % service
        return self.query(query_endpoint=request_endpoint, query_type='GET', **kwargs)

    def get_services_config(self, **kwargs):
        """ Get services config from EM """
        request_endpoint = '/api/v1/config/services'
        return self.query(query_endpoint=request_endpoint, query_type='GET', **kwargs)

    def get_service_config(self, service=None, cluster=None, **kwargs):
        """ Get service config for one specific service """
        if service is None:
            raise SyntaxError('Service has not been specified')
        if cluster is None:
            raise SyntaxError('Cluster name (team) has not been specified')
        request_endpoint = '/api/v1/config/services/%s/%s' % (service, cluster)
        return self.query(query_endpoint=request_endpoint, query_type='GET', **kwargs)

    ## Status
    def get_status(self, **kwargs):
        """ Get internal status of EM """
        request_endpoint = '/api/v1/diagnostics/healthcheck'
        return self.query(query_endpoint=request_endpoint, query_type='GET', **kwargs)

    ## Target State
    def get_target_state(self, environment=None, **kwargs):
        """ Get target state for specific environment """
        if environment is None:
            raise SyntaxError('Environment has not been specified')
        request_endpoint = '/api/v1/target-state/%s' % environment
        return self.query(query_endpoint=request_endpoint, query_type='GET', **kwargs)

    ## Upstream
    def get_upstream_slices(self, upstream=None, **kwargs):
        """ Get slices attached to upstream """
        if upstream is None:
            raise SyntaxError('Upstream name has not been specified')
        request_endpoint = '/api/v1/upstreams/%s/slices' % upstream
        return self.query(query_endpoint=request_endpoint, query_type='GET', **kwargs)

    def get_upstreams_config(self, **kwargs):
        """ Get config for Upstreams from EM """
        request_endpoint = '/api/v1/config/upstreams'
        return self.query(query_endpoint=request_endpoint, query_type='GET', **kwargs)

    def get_upstream_config(self, upstream=None, account='Non-Prod', **kwargs):
        """ Get config for specific upstream """
        if upstream is None:
            raise SyntaxError('Upstream name has not been specified')
        request_endpoint = '/api/v1/config/upstreams/%s?account=%s' % (upstream, account)
        return self.query(query_endpoint=request_endpoint, query_type='GET', **kwargs)
