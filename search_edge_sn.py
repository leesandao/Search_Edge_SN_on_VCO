import requests
import pickle
import json
import jsonpath
import argparse
import os
import sys
import ast
import time
import datetime

# Specific imports
from requests.packages.urllib3.exceptions import InsecureRequestWarning


class Password(argparse.Action):
    def __call__(self, parser, namespace, values, option_string):
        if values is None:
            values = getpass.getpass()

        setattr(namespace, self.dest, values)


class ApiException(Exception):
    pass


class VcoRequestManager(object):

    # TODO: Give path outside here for the user to alter
    def __init__(self, hostname, verify_ssl=os.getenv('VCO_VERIFY_SSL', False),
                 path=os.getenv('VCO_COOKIE_PATH', "C:/Temp/")):
        """
        Init the Class
        """
        if not hostname:
            raise ApiException("Hostname not defined")
        self._session = requests.Session()
        self._verify_ssl = verify_ssl
        if self._verify_ssl == False:
            requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
        self._root_url = self._get_root_url(hostname)
        self._portal_url = self._root_url + "/portal/"
        self._livepull_url = self._root_url + "/livepull/liveData/"
        self._store_cookie = path + hostname + ".txt"
        self._seqno = 0

    def _get_root_url(self, hostname):
        """
        Translate VCO hostname to a root url for API calls
        """
        if hostname.startswith("http"):
            re.sub('http(s)?://', '', hostname)
        proto = "https://"
        return proto + hostname

    def login(self, **kwargs):
        self.authenticate(**kwargs)

    def logout(self, **kwargs):
        self.authenticate(logout=True, **kwargs)

    def authenticate(self, username="", password="", logout=False, is_operator=True, *args, **kwargs):
        """
        Authenticate to API - on success, a cookie is stored in the session and file
        """
        if not logout:
            path = "/login/operatorLogin" if is_operator else "/login/enterpriseLogin"
            data = {"username": username, "password": password}
        else:
            path = "/logout"
            data = {}

        url = self._root_url + path
        headers = {"Content-Type": "application/json"}
        r = self._session.post(url, headers=headers, data=json.dumps(data),
                               allow_redirects=True, verify=self._verify_ssl)

        if r.status_code == 200:
            if not logout:
                if "velocloud.message" in self._session.cookies:
                    if "Invalid" in self._session.cookies["velocloud.message"]:
                        raise ApiException(self._session.cookies["velocloud.message"].replace("%20", " "))

                if "velocloud.session" not in self._session.cookies:
                    raise ApiException("Cookie not received by server - something is very wrong")

                self._save_cookie()

            else:
                self._del_cookie()
        else:
            raise ApiException(r.text)

    def call_api(self, method=None, params=None, *args, **kwargs):
        """
        Build and submit a request
        Returns method result as a Python dictionary
        """
        if "velocloud.session" not in self._session.cookies:
            if not self._load_cookie():
                raise ApiException("Cannot load session cookie")

        if not method:
            raise ApiException("No Api Method defined")

        self._seqno += 1
        headers = {"Content-Type": "application/json"}
        method = self._clean_method_name(method)
        payload = {"jsonrpc": "2.0",
                   "id": self._seqno,
                   "method": method,
                   "params": params}

        # print(payload)
        if method in ("liveMode/readLiveData", "liveMode/requestLiveActions", "liveMode/clientExitLiveMode"):
            url = self._livepull_url
        else:
            url = self._portal_url

        r = self._session.post(url, headers=headers,
                               data=json.dumps(payload), verify=self._verify_ssl)

        response_dict = r.json()
        # print(response_dict)
        if "error" in response_dict:
            raise ApiException(response_dict["error"]["message"])
        return response_dict["result"]

    def _clean_method_name(self, raw_name):
        """
        Ensure method name is properly formatted prior to initiating request
        """
        return raw_name.strip("/")

    def _save_cookie(self):
        """
        Save cookie from VCO
        """
        with open(self._store_cookie, "wb") as f:
            try:
                pickle.dump(self._session.cookies, f)
            except Exception as e:
                raise ApiException(str(e))

    def _load_cookie(self):
        """
        Load VCO session cookie
        """
        if not os.path.isfile(self._store_cookie):
            return False

        with open(self._store_cookie, "rb") as f:
            try:
                self._session.cookies.update(pickle.load(f))
                return True
            except Exception as e:
                raise ApiException(str(e))

    def _del_cookie(self):
        """
        Delete VCO session cookie
        """
        try:
            os.remove(self._store_cookie)
            return True
        except Exception as e:
            raise ApiException(str(e))


class VcoApiExecuteError(Exception):
    pass




def search_all_edges_sn():
    VCOURL = input("Input VCO: ")
    username = input("Username: ")
    password = input("Password: ")
    SN = input("Edge S/N you want to search: ")

    client = VcoRequestManager(VCOURL)
    client.authenticate(username, password, is_operator=True)
    # 获取所有在这个VCO上的enterprise
    all_enterprise = client.call_api("network/getNetworkEnterprises",{"networkId":1})

    # 将其中所有的key为id的value取出并列为一个list
    list_enterprise = jsonpath.jsonpath(all_enterprise, '$..id')
    # print(list_enterprise)

    # 显示第一个用户名称
    # print(all_enterprise[0]['name'])

    # 根据这个VCO下有多少企业用户来决定最大值的范围
    # check_enterprises = range(1,150)
    # 根据这个企业用户下有多少个Edge站带你来决定最大值的范围
    # check_edges_under_enterprise = range(1,50)

    # 如何只有一个企业用户，则
    if len(list_enterprise) == 1:
        all_edge = client.call_api("enterprise/getEnterpriseEdgeList", {"enterpriseId":1})  # 只有一个用户，enterpriseId应该为1
        list_edge = jsonpath.jsonpath(all_edge, '$..id')
        # print(list_edge)
        # exit()
        # 如果这个企业用户只有一个Edge，按照如下进行判断
        if len(list_edge) == 1:
            if SN == all_edge[0]['serialNumber']:
                print("Got it!!!!!!This SN is %s of Enterprise %s" % (all_edge[0]['name'], all_enterprise[0]['name']))

            else:
                # return None
                print("There is no SN#%s on under this Customer %s" % (SN,all_enterprise[0]['name']))
        # 如果这个企业用户不止一个Edge，那么对所有Edge循环取出SN号，并判断是否是我们要找的序列号
        else:
            for edge_num in range(len(list_edge)):
                if SN == all_edge[edge_num]['serialNumber']:
                    print("Got it!!!!!!This SN is %s of Enterprise %s" % (all_edge[edge_num]['name'], all_enterprise[0]['name']))
                # 没有这个SN号就不要输出
                else:
                    # return None
                    # print("There is no SN#%s on under this Customer %s" % (SN, all_enterprise[0]['name']))
                    continue



    # 如果有多个企业用户
    else:
        # 轮询所有的企业用户
        for enterprise_num in range(len(list_enterprise)):
            try:
                # 拿到这个企业用户下所有的Edge信息
                all_edge = client.call_api("enterprise/getEnterpriseEdgeList", {"enterpriseId": list_enterprise[enterprise_num]})
                # 通过list列出这个企业用户下的所有的edge id
                list_edge = jsonpath.jsonpath(all_edge, '$..id')

                # print(len(list_edge))
                # print()
                # range(len(list_edge))
                # 取得了所有id，但是Array里是按照顺序来排列edge的信息，第一个就是0
                # print(res[len(list_edge)-1]['serialNumber']
                # exit()

                # 如果只有一个Edge
                if len(list_edge) == 1:
                    if SN == all_edge[0]['serialNumber']:
                        print("Got it!!!!!!This SN is %s of Enterprise %s" % (all_edge[0]['name'], all_enterprise[enterprise_num]['name']))
                    # 没有这个SN号就不要输出
                    # else:
                         # return None
                         # print("There is no SN#%s on under this Customer %s" % (SN,all_enterprise[enterprise_num]['name']))
                # 有多个Edge的情况下
                else:
                    # 列举出所有的Edge
                    for edge_num in range(len(list_edge)):
                        # print(res[edge_num]['serialNumber'])
                        # exit()
                        if SN == all_edge[edge_num]['serialNumber']:
                            print("Got it!!!!!!This SN is %s of Enterprise %s" % (all_edge[edge_num]['name'], all_enterprise[enterprise_num]['name']))
                            # exit()
                        # 没有这个SN号就不要输出
                        else:
                            continue
                            # print("There is no SN#%s on under this Customer %s" % (SN,all_enterprise[enterprise_num]['name']))
                            # exit()


                    # if res[edge_num]['serialNumber'] == SN:
                    #
                    #     print("SN is on enterprise %s" % enterprise_num)
                    # else:
                    #     print("No edge of %s" % SN)
                # print(res[1]['serialNumber'])

            except Exception as e:
                print("It may be no edges under %s Customer" % all_enterprise[enterprise_num]['name'])

        # print(res)
