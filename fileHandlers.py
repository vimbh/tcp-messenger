# Written by Vimukthi Herath

import time
from datetime import datetime

# Checks block status
def userBlocked(username, allowedAttempts):

    currentTime = time.time()

    arFile = "attempt_records.txt"
    # Read file contents if exists / add user to attempts record if file doesn't exist
    try:        
        with open(arFile, 'r') as f:
            lines = f.readlines()

        for line in lines:
            user, attempts, lastAttemptTime = line.strip().split()

            if user == username:

                # > 10 seconds passed, no longer blocked
                if currentTime - float(lastAttemptTime) > 10:
                    return False

                # < 10 seconds + attempts exceeded
                if int(attempts) >= allowedAttempts:
                    return True

    except FileNotFoundError:
        # Cant be blocked if file not found
        return False



# Similar to block status, but writes updated values to file
# Returns a tuple: (errorMessage, blockStatus)
def handleIncorrectLogin(username, allowedAttempts):

    arFile = "attempt_records.txt"
    message = "Invalid Password. Please try again" # default error message
    userFound = False
    lines = []
    currentTime = time.time()
    blockStatus = False

    # Read file contents if exists / add user to attempts record if file doesn't exist
    try:        
        with open(arFile, 'r') as f:
            lines = f.readlines()
    except FileNotFoundError:
        with open(arFile, 'w') as f:
            # If the file was empty, we add the user with an attempt count of 1
            f.write(f"{username} 1 {time.time()}\n")
            return message, blockStatus

    with open(arFile, 'w') as f:
        for line in lines:
            user, attempts, lastAttemptTime = line.strip().split()
        
            # User already has an entry in the attempts record
            if user == username:

                userFound = True

                # If it's been more than 10 seconds, clear the last entry and set this attempt to the first attempt
                if currentTime - float(lastAttemptTime) > 10:
                    currentAttempt = 1
                else:
                    currentAttempt = int(attempts) + 1

                # Check no. of attempts
                if currentAttempt == allowedAttempts:
                    message = "Invalid Password. Your account has been blocked. Please try again later\n"
                    blockStatus = True
                # attempts exceeded < 10 seconds since last entry
                elif currentAttempt > allowedAttempts:
                    message = "Your account is blocked due to multiple login failures. Please try again later\n"
                    blockStatus = True

                attempts = currentAttempt

            # Write lines back to file
            f.write(f"{username} {attempts} {time.time()}")

        # If the user wasn't found in the records, add them to the records
        if not userFound:
            f.write(f"{username} 1 {time.time()}\n")

    return message, blockStatus


# Writes the active user to the userlog
def userLogManager(username, client_address, client_udp_port):

    ulFile = "userlog.txt"
    currentTime = datetime.now()
    formattedTime = currentTime.strftime('%d %b %Y %H:%M:%S')

    try:        
        # Get the last sequence number
        with open(ulFile, 'r') as f:
            seqNumber = sum(1 for _ in f)

        # Append new user to userlog
        with open(ulFile, 'a') as f:
            f.write(f"{int(seqNumber)+1}; {formattedTime}; {username}; {client_address[0]}; {client_udp_port}\n")

    # Create the first entry
    except FileNotFoundError:
        with open(ulFile, 'w') as f:
            # Add the user with an attempt count of 1
            f.write(f"1; {formattedTime}; {username}; {client_address[0]}; {client_udp_port}\n")



# Writes a message to the message log 
def messageLogManager(username, message):

    ulFile = "messagelog.txt"
    currentTime = datetime.now()
    formattedTime = currentTime.strftime('%d %b %Y %H:%M:%S')

    try:        
        # Get the last sequence number
        with open(ulFile, 'r') as f:
            msgNumber = sum(1 for _ in f)

        # Append new user to userlog
        with open(ulFile, 'a') as f:
            f.write(f"{int(msgNumber)+1}; {formattedTime}; {username}; {message}\n")

    # Create the first entry
    except FileNotFoundError:
        with open(ulFile, 'w') as f:
            # Add the user with an attempt count of 1
            f.write(f"1; {formattedTime}; {username}; {message}\n")


# Writes a message to a groups message log 
def groupMessageLogManager(groupname, username, message):

    ulFile = f"{groupname}_messagelog.txt"

    currentTime = datetime.now()
    formattedTime = currentTime.strftime('%d %b %Y %H:%M:%S')

    try:

        # Get the last sequence number
        with open(ulFile, 'r') as f:
            msgNumber = sum(1 for _ in f)

        # Append new user to userlog
        with open(ulFile, 'a') as f:
            f.write(f"{int(msgNumber)+1}; {formattedTime}; {username}; {message}\n")

    # Create the file (leave empty)
    except FileNotFoundError:
        with open(ulFile, 'w') as f:
            pass
        
