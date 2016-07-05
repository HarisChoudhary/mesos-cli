import json
import sys
import urllib2
import config
from socket import error as socket_error

import mesos

from mesos.plugins import PluginBase

PLUGIN_CLASS = "Agent"
PLUGIN_NAME = "agent"

VERSION = "Mesos CLI Agent Plugin 1.0"

SHORT_HELP = "Agent specific commands for the Mesos CLI"


class Agent(PluginBase):

    COMMANDS = {
        "ping" : {
            "arguments" : [],
            "flags" : {
                "--addr=Addr" :
                "IP and Port of Agent [Default: "+config.AGENT_IP+"]"
                },
            "short_help" : "Check Health of a running agent",
            "long_help"  :
"""
Sends a HTTP healthcheck request and returns the result.
"""
        },
        "state" : {
            "arguments" : ["[<field>...]"],
            "flags" : {
                "--addr=Addr" :
                "IP and Port of Agent [Default: "+config.AGENT_IP+"]"
                },
            "short_help" : "Get Agent State Informtation",
            "long_help"  :
"""
Get the agent state from the /state endpoint. If no <field> is supplied, 
it will display the entire state json. A field may be parsed from the 
state json to get its value. The format is field or index seperated by a \'.\'
So for example, getting the work_dir from flags is : flags.work_dir
Getting checkpoint information for the first framework would be : 
frameworks.0.checkpoint

Multiple fields can be parsed from the same command. I.e. flags.work_dir id
"""
        }
    }

    
    def __setup__(self, command, argv):
        pass

    
    def __autocomplete__(self, command, current_word, argv):
        return []
    
    #Helper to hit the specified endpoint and return json results
    def hit_endpoint(self,addr,endpoint):
        try:
            http_response = ( urllib2.urlopen("http://"+addr+endpoint)
                                            .read().decode('utf-8') )
        except socket_error as e:
            print("Cannot establish connection with Agent")
            sys.exit(1)

        return json.loads(http_response)

    def isInt(self, num):
        try:
            int(num)
            return True
        except ValueError:
            return False

    def parseJSON(self, fields, jsonInfo):

        splitFields = fields.split(".")
        jsonSub = jsonInfo
        command = ""

        for field in splitFields:
            command += field + "."
            if isinstance(jsonSub,dict):
                if self.isInt(field):
                    print("JSON is not a list, not expecting integer!")
                    return
                if field in jsonSub:
                    jsonSub = jsonSub[field]
                else:
                    print("JSON field : ", field, " not found!")
                    return
            elif isinstance(jsonSub,list):
                if not self.isInt(field):
                    print("JSON is a list, not expecting non-integer!")
                    return
                index = int(field)
                if index >= len(jsonSub):
                    print("List index out of bound!")
                    return
                jsonSub = jsonSub[index]
            else:
                print("No further sub-fields for : ",field)
                return jsonSub

        return jsonSub

    def ping(self, argv):
        httpResponseCode = None;
        try:
            httpResponseCode = ( urllib2.urlopen("http://"+argv["--addr"]
                                                    +"/health").getcode() )
        except socket_error as e:
            print("Cannot establish connection with Agent")
            sys.exit(1)

        if httpResponseCode == 200 :
            print("Agent Healthy!")
        else:
            print("Agent not healthy!")

    def state(self,argv):
        stateInfo = self.hit_endpoint(argv["--addr"],"/state")
        
        if len(argv["<field>"]) == 0:
            print(json.dumps(stateInfo,indent=2))
            return

        for arg in argv["<field>"]:
            result = self.parseJSON(arg, stateInfo)
            if result is None:
                print("Error parsing json for : ", arg)
            else:
                print(arg)
                print(json.dumps(result,indent=2))
                print("\n")
