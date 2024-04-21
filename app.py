from flask import Flask, jsonify, request, Response
from flask_socketio import SocketIO, join_room, leave_room
from flask_jwt_extended import JWTManager, create_access_token, unset_access_cookies, jwt_required, get_jwt_identity
from db import add_room_members, get_room, get_room_members, get_rooms_for_user, get_user, is_room_member, save_room, save_user
from chatRoom import ChatRoom
from dotenv import load_dotenv
from datetime import timedelta
import os

# Load environment variables from .env file
load_dotenv()
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY')

app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY')
app.config['JWT_TOKEN_LOCATION'] = ['headers', 'cookies']
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(minutes=360)
app.config['JWT_COOKIE_SECURE'] = True
app.config['JWT_COOKIE_SAMESITE'] = 'None'

socketio = SocketIO(app, cors_allowed_origins="*")
jwt = JWTManager(app)

##init chatroom
chat_room = ChatRoom()

@app.route('/',methods=['GET'])
@jwt_required() 
def home():
    current_username = get_jwt_identity()
    rooms = get_rooms_for_user(current_username)
    # Convert ObjectId to string for JSON serialization
    formatted_rooms = []
    for room in rooms:
        room_id_str = str(room['_id']['room_id'])  
        formatted_room = {
            'room_id': room_id_str,
            'room_name': room['room_name'],
            'added_by': room['added_by'],
            'added_at': room['added_at'].isoformat(),
            'is_room_admin': room['is_room_admin']
        }
        formatted_rooms.append(formatted_room)
    return jsonify({'username': current_username, 'rooms':formatted_rooms}), 200

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password_input = data.get('password')

    if not username or not password_input:
        return jsonify({'error': 'Invalid credentials'}), 400
    
    try:
        user = get_user(username)
        if user and user.check_password(password_input):
            access_token = create_access_token(identity=user.get_id())
            res = jsonify(accessToken=access_token, username=user.get_id())
            return res
        else:
            return jsonify({'error': 'Failed to login'}), 401
    except Exception as e:
        # Log the error for debugging
        app.logger.error(f"Error occurred while fetching user '{username}' from database: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/logout', methods=['POST'])   
@jwt_required() 
def logout():
    print('Received POST request for /logout')
    res = Response(status=204)
    unset_access_cookies(res)
    return res

@app.route('/signup', methods=['POST'])
def signup():
    data = request.get_json()
    username = data.get('username')
    password_input = data.get('password')

    if not username or not password_input:
        return jsonify({'error': 'Invalid credentials'}), 400
    
    user = get_user(username)
    if user:
        return jsonify({'error': 'This username has been used!'}), 400    
        
    else:
        save_user(username, password_input)
        access_token = create_access_token(identity=username)
        res = jsonify(accessToken=access_token, username = username)
        return res


@app.route('/create-room', methods=['GET', 'POST'])
@jwt_required()
def create_room():
    current_username = get_jwt_identity()
    if request.method == 'GET':
        return jsonify({'username': current_username}), 200
    else:
        try:
            room_name = request.get_json().get('room_name')
            room_type = request.get_json().get('room_type')
            usernames = [username.strip() for username in request.get_json().get('members').split(',')]
            if len(room_name) and len(usernames):
                room_id = save_room(room_name, room_type, current_username)
                if current_username in usernames:
                    usernames.remove(current_username)
                if len(usernames) > 1 or usernames[0] != '':
                    if room_type == 'PublicGroup':
                        add_room_members(room_id, room_name, usernames, current_username)

                # Create a new chat room
                chat_room.create_new_chat_room(room_id)

                return jsonify(room_id=str(room_id))
            else:
                return jsonify({'error': 'Invalid credentials'}), 400
        except ValueError  as e:
            # Log the error for debugging
            print(f"An error occurred while creating the chat room: {e}")
            return jsonify({'error': str(e)}), 500
                  
@app.route('/rooms/<room_id>/')
@jwt_required()
def view_room(room_id):
    current_username = get_jwt_identity()
    room = get_room(room_id)
    if room and is_room_member(room_id, current_username):
        room_id_str = str(room['_id'])
        formatted_room = {
            '_id' : room_id_str,
            'name': room['name'],
            'created_by': room['created_by'],
            'created_at' : room['created_at'].isoformat()
        }
        room_members = get_room_members(room_id)
        formatted_room_members = []
        for room_member in room_members:
            room_id_str = str(room_member['_id']['room_id'])  
            formatted_room_member = {
                'room_id': room_id_str,
                'username': room_member['_id']['username'],
                'added_by': room_member['added_by'],
                'added_at': room_member['added_at'].isoformat(),
                'is_room_admin': room_member['is_room_admin']
            }
            formatted_room_members.append(formatted_room_member)
        return jsonify(username=current_username, room=formatted_room, room_members=formatted_room_members)
    else :
        return jsonify({'error': 'Invalid credentials'}), 400

@app.route('/chatRoom/<room_id>/', methods=['GET'])
@jwt_required()
def get_chat_room(room_id):
    current_username = get_jwt_identity()

    # Check if the user is a member of the requested room
    if not is_room_member(room_id, current_username):
        return jsonify({'error': 'You are not a member of this room.'}), 403

    # Retrieve chat room details from the database
    room = get_room(room_id)
    if not room:
        return jsonify({'error': 'Chat room not found.'}), 404

    # Retrieve chat messages for the room
    chat_messages = chat_room.get_messages(room_id)

    # Format room data and messages for response
    formatted_room = {
        '_id': str(room['_id']),
        'name': room['name'],
        'type': room['type'],
        'created_by': room['created_by'],
        'created_at': room['created_at'].isoformat(),
        'chat_messages': chat_messages
    }

    return jsonify(formatted_room), 200

##############################################################    
# socket programming...
##############################################################

@socketio.on('send_message')
def handle_send_message_event(data):
    room_id = data['room']
    sender = data['username']
    message = data['message']
    
    # Add the message to the chat room
    chat_room.add_message(room_id, sender, message)
    
    # Broadcast the message to all clients in the room
    socketio.emit('receive_message', data, room=room_id)


@socketio.on('join_room')
def handle_join_room_event(data):
    app.logger.info("{} has joined the room {}".format(data['username'], data['room']))
    join_room(data['room'])
    socketio.emit('join_room_announcement', data, room=data['room'])


@socketio.on('leave_room')
def handle_leave_room_event(data):
    app.logger.info("{} has left the room {}".format(data['username'], data['room']))
    leave_room(data['room'])
    socketio.emit('leave_room_announcement', data, room=data['room'])

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0')
    # socketio.run(app,debug=True, port=5050)
