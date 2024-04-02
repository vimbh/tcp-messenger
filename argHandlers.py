
# Written by Vimukthi Herath

import sys

# Handles argument errors for client.py
def clientArgHandler():

    if len(sys.argv) != 4:
        raise ValueError("\n===== Usage error: python3 TCPClient3.py SERVER_IP SERVER_PORT CLIENT_UDP_SERVER_PORT ======\n")

    return sys.argv[1], int(sys.argv[2]), int(sys.argv[3])

# Handles argument errors for server.py
def serverArgHandler():

    if len(sys.argv) != 3:
        raise ValueError("\n===== Usage error: python3 TCPServer3.py SERVER_PORT NO_ALLOWED_ATTEMPTS ======\n")

    try:
        port = int(sys.argv[1])
        attempts = int(sys.argv[2])

        if attempts < 1 or attempts > 6 :
            raise ValueError(f"Invalid number of allowed failed consecutive attempt: {attempts}")
        else:
            return port, attempts

    except ValueError:

        raise ValueError(f"Invalid number of allowed failed consecutive attempt: {attempts}")
