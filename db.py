from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from werkzeug.security import generate_password_hash
from user import User
from datetime import datetime
from bson import ObjectId
from flask import jsonify
import os

mongo_uri = os.getenv("MONGO_URI")

# Create a new client and connect to the server
client = MongoClient(mongo_uri, server_api=ServerApi('1'))
# Send a ping to confirm a successful connection
try:
    client.admin.command('ping')
    print("Pinged your deployment. You successfully connected to MongoDB!")
except Exception as e:
    print(e)

chat_db = client.get_database('chat-db')
# users
users_collection = chat_db.get_collection("users")
# rooms
rooms_collection = chat_db.get_collection("rooms")
room_members_collection = chat_db.get_collection("room_members")
# messages
group_messages = chat_db.get_collection("group_messages")
direct_messages = chat_db.get_collection("direct_messages")

chat_room_collection = chat_db.get_collection("chat_room")

# User Operation--------------------------------------------------------------------------------------------------------
def save_user(username, password):
    password_hash = generate_password_hash(password)
    users_collection.insert_one({'_id':username, 'password':password_hash})

def get_user(username):
    user_data = users_collection.find_one({'_id':username})
    return User(user_data['_id'], user_data['password']) if user_data else None

def get_all_friends(username):
    # Retrieve all users from the database
    all_users = users_collection.find({}, {'_id': 1})
    # Extract usernames from user documents
    all_usernames = [user['_id'] for user in all_users]
    # Exclude the user's own username from the list of friends
    friends = [friend for friend in all_usernames if friend != username]
    return friends

# Room Operation --------------------------------------------------------------------------------------------------------
def update_room(room_id, room_name):
    rooms_collection.update_one({'_id': ObjectId(room_id)}, {'$set': {'name': room_name}})
    room_members_collection.update_many({'_id.room_id': ObjectId(room_id)}, {'$set': {'room_name': room_name}})

def get_room(room_id):
    return rooms_collection.find_one({'_id': ObjectId(room_id)})

def get_rooms_from_type(room_type):
    # Find all rooms with the specified room_type
    rooms = rooms_collection.find({'type': room_type})
    # Extract _id and room_name from room documents
    room_data = [{'_id': str(room['_id']), 'name': room['name']} for room in rooms]
    return room_data

# Room Member Operation -------------------------------------------------------------------------------------------------
def add_a_room_member(room_id, username, added_by):
    try:
        print(1)
        #only the admin can remove
        if not is_room_admin(room_id, added_by):
            raise ValueError("User '{}' don't have permission to add member".format(added_by))
        # Check if the user is already a member of the group
        if is_room_member(room_id, username):
            raise ValueError("User '{}' is already a member of the group".format(username))
        # Check if the user exists in the system
        if users_collection.count_documents({"_id": username}) == 0:
            raise ValueError("User '{}' does not exist in the system".format(username))
        # Check if the room is private room
        if get_room_type(room_id) != 'PrivateGroup':
            raise ValueError("Room '{}' is not a PrivateGroup".format(room_id))
        
        room_name = get_room_name(room_id)
        print(room_name)
        room_members_collection.insert_one({
            '_id': {'room_id': ObjectId(room_id), 'username': username}, 
            'room_name': room_name, 
            'added_by': added_by,
            'added_at': datetime.now(), 
            'is_room_admin': False
        })
        return jsonify({'message': 'User {} added to room {}'.format(username, room_name)}), 200
    except ValueError as e:
        print("valueerror")
        return jsonify({'error': str(e)}), 400


def add_room_members(room_id, room_name, usernames, added_by):
    for username in usernames:
        # Check if the user exists in the system
        if users_collection.count_documents({"_id": username}) == 0:
            raise ValueError("User '{}' does not exist in the system.".format(username))
        
        # Check if the user is already a member of the group
        if is_room_member(room_id, username):
            raise ValueError("User '{}' is already a member of the group.".format(username))
    
    bulk_operations = [
        {
            '_id': {'room_id': ObjectId(room_id), 'username': username},
            'room_name': room_name,
            'added_by': added_by,
            'added_at': datetime.now(),
            'is_room_admin': False
        }
        for username in usernames
    ]
    room_members_collection.insert_many(bulk_operations)

def remove_a_room_member(room_id, remove_by, username):
    try:
        # Only the admin can remove
        if not is_room_admin(room_id, remove_by):
            raise ValueError("User '{}' doesn't have permission to remove member".format(remove_by))
        
        # Check if the room is a private room
        if get_room_type(room_id) != 'PrivateGroup':
            raise ValueError("Room '{}' is not a PrivateGroup".format(room_id))
        
        # Check if the user is a member of the group
        if not is_room_member(room_id, username):
            raise ValueError("User '{}' is not a member of the group".format(username))
        
        # Remove the user from the room
        room_members_collection.delete_one({'room_id': ObjectId(room_id), 'username': username})
        
        return jsonify({'message': "User '{}' removed from room".format(username)}), 200
    
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    
def remove_room_members(room_id, remove_by, usernames):
    #only the admin can remove
    if not is_room_admin(room_id, remove_by):
        raise ValueError("User '{} don't have permission to remove member'".format(username) )
    # Check if the room is private room
    if get_room_type(room_id) != 'PrivateGroup':
        raise ValueError("Room '{}' is not a PrivateGroup.".format(room_id))
    for username in usernames:
        # Check if the user is a member of the group
        if not is_room_member(room_id, username):
            raise ValueError("User '{}' is not a member of the group.".format(username))
    
    room_members_collection.delete_many({
        '_id': {'$in': [{'room_id': ObjectId(room_id), 'username': username} for username in usernames]}
    })
def save_room(room_name, room_type, created_by):
    room_id = rooms_collection.insert_one(
        {'name': room_name,
         'type': room_type, #(Direct, PublicGroup, PrivateGroup)
         'created_by': created_by,
         'created_at': datetime.now()}).inserted_id
    add_a_room_member(room_id, room_name, created_by, created_by, is_room_admin=True)
    return room_id

def get_room_members(room_id):
    return list(room_members_collection.find({'_id.room_id': ObjectId(room_id)}))

def get_rooms_for_user(username):
    return list(room_members_collection.find({'_id.username': username}))


def is_room_member(room_id, username):
    return room_members_collection.count_documents({'_id': {'room_id': ObjectId(room_id), 'username': username}})

def is_room_admin(room_id, username):
    return room_members_collection.count_documents(
        {'_id': {'room_id': ObjectId(room_id), 'username': username}, 'is_room_admin': True})

def get_room_type(room_id):
    room = rooms_collection.find_one({'_id': ObjectId(room_id)})
    if room:
        room_type = room.get('type')
        return room_type
    else:
        return None 
    
def get_room_name(room_id):
    room = rooms_collection.find_one({'_id': ObjectId(room_id)})
    if room:
        room_name = room.get('name')
        return room_name
    else:
        return None 
