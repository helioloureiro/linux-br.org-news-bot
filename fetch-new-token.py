#! /usr/bin/env python3
from getpass import getpass
import argparse
import configparser
import requests
import json

def readConfig(configFile):
    cfg = configparser.ConfigParser()
    cfg.read(configFile)
    return cfg

def getSiteFromConfig(cfgObj):
    return cfgObj.get('WORDPRESS', 'SITE')

def updateTokenConfig(token, configFile):
    cfg = readConfig(configFile)
    with open(configFile, 'w') as cFD:
        cfg.set('WORDPRESS', 'TOKEN', token)
        cfg.write(cFD)
    print('Token updated at configuration file')

def main():
    parse = argparse.ArgumentParser(description="Fetch you webtoken from JWT enabled Wordpress site")
    parse.add_argument('--config', help="Configuration file")
    args = parse.parse_args()
    if args.config is None:
        raise Exception("Missing --config parameter")

    cfg = readConfig(args.config)
    site = getSiteFromConfig(cfg)

    jwt_username = input(f'Enter the site {site} username: ')
    jwt_password = getpass(prompt='Enter the site password: ')

    jwt_auth_url = f'{site}/wp-json/jwt-auth/v1/token'

    jwt_payload = {"username": jwt_username, "password": jwt_password}
    jwt_response = requests.post(jwt_auth_url, data=json.dumps(jwt_payload), headers={"Content-Type": "application/json"})

    if jwt_response.status_code != 200:
        print('status code:', jwt_response.status_code)
        print('Error: ', jwt_response.text)
        return
    jwt_token = jwt_response.json()["data"]["token"]
    print(jwt_token)
    updateTokenConfig(jwt_token, cfg)




if __name__ == '__main__':
    main()
