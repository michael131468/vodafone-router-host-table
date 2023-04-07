#!/usr/bin/env python3

import argparse
import hashlib
import hmac
import logging
import os
import requests
import sys
import urllib.parse

from datetime import datetime

from pbkdf2 import PBKDF2

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def talk_router(
    session: requests.sessions.Session,
    router_ip: str,
    path: str,
    query_params={},
    form_data=None,
) -> dict:
    """Send http requests to the router"""
    # The router expects a nonce in the query params (named "_") which protects
    # the api endpoints. It expects a unix timestamp that lines up closely to
    # its local time (to the millisecond). This function hopes your local time
    # is the same as the router
    nonce = int(datetime.now().timestamp() * 1e3)
    query_params["_"] = nonce

    # Say something
    headers = {
        "X-Requested-With": "XMLHttpRequest",
        "referer": f"http://{router_ip}/",
        "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/110.0",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept": "text/javascript, application/javascript, application/ecmascript, application/x-ecmascript, */*; q=0.01",
    }
    url = urllib.parse.urljoin(f"http://{router_ip}", path)
    if form_data:
        resp = session.post(url, headers=headers, params=query_params, data=form_data)
    else:
        resp = session.get(url, headers=headers, params=query_params)

    logging.debug("-- Request --")
    logging.debug(resp.request.url)
    logging.debug(resp.request.headers)
    logging.debug(resp.request.body)
    logging.debug("--")

    logging.debug("-- Response --")
    logging.debug(resp)
    logging.debug(resp.headers)
    logging.debug(resp.content.decode())
    logging.debug("--")

    # Check status code and provide debug if router seems unhappy
    if not 200 <= resp.status_code < 300:
        print(f"Error: {resp.status_code}")
        return None

    # Return json payload if possible
    try:
        ret = resp.json()
    except:
        ret = None

    return ret


def do_login(
    session: requests.sessions.Session,
    router_ip: str,
    username: str,
    password: str,
    force_logout=False,
) -> bool:
    """Try to login to router"""

    # First get the salts (magic constant: seeksalthash)
    payload = {"username": username, "password": "seeksalthash"}
    if force_logout:
        payload["logout"] = "true"
    resp = talk_router(session, router_ip, "/api/v1/session/login", form_data=payload)
    if not resp or resp.get("error") != "ok":
        print("Error: could not discover salts")
        return False

    salt = resp.get("salt")
    saltwebui = resp.get("saltwebui")

    # Apply two rounds of pbkdf2 to the password
    # Each round has 1000 iterations and uses SHA256/HMAC
    # And the key is reduced to 128bits (16 bytes)
    key = PBKDF2(
        password, salt, iterations=1000, digestmodule=hashlib.sha256, macmodule=hmac
    ).hexread(16)
    key = PBKDF2(
        key, saltwebui, iterations=1000, digestmodule=hashlib.sha256, macmodule=hmac
    ).hexread(16)

    # Send login data
    resp = talk_router(
        session,
        router_ip,
        "/api/v1/session/login",
        form_data={"username": username, "password": key},
    )

    if not resp:
        print("Error: login failed")
        print(resp)
        return False

    # Check response. Expect something like:
    # {'error': 'error', 'message': 'MSG_LOGIN_1', 'data': {'failedAttempts': 1}}
    # or
    # {'error': 'ok', 'message': 'MSG_LOGIN_1', 'data': {[user': 'admin', ...]}}
    if resp.get("error") == "error":
        # MSG_LOGIN_150 means another user must be logged out to be able to login
        if resp.get("message") == "MSG_LOGIN_150":
            return do_login(session, router_ip, username, password, force_logout=True)
        else:
            print("Error: login failed")
            print(resp)
            return False

    return True


def get_session(router_ip: str) -> requests.sessions.Session:
    """Asks router to create a PHP session"""
    session = requests.Session()
    resp = talk_router(session, router_ip, "/api/v1/session/dlang")

    # Expect something like: {"data":{"dlang":"en"}}
    if "data" not in resp or "dlang" not in resp["data"]:
        print(f"Error: unexpected response from router: {resp}")
        session = None

    session.cookies.set("cwd", "No", domain=router_ip)
    logging.debug(session.cookies.get_dict())
    return session


def main() -> int:
    """Main function"""
    # Configuration
    parser = argparse.ArgumentParser(
        epilog="Set ROUTER_USERNAME to override the default admin username.\n"
        "Set ROUTER_PASSWORD to set the admin password.",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--router-ip",
        type=str,
        help="Router IP (Default: 192.168.0.1)",
        default="192.168.0.1",
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug trace")
    args = parser.parse_args()

    debug = args.debug
    router_ip = args.router_ip
    username = os.environ.get("ROUTER_USERNAME", "admin")
    password = os.environ.get("ROUTER_PASSWORD", None)

    if not password:
        print(
            "Error: No password set. Please set environment variable: ROUTER_PASSWORD"
        )
        return 1

    if debug:
        logger.setLevel(logging.DEBUG)

    # Get a cookie
    session = get_session(router_ip)
    if not session:
        return 1

    # Do login
    success = do_login(session, router_ip, username, password)
    if not success:
        return 1

    # Ask router for host table
    # You must first js/app/bsd_acl_rules.js and then /api/v1/session/menu
    # otherwise the session becomes invalidated (some kind of protection mechanism)
    # This might change with different firmware versions, I discovered the ordering
    # by watching the firefox network connections made and replicating them in the
    # order presented followed by deleting paths one-by-one to find unnecessary paths.
    resp = talk_router(session, router_ip, "/js/app/bsd_acl_rules.js")
    resp = talk_router(session, router_ip, "/api/v1/session/menu")
    resp = talk_router(session, router_ip, "/api/v1/host/hostTbl")

    # Other host api endpoints include:
    # ,WPSEnable1,WPSEnable2,RadioEnable1,RadioEnable2,SSIDEnable1,SSIDEnable2,SSIDEnable3,
    # operational,call_no,call_no2,LineStatus1,LineStatus2,DeviceMode,ScheduleEnable,
    # dhcpLanTbl,dhcpV4LanTbl,lpspeed_1,lpspeed_2,lpspeed_3,lpspeed_4,AdditionalInfos1,
    # AdditionalInfos2

    # Parse results and display
    if "data" not in resp or "hostTbl" not in resp["data"]:
        print("Error: No host table data")
        return 1

    max_alias_len = max(map(lambda x: len(x["alias"]), resp["data"]["hostTbl"]))
    max_ip_len = max(map(lambda x: len(x["ipaddress"]), resp["data"]["hostTbl"]))

    print(
        f"{'Alias'.ljust(max_alias_len)} | {'IP Address'.ljust(max_ip_len)} | MAC Address"
    )
    print(f"{'-'*max_alias_len} | {'-'*max_ip_len} | -----------------")
    for host in resp["data"]["hostTbl"]:
        if host["active"] == "false":
            continue
        print(
            f"{host['alias'].ljust(max_alias_len)} | {host['ipaddress'].ljust(max_ip_len)} | {host['physaddress']}"
        )


if __name__ == "__main__":
    sys.exit(main())
