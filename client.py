#!/usr/bin/python3

# Written by Vimukthi Herath

from socket import *
import sys
import time
import json
import os
from threading import Thread
import queue
import select
from argHandlers import clientArgHandler 

# Global variables
loggedIn = False
blocked = False
sessionEnded = False
responseLoading = False
inputQueue = queue.Queue() # Each element in the queue represents a response from the server awaiting processing.
activeUserInfo = {} # Store information on active users on each active user call

# Input handler which allows for server responses to be checked for while waiting for user input
# required as stdLibs input() is blocking
def nonBlockInput(prompt, timeout=0.1):
    
    # Only print prompt when there are no server responses to process
    if inputQueue.empty():
        print(prompt, end='', flush=True)
    
    # Wait for stdin at input. Intermittently check for server responses.
    while True:
        readable, _, _ = select.select([sys.stdin], [], [], timeout)
        
        # If stdin buffer is not empty, process input
        if readable:
            return sys.stdin.readline().rstrip()

        # If the queue is not empty, process queued server responses
        if not inputQueue.empty():
            inputQueue.get() 
            return

# Handle usage errors for all commands
# Returns a tuple: (UsageErrorBool, errorMsg)
def commandUsageHandler(command, args):

    global activeUserInfo

    if command == '/activeuser':
        if len(args) != 1:
            raise ValueError("\nUsage error: no arguments should be provided to /activeuser\n")
        
    if command == '/msgto':
        if len(args) < 3:
            raise ValueError("\nUsage error: /msgto USERNAME MESSAGE_CONTENT\n")

    if command == '/logout':
        if len(args) != 1:
            raise ValueError("\nUsage error: no arguments should be provided to /logout\n")
        
    if command == '/creategroup':
         if len(args) < 3:
            raise ValueError("\nUsage error: /creategroup GROUPNAME USERNAME_1 [USERNAME_2 ...]\n")
         
         if not args[1].isalnum():
            raise ValueError("\nError: Group name must only contain letters and digits.\n")

    if command == '/joingroup':
        if len(args) != 2:
            raise ValueError("\nUsage error: /joinegroup GROUPNAME\n")

    if command == '/groupmsg':
         if len(args) < 3:
            raise ValueError("\nUsage error: /groupmsg GROUPNAME MESSAGE_CONTENT\n")
         
    if command == '/p2pvideo':
        if len(args) != 3:
            raise ValueError("\nUsage error: /p2pvideo USERNAME FILENAME\n")
        
        username = args[1]
        if username not in activeUserInfo:
            raise ValueError(f"{username} appears to be offline. Run /activeuser to see if they are online.\n")


# Send video via UDP
def sendVideoUDP(presenter_username, audience_username, filename):

    try:
        # Lookup user address
        audience_host, audience_port = activeUserInfo[audience_username]
        audience_address = (audience_host, int(audience_port.strip('.').strip()))

        # Send file via UDP
        with socket(AF_INET, SOCK_DGRAM) as udp_socket, open(filename, 'rb') as f:
            
            # Send presenter username
            udp_socket.sendto(presenter_username.encode(), audience_address)
            
            # Send filename
            udp_socket.sendto(filename.encode(), audience_address)
            
            # Send file
            while True:
                file_content = f.read(1024)

                if not file_content:
                    # Send a packet to signify EOF as UDP is connectionless
                    udp_socket.sendto(b"EOF", audience_address)
                    break

                udp_socket.sendto(file_content, audience_address)

        print(f"\nVideo file {filename} has been sent to {audience_username}.\n")

    except Exception as e:
        print(f"Error in sending file via UDP: {e}")

# Receive video via UDP; runs on a explicit UDP thread.
# Note the clientSocket is NOT used for file transfer, 
# it is just used to emit a message to the recipient when file transfer is complete.
def receiveVideoUDP(addressUDP, clientSocket):

    global inputQueue

    try:
        # run UDP socket
        with socket(AF_INET, SOCK_DGRAM) as udp_socket:
            udp_socket.bind(addressUDP)

            # Receive the presenters username first
            presenter_username, _ = udp_socket.recvfrom(1024)
            presenter_username = presenter_username.decode()
            
            # Receive the file name
            filename, _ = udp_socket.recvfrom(1024)
            filename = filename.decode() 
            name, extension = os.path.splitext(filename)
            filename = name + '_received' + extension

            with open(filename, 'wb') as f:
                while True:
                    data, _ = udp_socket.recvfrom(1024)
                    if data == b'EOF':
                        break
                    f.write(data)
        

        # Send a TCP message on completion to confirm the send on the recipient side
        confirmUDP_request = {
            "header": "confirmUDP",
            "message": f"Received video file from {presenter_username}, saved as {filename}"
        }
        clientSocket.sendall(json.dumps(confirmUDP_request).encode())

    except Exception as e:
        print(f"Error in receiving file via UDP: {e}")


# Receive and display server responses via TCP; runs on an explicit TCP thread.
# Seperates client listening to server & client waiting for input.
def serverListener(socket):

    global loggedIn, blocked, sessionEnded, responseLoading, activeUserInfo


    while True:

        try:

            # Each response is a json object, for which the header tag defines the response type
            raw_response = socket.recv(1024).decode()
            response = json.loads(raw_response)
            key = response["header"]

            if key == "login":
                if response["success"]:
                    print("\nWelcome to Tessenger!\n")
                    loggedIn = True
                else:
                    print(f"\n{response['errorMessage']}\n")
                    if response['blocked']:
                        blocked = True

                responseLoading = False
            
            elif key == "confirmSentMessage":
                inputQueue.put(1)
                print(f"\nmessage sent at {response['timeSent']}")

            elif key == "message":
                inputQueue.put(1)
                print("\n")
                print(f"{response['timeSent']}, {response['from']}: {response['message']}\n")
                
            elif key == "activeUser":

                if not response["userList"]:
                    inputQueue.put(1)
                    print("\nNo currently active users.")
                else:
                    inputQueue.put(1)
                    for str in response["userList"]:
                        user, host_address, _, udp_port = str.strip().split('; ')
                        activeUserInfo[user] = (host_address, udp_port)

                        # Output information
                        print(str)

            elif key == "createGroup":
                inputQueue.put(1)
                print(response["message"])

            elif key == "joinGroup":
                inputQueue.put(1)
                print(response["message"])

            elif key == "confirmGroupMessage":
                print(response["message"])

            elif key == "groupMessage":
                inputQueue.put(1)
                print("\n")
                print(f"{response['timeSent']}, {response['groupName']}, {response['from']}: {response['message']}\n")

            elif key == "confirmUDP":
                print("recv")
                inputQueue.put(1)
                print(f"\n{response['message']}")

            elif key == "logout":
                if response["success"]:
                    print(f"\nYou have successfully logged out. Goodbye!\n")
                    sessionEnded = True
                    break
                else:
                    print("\nAn error occured while logging out.\n")
            
            elif key == "unkown":
                print(response["message"])

        except Exception as e:

            print(f"\nError receiving data: {e}\n")
            break


def main():

    # Set loading response
    global responseLoading

    # Get port and set attempt no's
    try:
        serverHost, serverPort, udp_serverPort = clientArgHandler()
    except ValueError as error:
        print(f"{error}", file=sys.stderr)
        sys.exit(1)

    # Connect client to server
    serverAddress = (serverHost, serverPort)
    clientSocket = socket(AF_INET, SOCK_STREAM)
    clientSocket.connect(serverAddress)

    # Thread for listening to server independently (TCP)
    listeningThread = Thread(target=serverListener, args=(clientSocket,), daemon=True)
    listeningThread.start()

    # Thread for UDP
    addressUDP = (serverHost, udp_serverPort)
    receiver_thread = Thread(target=receiveVideoUDP, args=(addressUDP, clientSocket), daemon=True)
    receiver_thread.start()

    # Set of possible commands
    possibleCommands = {'/msgto', '/activeuser', '/creategroup', '/joingroup', '/groupmsg', '/p2pvideo', '/logout'}

    try:

        print("\nPlease login\n")

        # Loop listening to server
        while True:
            
            # Exit program if user is blocked
            if blocked:
                clientSocket.close()
                sys.exit(1)
            
            #=================== Login loop ======================#
            
            while not loggedIn:

                if not responseLoading and not loggedIn:
                    username = input("Username: ")
                    password = input("Password: ")

                    auth_request = {
                        "header": "login",
                        "username": username,
                        "password": password,
                        "udp_port": udp_serverPort
                    }

                    responseLoading = True
                    clientSocket.sendall(json.dumps(auth_request).encode())


            # Force sleep to let "Welcome" message resolve first
            time.sleep(0.1)

            #=================== Possible commands loop ======================#
            
            # Exit program if user logs out
            if sessionEnded:
                clientSocket.close()
                break

            # Process user input. If return userInput after processing is null,
            # We're still waiting for server responses to be processed. Start loop again.
            userInput = nonBlockInput("\nEnter one of the following commands (/msgto, /activeuser, /creategroup, /joingroup, /groupmsg, /p2pvideo, /logout): ")
            if not userInput:
                continue
       
            # Get input arguments
            inputArgs = userInput.split()
            commandName = inputArgs[0]

            # Nonsensical command
            if commandName not in possibleCommands:
                print("Error: Invalid command.\n")
                continue

            # Catch command usage errors:
            try:
                commandUsageHandler(commandName, inputArgs)
            except ValueError as e:
                print(e)
                continue           

            # /activeuser
            if commandName == "/activeuser":

                activerUser_request = {
                    "header": "activeUser"
                }

                clientSocket.sendall(json.dumps(activerUser_request).encode())
                continue

            # /msgto
            elif commandName == '/msgto':

                recipient, message = inputArgs[1], ' '.join(inputArgs[2:])

                msg_request = {
                    "header": "sendMessage",
                    "sender": username,
                    "recipient": recipient,
                    "message": message
                }
                clientSocket.sendall(json.dumps(msg_request).encode())

            # /creategroup
            elif commandName == '/creategroup':
                
                groupName = inputArgs[1]
                users = inputArgs[2:]

                createGroup_request = {
                    "header": "createGroup",
                    "groupName": groupName,
                    "users": users
                }
                clientSocket.sendall(json.dumps(createGroup_request).encode())

            # /joingroup
            elif commandName == '/joingroup':
                
                groupName = inputArgs[1]

                joinGroup_request = {
                    "header": "joinGroup",
                    "groupName": groupName,
                }
                clientSocket.sendall(json.dumps(joinGroup_request).encode())

            # /groupmsg
            elif commandName == '/groupmsg':

                groupName, message = inputArgs[1], ' '.join(inputArgs[2:])
                
                messageGroup_request = {
                    "header": "messageGroup",
                    "groupName": groupName,
                    "message": message
                }
                clientSocket.sendall(json.dumps(messageGroup_request).encode())


            # /p2pvideo
            elif commandName == '/p2pvideo':

                audience, filename = inputArgs[1], inputArgs[2]
                sendVideoUDP(username, audience, filename)

            # /logout
            elif commandName == '/logout':

                logout_request = {
                    "header": "logout"
                }

                clientSocket.sendall(json.dumps(logout_request).encode())

            else:
                print("\nSorry, an uncaught error has occured.\n")     


    except KeyboardInterrupt as error:
        print("Client socket is now closed.")
    finally:
        clientSocket.close()
        exit(0)


    

if __name__ == "__main__":
    main()
