"""
The is the Python code to initialize the topo config repo in CMS. it will
do the following:
1. create a topoconfig repo if not exist yet
2. create meta data definition for Mapping class, schema is defined at mapping_schema.json
3. for subfolder such as aws:
    3.1 create topoaws repo for aws topo
    3.2 create metadata definition in topoaws based on config file in mapping folder
    3.3 load metadata definition in topoaws
    3.4 load files in mapping folder into topoconfig.
"""

import json
import unicodedata
import logging

from icotopo.yidbclient.client import YidbClient
import os

def u2s(unicode):
    "convert unicode string to string"
    return unicodedata.normalize('NFKD', unicode).encode('ascii','ignore')

def save_metadata(repo, class_name, metadata):
    dir_name = "../generated/" + repo
    if (not os.path.isdir(dir_name)):
        os.makedirs(dir_name)
    file = dir_name + "/" + class_name + ".json"
    with open(file, 'w') as outfile:
        json.dump(metadata,outfile, sort_keys=True, indent=4)

def mapping2metadata(yidb, repo, mapping):
    "convert the mapping to CMS metadata"
    metadata = {}
    metadata['name'] = mapping['className']
    metadata['description'] = "Auto generated by init.py"
    fields = {}
    metadata['fields'] = fields
    for item in mapping['fields']:
        item = u2s(item)
        field_def = mapping['fields'][item]
        field = {}
        field['description'] = str(field_def['path'])
        if ('class' in field_def):
            yidb.init_metadata_def(repo, field_def['class'])
            field['refDataType'] = field_def['class']
            field['relationType'] = 'Reference'
            field['dataType'] = 'relationship'
        else:
            if ('dataType' in field_def):
                field['dataType'] = field_def['dataType']
            else:
                field['dataType'] = 'string'
        fields[item] = field
    return metadata


def main():
    logging.basicConfig(level=logging.INFO)

    logging.info("load topo_config.json")
    config = json.load(open("../config/topo_config.json"))
    logging.info(config)
    topo_config_repo = config['topo_config_repo']

    # enable delete for metadata in YiDB
    yidb = YidbClient(config['cms_endpoint'])
    logging.info("allow metadata delete")
    response = yidb.enable_delete()
    logging.info("response status:" + str(response.status_code) + " content:" + response.content)

    # check to see if repo exists, if not, create the repo
    logging.info("adding new repo if not exists:" + topo_config_repo)
    response = yidb.upsert_repo(topo_config_repo)
    logging.info("response status:" + str(response.status_code) )

    mapping = json.load(open("../config/topo_mapping.json"))
    logging.info("load TopoMapping metadata:" + str(mapping))
    response = yidb.upsert_metadata(topo_config_repo, "TopoMapping", mapping)
    logging.info("response status:" + str(response.status_code) + " content:" + response.content)

    # loop through each sub directory that having mapping folder
    # load the mapping, create topo_repo and load the meta data
    for client_id in ['ec2','s3']:
        # create topo repo
        client_config = json.load(open("../config/" + client_id + "/config.json"))
        topo_repo = client_config['topo_repo']
        yidb.upsert_repo(topo_repo)
        yidb.delete_all_metadata(topo_repo)

        # for each class, load the mapping and also load the metadata
        resource_config = json.load(open("../config/" + client_id + "/resource.json"))
        for resource in resource_config:
            class_name = resource['className']
            mapping_file = "../config/" + client_id + "/mapping/" + class_name.lower() + ".json"
            mapping_json = json.load(open(mapping_file))
            mapping_payload = {}
            mapping_payload['clientId'] = client_id
            mapping_payload['_oid'] = client_id + ":" + class_name
            mapping_payload['className'] = class_name
            mapping_payload['mapping'] = mapping_json
            logging.info("insert mapping to TopMapping:" + str(mapping_payload))
            response = yidb.upsert_object(topo_config_repo, "TopoMapping", mapping_payload)
            logging.info("response status:" + str(response.status_code) + " content:" + response.content)

            logging.info("insert metadata for repo:" + topo_repo)
            metadata = mapping2metadata(yidb, topo_repo, mapping_json)
            response = yidb.upsert_metadata(topo_repo, class_name, metadata)
            if (response.status_code == 200):
                save_metadata(topo_repo, class_name, metadata)
            logging.info("response status:" + str(response.status_code) + " content:" + response.content)

if __name__ == '__main__':
    main()

