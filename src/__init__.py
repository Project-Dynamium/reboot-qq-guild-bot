import botpy
from botpy import logging, BotAPI
from botpy.message import Message, DirectMessage
from botpy.errors import ServerError
from botpy.types.message import Reference
from botpy.ext.command_util import Commands
from botpy.ext.cog_yaml import read

import os, json, asyncio, time, traceback
from typing import Union

import motor.motor_asyncio
from bson.objectid import ObjectId

config = read(os.path.join(os.path.dirname(__file__), "../config.yaml"))
log = logging.get_logger()
Msg = Union[Message, DirectMessage]

class DatabaseWorker:
    def __init__(self, url, dbname):
        mongo_cli = motor.motor_asyncio.AsyncIOMotorClient(url)
        mongo_cli.get_io_loop = asyncio.get_running_loop
        self.database = mongo_cli[dbname]

    def __generate_id_filter__(self, id = None):
        return {"_id": ObjectId(id) if type(id) is str else id} if id != None else {}

    async def find(self, set, filter = None, id = None):
        filter = self.__generate_id_filter__(id) if filter is None else filter
        return await self.database[set].find_one(filter)
    
    async def delete(self, set, filter = None, id = None):
        filter = self.__generate_id_filter__(id) if filter is None else filter
        return await self.database[set].delete_one(filter)

    async def insert(self, set, doc = {}, specific_id = False):
        if not specific_id:
            doc["_id"] = ObjectId()
        await self.database[set].insert_one(doc)
        return doc["_id"]

    async def update(self, set, doc = {}, filter = None, id = None):
        filter = self.__generate_id_filter__(id) if filter is None else filter
        if filter == {}: raise Exception("Invalid database update.")
        await self.database[set].update_one(filter, {"$set": doc})


db = DatabaseWorker(config["database"]["url"], config["database"]["dbname"])