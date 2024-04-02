#!/usr/bin/python3

# Written by Vimukthi Herath

from socket import *
from threading import Thread
import sys
import os
import json
import time
from datetime import datetime
from argHandlers import serverArgHandler
from fileHandlers import userBlocked, handleIncorrectLogin, userLogManager, messageLogManager, groupMessageLogManager

## Just for dev use
# Clear any existing files on server restart
if os.path.exists("userlog.txt"):
    os.remove("userlog.txt")
if os.path.exists("attempt_records.txt"):
    os.remove("attempt_records.txt")


# Global variables
allowedAttempts = 2 # Default val
active_clients = {} # Stores { username, userThreadRef }
groups = {} # Stores {groupname1: [{participant1, onlineStatus}, {participant2, onlineStatus}], groupname2: [{..},{..},..]], ...}


## ClientThread class has been provided by: Wei Song (Tutor for COMP3331/9331) and thereby modified
class ClientThread(Thread):

    # Init thread
    def __init__(self, clientAddress, clientSocket):
        Thread.__init__(self)
        self.clientAddress = clientAddress
        self.clientSocket = clientSocket
        self.clientAlive = False
        self.loggedIn = False
        self.username = ""
        
        print(f"===== New connection created for: {clientAddress}")
        self.clientAlive = True


    # <---- METHOD: Listen to thread while alive ------>
    def run(self):

        global active_clients
        
        while self.clientAlive:
 
            raw_request = self.clientSocket.recv(1024).decode()

            # if the request from client is empty, the client ended the connection to the server
            if not raw_request:
                self.clientAlive = False
                print(f"\n===== the user disconnected - {self.clientAddress}\n")
                break    

            # Each request is a json object, for which the header tag defines the request type
            request = json.loads(raw_request)
            key = request["header"]
            
            # Pass on request to relevant method handler
            if key == 'login':
                self.processLogin(request["username"], request["password"], request["udp_port"])

            elif key == 'activeUser':
                self.getActiveUsers()

            elif key == 'logout':
                self.processLogout()

            elif key == 'sendMessage':
                self.sendMessage(request['sender'], request['recipient'], request['message'])

            elif key == 'createGroup':
                self.createGroup(self.username, request['groupName'], request['users'])

            elif key == 'joinGroup':
                self.joinGroup(request["groupName"])

            elif key == 'messageGroup':
                self.messageGroup(request["groupName"], request["message"])  

            elif key == 'confirmUDP':
                self.confirmUDP(request["message"])  

            else:
                print(f"Server cannot understand this request: {key}\n")
                self.clientSocket.send(json.dumps({
                    "header": "unknown",
                    "message": f"\nThe server could not understand the request.\n",
                }).encode())

    #<----------------------------------------------->



    # <---- METHOD: Handle login ------>
    def processLogin(self, username, password, udp_port):

        # Defaults
        validUser = False
        validLogin = False

        login_response = {
            "header": "login",
            "success": False,
            "errorMessage": "",
            "blocked": False
        }

        # Check if login details are valid
        with open('credentials.txt', 'r') as f:
            for line in f:
                user, pw = line.strip().split()
                if username == user:
                    validUser = True
                    if password == pw:
                        validLogin = True
                        break

        # Case where user does not exist
        if not validUser:

            login_response['errorMessage'] = "Username does not exist\n"
            self.clientSocket.send(json.dumps(login_response).encode())
            return
        
        # Check if currently blocked
        blocked = userBlocked(username, allowedAttempts)

        # User exists + correct login + not blocked
        if validLogin and not blocked:

            login_response['success'] = True
            self.username = username
            self.clientSocket.send(json.dumps(login_response).encode())
            
            # generate/add to userlog
            userLogManager(username, self.clientAddress, udp_port)
            
            # store client in active client dict
            active_clients[username] = self
            return

        # User exists + wrong password
        else:

            errorMsg, blocked = handleIncorrectLogin(username, allowedAttempts)

            if blocked:
                login_response['blocked'] = True

            login_response['errorMessage'] = errorMsg
            self.clientSocket.send(json.dumps(login_response).encode())
            return
    #<----------------------------------------------->



    # <---- METHOD: get list of active users ------>
    def getActiveUsers(self):

        ulFile = "userlog.txt"  
        activeUserStrings = []

        # Server display
        print(f"\n{self.username} issued /activeuser command.")
        print("\nReturn active user list:")

        activerUser_response = {
            "header": "activeUser",
            "userList": activeUserStrings
        }

        # Read userlog file
        with open(ulFile, 'r') as f:
            for line in f:
                _, dateTime, user, ipAddress, udp_port_num = line.strip().split('; ')
                if user != self.username:
                    responseString = f"\n{user}; {ipAddress}; active since {dateTime}; {udp_port_num}.\n"
                    print(responseString)
                    activeUserStrings.append(responseString)


        self.clientSocket.send(json.dumps(activerUser_response).encode())
    #<----------------------------------------------->



    # <---- METHOD: process logout ------>
    def processLogout(self):

        ulFile = "userlog.txt"
        lines = []
        seqNum = 0

        logout_response = {
            "header": "logout",
            "success": False
        }

        with open(ulFile, 'r') as f:
            lines = f.readlines()

        # Server display
        print(f"\n{self.username} has logged out.\n")
        print("Current active user list:\n")

        # Remove user from the user log
        with open(ulFile, 'w') as f:
            for line in lines:

                seqNum += 1

                _, dateTime, user, ipAddress, udp_port_num = line.strip().split('; ')

                # Write back all the users except current user + adjust sequence numbers
                if user != self.username:
                    f.write(f"{seqNum}; {dateTime}; {user}; {ipAddress}; {udp_port_num}\n")
                    print(f"{user}; {ipAddress}; active since {dateTime}; {udp_port_num}.\n")

        # Remove user from thread dict
        if self.username in active_clients:
            del active_clients[self.username]
            # At this point, logout has processed correctly
            logout_response["success"] = True

        self.clientSocket.send(json.dumps(logout_response).encode())
        
        # End thread
        self.clientAlive = False

    #<----------------------------------------------->
                
    # <---- METHOD: Send message ------>
    def sendMessage(self, sender, recipient, message):

        recipient_thread = active_clients.get(recipient)

        if recipient_thread:
            try:
                currentTime = datetime.now()
                formattedTime = currentTime.strftime('%d %b %Y %H:%M:%S')

                # Relay the message
                recipient_thread.clientSocket.send(json.dumps({
                    "header": "message",
                    "timeSent": formattedTime,
                    "from": sender,
                    "message": message
                }).encode())

                # return message confirmation to sender
                self.clientSocket.send(json.dumps({
                    "header": "confirmSentMessage",
                    "timeSent": formattedTime
                }).encode())

                # Add message to message log
                messageLogManager(sender, message)
                
            except Exception as e:
                print(f"Error sending message to {recipient}: {e}")
    #<----------------------------------------------->

    # <---- METHOD: Create group ------>
    def createGroup(self, creator, groupname, participants):

        # Display to server
        print(f"\n{creator} issued /creategroup command\n")

        createGroup_response = {
            "header": "createGroup",
            "success": False,
            "message": ""
        }

        # Group name already exists
        if groupname in groups:
            createGroup_response["message"] = f"\nA group chat (Name: {groupname}) already exists"
            self.clientSocket.send(json.dumps(createGroup_response).encode())
            print(f"Return message:\nGroup chat was not created. {createGroup_response['message']}")
            return
       
        inactive_users = [user for user in participants if user not in active_clients]

        # A participant is not active
        if inactive_users:
            createGroup_response["message"] = f"\nCannot create group as the following participant(s) are inactive: {', '.join(inactive_users)}"
            self.clientSocket.send(json.dumps(createGroup_response).encode())
            print(f"Return message:\nGroup chat was not created. {createGroup_response['message']}")
            return            

        # Add group members + groupname to group dict
        groups[groupname] = []
        groups[groupname].append({"username": creator, "hasJoined": True})

        for participant in participants:
            groups[groupname].append({"username": participant, "hasJoined": False})

        # Generate group message log
        groupMessageLogManager(groupname, creator, "")            

        # Set the users join state
        for user in groups[groupname]:
            if user["username"] == self.username:
                user["hasJoined"] = True
                break

        # Send success result
        createGroup_response["success"] = True
        participants_str = ", ".join(participants)
        createGroup_response["message"] = f"\nGroup chat has been created, room name: {groupname}. Users in this room: {participants_str}."
        self.clientSocket.send(json.dumps(createGroup_response).encode())
       
        # Display to server
        print(f"Return message:\n{createGroup_response['message']}")
    #<----------------------------------------------->


    # <---- METHOD: Join group ------>
    def joinGroup(self, groupname):

        # Display to server
        print(f"\n{self.username} issued /joingroup command\n")

        joinGroup_response = {
            "header": "joinGroup",
            "success": False,
            "message": ""
        }

        # Group name doesn't exist
        if groupname not in groups:
            joinGroup_response["message"] = f"\ngroup chat (Name: {groupname}) does not exist.\n"
            self.clientSocket.send(json.dumps(joinGroup_response).encode())
            print(f"Return message:\nGroup chat was not joined. {joinGroup_response['message']}")
            return
    
        # User is not a participant of group
        groupParticipant = any(particpant["username"] == self.username for particpant in groups[groupname])

        if not groupParticipant:
            joinGroup_response["message"] = f"\nYou have not been added to the group (Name: {groupname}).\n"
            self.clientSocket.send(json.dumps(joinGroup_response).encode())
            print(f"Return message:\nGroup chat was not joined. {joinGroup_response['message']}")
            return          

        # User has already joined the group
        participant = next((participant for participant in groups[groupname] if participant["username"] == self.username), None)

        if participant["hasJoined"]:
            joinGroup_response["message"] = f"\nYou have already joined group chat {groupname}.\n"
            self.clientSocket.send(json.dumps(joinGroup_response).encode())
            print(f"Return message:\nGroup chat was not joined. {joinGroup_response['message']}")
            return              

        # get participant names
        participants = [participant["username"] for participant in groups[groupname]]
         
        # Set the users join state
        for user in groups[groupname]:
            if user["username"] == self.username:
                user["hasJoined"] = True
                break
        
        # Send success result
        joinGroup_response["success"] = True
        participants_str = ", ".join(participants)
        joinGroup_response["message"] = f"\nGroup chat has been joined, room name: {groupname}. Users in this room: {participants_str}."
        self.clientSocket.send(json.dumps(joinGroup_response).encode())
       
        # Display to server
        print(f"Return message:\n{joinGroup_response['message']}")
    #<----------------------------------------------->

    # <---- METHOD: Message group ------>
    def messageGroup(self, groupname, message):

        # Display to server
        print(f"\n{self.username} issued /groupmsg command\n")

        msgGroup_response = {
            "header": "confirmGroupMessage",
            "success": False,
            "message": ""
        }

        # Group name doesn't exist
        if groupname not in groups:
            msgGroup_response["message"] = f"\ngroup chat (Name: {groupname}) does not exist.\n"
            self.clientSocket.send(json.dumps(msgGroup_response).encode())
            print(f"Return message:\nGroup chat was not messaged. {msgGroup_response['message']}")
            return
    
        # User is not a participant of group
        groupParticipant = any(particpant["username"] == self.username for particpant in groups[groupname])

        if not groupParticipant:
            msgGroup_response["message"] = f"\nYou have not been added to the group (Name: {groupname}).\n"
            self.clientSocket.send(json.dumps(msgGroup_response).encode())
            print(f"Return message:\nGroup chat was not messaged. {msgGroup_response['message']}")
            return 

        # User is a participant but has not joined
        participant = next((participant for participant in groups[groupname] if participant["username"] == self.username), None)

        if not participant["hasJoined"]:
            msgGroup_response["message"] = f"\nPlease join the group before sending messages, via /joingroup {groupname}.\n"
            self.clientSocket.send(json.dumps(msgGroup_response).encode())
            print(f"Return message:\nGroup chat was not messaged. {msgGroup_response['message']}")
            return        

        # Send success result back to sender
        msgGroup_response["success"] = True
        msgGroup_response["message"] = f"\nMessage to group chat {groupname} has been sent."
        self.clientSocket.send(json.dumps(msgGroup_response).encode())
       
        # Send messages to participants of groupchat
        activeParticipants = [participant["username"] for participant in groups[groupname] 
                    if participant["hasJoined"] and participant["username"] != self.username]
       
        groupMessageLogManager(groupname, self.username, message)

        # Broadcast message to active participants in group
        if activeParticipants:
            for recipient in activeParticipants:

                recipient_thread = active_clients.get(recipient)

                if recipient_thread:
                    try:
                        currentTime = datetime.now()
                        formattedTime = currentTime.strftime('%d %b %Y %H:%M:%S')

                        # Relay the message
                        recipient_thread.clientSocket.send(json.dumps({
                            "header": "groupMessage",
                            "timeSent": formattedTime,
                            "groupName": groupname,
                            "from": self.username,
                            "message": message
                        }).encode())

                    except Exception as e:
                        print(f"Error sending message to group chat {groupname}: {e}")


        # Display to server
        print(f"Return message:\n{msgGroup_response['message']}")
    #<----------------------------------------------->


    # <---- METHOD: Confirm UDP ------>
    def confirmUDP(self, message):
        print("recv server")
        confirmUDP_response = {
            "header": "confirmUDP",
            "message": message
        }

        self.clientSocket.send(json.dumps(confirmUDP_response).encode())
    #<----------------------------------------------->

#-------------------------------- END CLASS DEFINITION -----------------------------------#



def main():

    global allowedAttempts

    # Get port and set attempt no's
    try:
        serverPort, allowedAttempts = serverArgHandler()
    except ValueError as error:
        print(f"{error}", file=sys.stderr)
        sys.exit(1)


    # Set host on localhost
    serverHost = "127.0.0.1"
    serverAddress = (serverHost, serverPort)

    # define socket for the server side and bind address
    serverSocket = socket(AF_INET, SOCK_STREAM)
    serverSocket.bind(serverAddress)

    print(f"\n===== Server is running @ {serverHost}, port:{serverPort} =====")
    print("===== Waiting for connection request from clients... =====")


    # Loop listening
    try:
        while True:
            serverSocket.listen()
            clientSocket, clientAddress = serverSocket.accept()
            clientThread = ClientThread(clientAddress, clientSocket)
            clientThread.start()
            
    except KeyboardInterrupt:
        print("\nExiting on keyboard interrupt...")
    finally:
        serverSocket.close()
        print("Server socket is now closed.")
        sys.exit(0)

if __name__ == "__main__":
    main()




