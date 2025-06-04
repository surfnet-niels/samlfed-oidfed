##################################################################################################################################
#
# Object classes for various OIDFed Entities functions
#
##################################################################################################################################

import yaml

class tmo_config:
    def __init__(self):
        self.trust_mark_owner = None
        self.trust_marks = []

    def from_yaml(file_path):
        config = tmo_config()
        with open(file_path, 'r') as f:
            data = yaml.safe_load(f)
            if 'trust_mark_owner' in data:
                config.trust_mark_owner = data['trust_mark_owner']
            if 'trust_marks' in data:
                for trust_mark in data['trust_marks']:
                    tm = {}
                    if 'trust_mark_id' in trust_mark:
                        tm['trust_mark_id'] = trust_mark['trust_mark_id']
                    if 'delegation_lifetime' in trust_mark:
                        tm['delegation_lifetime'] = trust_mark['delegation_lifetime']
                    if 'logo_uri' in trust_mark:
                        tm['logo_uri'] = trust_mark['logo_uri']                        
                    if 'ref' in trust_mark:
                        tm['ref'] = trust_mark['ref']
                    if 'trust_mark_issuers' in trust_mark:
                        tm['trust_mark_issuers'] = trust_mark['trust_mark_issuers']

        return config
    
    def to_yaml(self, file_path):
        with open(file_path, 'w') as f:
            yaml.dump((self.__dict__), f)

    def get_trust_mark_owner(self):
        return self.trust_mark_owner

    def set_trust_mark_owner(self, trust_mark_owner):
        self.trust_mark_owner = trust_mark_owner

    def add_trust_mark(self, trust_mark_id, trust_mark_issuers, delegation_lifetime=86400, logo_uri=None, ref=None):
        tm = trustmark()
        tm.add(trust_mark_id, trust_mark_issuers, delegation_lifetime, logo_uri, ref)
        self.trust_marks.append(tm.asdict())

class trustmark:
    def __init__(self):
        self.trust_mark_id = None
        self.delegation_lifetime = None
        self.ref = []
        self.logo_uri=None
        self.trust_mark_issuers = None

    def asdict(self):
        d = {
            'trust_mark_id': self.trust_mark_id,
            'delegation_lifetime': self.delegation_lifetime,
            'ref': self.ref,
            'logo_uri': self.logo_uri
        }

        tmis = []
        for tmi in self.trust_mark_issuers:
            tmis.append({'entity_id': tmi})
        
        d['trust_mark_issuers'] = tmis

        return d

    def add(self, trust_mark_id, trust_mark_issuers, delegation_lifetime=86400, logo_uri=None, ref=None):
        self.trust_mark_id = trust_mark_id
        self.delegation_lifetime = delegation_lifetime
        self.logo_uri = logo_uri                        
        self.ref = ref
        self.trust_mark_issuers =[]
        for tmi in trust_mark_issuers:  
            self.trust_mark_issuers.append(tmi) 
        
    
    def set_delegation_lifetime(self, delegation_lifetime):
        self.delegation_lifetime = delegation_lifetime     

    def set_ref(self, ref):
        self.ref = ref

    def set_logo_uri(self, logo_uri):
        self.logo_uri = logo_uri

    def add_issuers(self, entity_id):
        self.trust_mark_issuers = []
        self.trust_mark_issuers.append({"entityid": entity_id})

class trust_mark_spec:
    def __init__(self):
        self.trust_mark_id = None
        self.lifetime = None
        self.ref = []
        self.logo_uri= None
        self.delegation_jwt = None
        self.checker = {}
        self.trust_anchors = []

    def asdict(self):
        d = {
                'trust_mark_id': self.trust_mark_id,
                'lifetime': self.lifetime,
                'ref': self.ref,
                'logo_uri': self.logo_uri,
                'checker': self.checker
            }
        
        if self.delegation_jwt != None:
            tas = []
            for ta in self.trust_anchors:
                tas.append({'entity_id': ta})
            
            checker = {
                'type': 'trust_path',
                'config': { 'trust_anchors': tas }
            }
            d.update({'checker': checker})
        else:
            d.update({'checker': self.checker})

        return d

    def set_trust_mark_id(self, trust_mark_id):
        self.trust_mark_id = trust_mark_id

    def set_lifetime(self, lifetime):
        self.lifetime = lifetime

    def set_ref(self, ref):
        self.ref = ref

    def set_logo_uri(self, logo_uri):
        self.logo_uri = logo_uri

    def set_delegation_jwt(self, delegation_jwt):
        self.delegation_jwt = delegation_jwt
 
    def add_checker(self, checker_type=None, trust_anchors=[]):
        if checker_type == 'trust_path':
            self.checker = {
                'type': 'trust_path',
                'config': { 'trust_anchors': [] }
            }
            for ta in trust_anchors:
                self.checker['config']['trust_anchors'].append({'entity_id': ta})
        else:
            self.checker = None

class ta_config:
    def __init__(self):
        self.server_port = None
        self.entity_id = None
        self.authority_hints = []
        self.signing_key_file = None
        self.organization_name = None
        self.data_location = None
        self.human_readable_storage = False
        self.metadata_policy_file = None
        self.endpoints = {}
        self.trust_mark_specs = []
        self.trust_marks = []
        self.trust_mark_owners = {}
        self.trust_mark_issuers = {}

    def from_yaml(file_path):
        config = ta_config()
        with open(file_path, 'r') as f:
            data = yaml.safe_load(f)
            if 'server_port' in data:
                config.server_port = data['server_port']
            if 'entity_id' in data:
                config.entity_id = data['entity_id']
            if 'authority_hints' in data:
                config.authority_hints = data['authority_hints']
            if 'signing_key_file' in data:
                config.signing_key_file = data['signing_key_file']
            if 'organization_name' in data:
                config.organization_name = data['organization_name']
            if 'data_location' in data:
                config.data_location = data['data_location']
            if 'human_readable_storage' in data:
                config.human_readable_storage = True
            if 'metadata_policy_file' in data:
                config.metadata_policy_file = data['metadata_policy_file']
            if 'endpoints' in data:
                for endpoint_name, endpoint_data in data['endpoints'].items():
                    config.endpoints[endpoint_name] = {'path': endpoint_data['path']}
            if 'trust_mark_specs' in data:
                for trust_mark_spec in data['trust_mark_specs']:
                    spec = trust_mark_spec()
                    if 'trust_mark_id' in trust_mark_spec:         
                        spec.set_trust_mark_id(trust_mark_spec['trust_mark_id'])
                    if 'lifetime' in trust_mark_spec:
                        spec.set_lifetime(trust_mark_spec['lifetime'])
                    if 'ref' in trust_mark_spec:
                        spec.set_ref(trust_mark_spec['ref'])
                    if 'delegation_jwt' in trust_mark_spec:
                        spec.set_delegation_jwt(trust_mark_spec['delegation_jwt'])
                    if 'checker' in trust_mark_spec:
                        if trust_mark_spec['checker'] == 'trust_path':
                            spec.set_checker(trust_mark_spec['checker'], trust_mark_spec['checker']['config']['trust_anchors'])
                        else:
                            spec.set_checker(trust_mark_spec['checker'])
                    config.trust_mark_specs.append(spec)
            if 'trust_mark_owners' in data:
                for trust_mark_id, owner_data in data['trust_mark_owners'].items():
                    owner = {}
                    if 'entity_id' in owner_data:
                        owner['entity_id'] = owner_data['entity_id']
                    if 'jwks' in owner_data:
                        owner['jwks'] = owner_data['jwks']
                    config.trust_mark_owners[trust_mark_id] = owner
            if 'trust_marks' in data:
                for trust_mark in data['trust_marks']:
                    if 'trust_mark_id' in trust_mark and 'trust_mark_issuer' in trust_mark:
                        config.trust_marks.append(trust_mark)
            if 'trust_mark_issuers' in data:
                for trust_mark_id, issuer_data in data['trust_mark_issuers'].items():
                    issuers = {}
                    if 'entity_id' in issuer_data:
                        issuer['entity_id'] = issuer_data['entity_id']
                    config.trust_mark_issuers.append = issuer            
        return config

    def to_yaml(self, file_path):
        with open(file_path, 'w') as f:
            yaml.dump((self.__dict__), f)

    def set_server_port(self, port):
        self.server_port = port

    def get_server_port(self):
        return self.server_port

    def set_entity_id(self, entity_id):
        self.entity_id = entity_id

    def get_entity_id(self):
        return self.entity_id

    def add_authority_hint(self, authority_hint):
        if 'authority_hints' not in self.__dict__:
            self.authority_hints = []
        self.authority_hints.append(authority_hint)

    def get_authority_hints(self):
        return self.authority_hints

    def set_signing_key_file(self, file_path):
        self.signing_key_file = file_path

    def get_signing_key_file(self):
        return self.signing_key_file

    def set_organization_name(self, name):
        self.organization_name = name

    def get_organization_name(self):
        return self.organization_name

    def set_data_location(self, location):
        self.data_location = location

    def get_data_location(self):
        return self.data_location

    def set_human_readable_storage(self, storage):
        if storage.lower() == 'true':
            self.human_readable_storage = True
        else:
            self.human_readable_storage = False

    def get_human_readable_storage(self):
        return self.human_readable_storage

    def set_metadata_policy_file(self, file_path):
        self.metadata_policy_file = file_path

    def get_metadata_policy_file(self):
        return self.metadata_policy_file

    def add_endpoint(self, name, path):
        if 'endpoints' not in self.__dict__:
            self.endpoints = {}
        self.endpoints[name] = {'path': path}

    def get_endpoints(self):
        return self.endpoints

    def add_trust_mark_spec(self, trust_mark_id, ref, delegation_jwt = None, logo_uri = None, lifetime = 86400, checker_type=None,trust_anchors=[]):
       spec = trust_mark_spec()

       spec.set_trust_mark_id(trust_mark_id)
       spec.set_lifetime(lifetime)
       spec.set_ref(ref)
       spec.set_logo_uri(logo_uri)
       spec.set_delegation_jwt(delegation_jwt)
       spec.add_checker(checker_type, trust_anchors)

       self.trust_mark_specs.append(spec.asdict())

    def get_trust_mark_specs(self):
        return self.trust_mark_specs

    def add_trust_mark(self, trust_mark_id, trust_mark_issuer):
        if 'trust_marks' not in self.__dict__:
            self.trust_marks = []
        self.trust_marks.append({'trust_mark_id': trust_mark_id, 'trust_mark_issuer': trust_mark_issuer})   

    def get_trust_marks(self):
        return self.trust_marks

    def add_trust_mark_owner(self, trust_mark_id, entity_id, jwks):
        if 'trust_mark_owners' not in self.__dict__:
            self.trust_mark_owners = {}
        self.trust_mark_owners[trust_mark_id] = {'entity_id': entity_id, 'jwks': jwks}

    def get_trust_mark_owners(self):
        return self.trust_mark_owners
    
    def add_trust_mark_issuer(self, trust_mark_id, entity_id):
        if 'trust_mark_issuers' not in self.__dict__:
            self.trust_mark_issuers = {}
        self.trust_mark_issuers.update({entity_id: [trust_mark_id]}) 

class tmi_config:
    def __init__(self):
        self.server_port = None
        self.entity_id = None
        self.authority_hints = []
        self.signing_key_file = None
        self.organization_name = None
        self.data_location = None
        self.human_readable_storage = False
        self.endpoints = {}
        self.trust_mark_specs = []
        self.trust_marks = []

    def from_yaml(file_path):
        config = tmi_config()
        with open(file_path, 'r') as f:
            data = yaml.safe_load(f)
            if 'server_port' in data:
                config.server_port = data['server_port']
            if 'entity_id' in data:
                config.entity_id = data['entity_id']
            if 'authority_hints' in data:
                config.authority_hints = data['authority_hints']
            if 'signing_key_file' in data:
                config.signing_key_file = data['signing_key_file']
            if 'organization_name' in data:
                config.organization_name = data['organization_name']
            if 'data_location' in data:
                config.data_location = data['data_location']
            if 'human_readable_storage' in data:
                config.human_readable_storage = True
            if 'endpoints' in data:
                for endpoint_name, endpoint_data in data['endpoints'].items():
                    config.endpoints[endpoint_name] = {'path': endpoint_data['path']}
            if 'trust_mark_specs' in data:
                for trust_mark_spec in data['trust_mark_specs']:
                    spec = trust_mark_spec()
                    if 'trust_mark_id' in trust_mark_spec:         
                        spec.set_trust_mark_id(trust_mark_spec['trust_mark_id'])
                    if 'lifetime' in trust_mark_spec:
                        spec.set_lifetime(trust_mark_spec['lifetime'])
                    if 'ref' in trust_mark_spec:
                        spec.set_ref(trust_mark_spec['ref'])
                    if 'delegation_jwt' in trust_mark_spec:
                        spec.set_delegation_jwt(trust_mark_spec['delegation_jwt'])
                    if 'checker' in trust_mark_spec:
                        if trust_mark_spec['checker'] == 'trust_path':
                            spec.set_checker(trust_mark_spec['checker'], trust_mark_spec['checker']['config']['trust_anchors'])
                        else:
                            spec.set_checker(trust_mark_spec['checker'])
                    config.trust_mark_specs.append(spec)
            if 'trust_marks' in data:
                for trust_mark in data['trust_marks']:
                    if 'trust_mark_id' in trust_mark and 'trust_mark_issuer' in trust_mark:
                        config.trust_marks.append(trust_mark)         
        return config

    def to_yaml(self, file_path):
        with open(file_path, 'w') as f:
            yaml.dump((self.__dict__), f)

    def set_server_port(self, port):
        self.server_port = port

    def get_server_port(self):
        return self.server_port

    def set_entity_id(self, entity_id):
        self.entity_id = entity_id

    def get_entity_id(self):
        return self.entity_id

    def add_authority_hint(self, authority_hint):
        if 'authority_hints' not in self.__dict__:
            self.authority_hints = []
        self.authority_hints.append(authority_hint)

    def get_authority_hints(self):
        return self.authority_hints

    def set_signing_key_file(self, file_path):
        self.signing_key_file = file_path

    def get_signing_key_file(self):
        return self.signing_key_file

    def set_organization_name(self, name):
        self.organization_name = name

    def get_organization_name(self):
        return self.organization_name

    def set_data_location(self, location):
        self.data_location = location

    def get_data_location(self):
        return self.data_location

    def set_human_readable_storage(self, storage):
        if storage.lower() == 'true':
            self.human_readable_storage = True
        else:
            self.human_readable_storage = False

    def get_human_readable_storage(self):
        return self.human_readable_storage

    def add_endpoint(self, name, path):
        if 'endpoints' not in self.__dict__:
            self.endpoints = {}
        self.endpoints[name] = {'path': path}

    def get_endpoints(self):
        return self.endpoints

    def add_trust_mark_spec(self, trust_mark_id, ref, delegation_jwt = None, logo_uri = None, lifetime = 86400, checker_type=None,trust_anchors=[]):
       spec = trust_mark_spec()

       spec.set_trust_mark_id(trust_mark_id)
       spec.set_lifetime(lifetime)
       spec.set_ref(ref)
       spec.set_logo_uri(logo_uri)
       spec.set_delegation_jwt(delegation_jwt)
       spec.add_checker(checker_type, trust_anchors)

       self.trust_mark_specs.append(spec.asdict())

    def get_trust_mark_specs(self):
        return self.trust_mark_specs

    def add_trust_mark(self, trust_mark_id, trust_mark_issuer):
        if 'trust_marks' not in self.__dict__:
            self.trust_marks = []
        self.trust_marks.append({'trust_mark_id': trust_mark_id, 'trust_mark_issuer': trust_mark_issuer})   

    def get_trust_marks(self):
        return self.trust_marks
    
class rp_config:
    def __init__(self):
        self.server_addr = None
        self.entity_id = None
        self.authority_hints = []
        self.trust_anchors = []
        self.signing_key_file = None
        self.organization_name = None
        self.key_storage = None
        self.filter_to_automatic_ops = False
        self.enable_debug_log = False
        self.trust_marks = []

    def from_yaml(file_path):
        config = rp_config()
        with open(file_path, 'r') as f:
            data = yaml.safe_load(f)
            if 'server_addr' in data:
                config.server_addr = data['server_addr']
            if 'entity_id' in data:
                config.entity_id = data['entity_id']
            if 'authority_hints' in data:
                config.authority_hints = data['authority_hints']
            if 'trust_anchors' in data:
                config.trust_anchors = data['trust_anchors']
            if 'signing_key_file' in data:
                config.signing_key_file = data['signing_key_file']
            if 'organization_name' in data:
                config.organization_name = data['organization_name']
            if 'key_storage' in data:
                config.key_storage = data['key_storage']
            if 'filter_to_automatic_ops' in data:
                config.filter_to_automatic_ops = data['filter_to_automatic_ops']
            if 'enable_debug_log' in data:
                config.enable_debug_log = data['enable_debug_log']
            if 'trust_marks' in data:
                for trust_mark in data['trust_marks']:
                    if 'trust_mark_id' in trust_mark and 'trust_mark_issuer' in trust_mark:
                        config.trust_marks.append(trust_mark)         
        return config

    def to_yaml(self, file_path):
        with open(file_path, 'w') as f:
            yaml.dump((self.__dict__), f)

    def set_server_addr(self, server_addr):
        self.server_addr = server_addr

    def get_server_addr(self):
        return self.server_addr

    def set_entity_id(self, entity_id):
        self.entity_id = entity_id

    def get_entity_id(self):
        return self.entity_id

    def add_authority_hint(self, authority_hint):
        if 'authority_hints' not in self.__dict__:
            self.authority_hints = []
        self.authority_hints.append(authority_hint)

    def get_authority_hints(self):
        return self.authority_hints

    def add_trust_anchor(self, trust_anchor):
        if 'trust_anchors' not in self.__dict__:
            self.trust_anchors = []
        self.trust_anchors.append({"entity_id": trust_anchor})

    def get_trust_anchors(self):
        return self.trust_anchors

    def set_signing_key_file(self, file_path):
        self.signing_key_file = file_path

    def get_signing_key_file(self):
        return self.signing_key_file

    def set_organization_name(self, name):
        self.organization_name = name

    def get_organization_name(self):
        return self.organization_name

    def set_key_storage(self, key_storage):
        self.key_storage = key_storage

    def get_key_storage(self):
        return self.key_storage

    def set_filter_to_automatic_ops(self, filter_to_automatic_ops):
        self.filter_to_automatic_ops = filter_to_automatic_ops

    def get_filter_to_automatic_ops(self):
        return self.filter_to_automatic_ops

    def set_enable_debug_log(self, enable_debug_log):
        self.enable_debug_log = enable_debug_log

    def get_enable_debug_log(self):
        return self.enable_debug_log

    def add_trust_mark(self, trust_mark_id, trust_mark_issuer):
        if 'trust_marks' not in self.__dict__:
            self.trust_marks = []
        self.trust_marks.append({'trust_mark_id': trust_mark_id, 'trust_mark_issuer': trust_mark_issuer})   

    def get_trust_marks(self):
        return self.trust_marks