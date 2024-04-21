from pymongo import MongoClient
from pymongo.server_api import ServerApi
from bson import ObjectId
from datetime import datetime
import os

mongo_uri = os.getenv("MONGO_URI")

class ChatRoom:
    def __init__(self):
        self.client = MongoClient(mongo_uri, server_api=ServerApi('1'))
        self.chat_db = self.client.get_database('chat-db')
        self.chat_room_collection = self.chat_db.get_collection("chat_room")

    def create_new_chat_room(self, room_id):
        """
        Create a new chat room with an empty chat list.
        """
        room_data = {
            "room_id": room_id,
            "chat_list": []
        }
        self.chat_room_collection.insert_one(room_data)

    def add_message(self, room_id, sender, message):
        """
        Add a message to the chat room.
        """
        self.chat_room_collection.update_one(
            {"_id": room_id},
            {"$push": {"chat_list": {"sender": sender, "message": message, "created_at": datetime.now()}}},
            upsert=True
        )

    def get_messages(self, room_id):
        """
        Retrieve all messages for the chat room.
        """
        chat_room = self.chat_room_collection.find_one({"_id": room_id})
        return chat_room.get("chat_list", []) if chat_room else []

    # Add other methods as needed

    def __del__(self):
        """
        Close the MongoDB client connection when the instance is deleted.
        """
        if hasattr(self, 'client'):
            self.client.close()
