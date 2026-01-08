import socket
import struct
import threading
import time

UDP_DEST_PORT = 13122  # The client needs to listen for the offer message on 13122 UDP port
MAGIC_COOKIE = 0xabcddcba
MSG_TYPE_OFFER = 0x2  # Offer
SERVER_NAME = "MyBlackJackDealer"
TCP_PORT = 0  # The port at the offer

# Padding the server name to 32 bytes
SERVER_NAME_PADDED = SERVER_NAME.encode('utf-8').ljust(32, b'\0')


# Serialization to the offer packet
# I - Unsigned Int  = 4 bytes (Magic Cookie)
# B - Unsigned Byte = 1 byte (Message Type)
# H - Unsigned Short= 2 bytes (Server Port)
# 32s - String = 32 bytes (Server Name)

def broadcast_offers(server_port):  # offer
    """
        Broadcasts offer packets via UDP to announce the server's availability.

        This function is intended to be run in a separate background thread,
        so it does not block the main TCP connection logic.
    """
    # AF_INET= We are going to use regular IPv4 internet addresses.
    # SOCK_DGRAM= UDP (Datagram)
    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    # enable Broadcast
    udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

    packet = struct.pack('I B H 32s', MAGIC_COOKIE, MSG_TYPE_OFFER, server_port, SERVER_NAME_PADDED)

    print(f"Dealer started broadcasting on UDP port {UDP_DEST_PORT}...")

    while True:
        try:
            udp_socket.sendto(packet, ('<broadcast>', UDP_DEST_PORT))
            time.sleep(1)
        except Exception as e:
            print(f"Broadcast error: {e}")


def handle_player(conn, addr):  # payload, request
    """
        Handles the communication session with a single connected player.
        Args:
            conn (socket.socket): The active socket object representing the connection.
            addr (tuple): A tuple containing the client's (IP, Port).

        Returns:
            None
    """
    with conn:
        try:
            # header = magic cookie 4 + type 1 = 5
            header_data = conn.recv(5)

            if len(header_data) < 5:
                print("Packet too short, closing connection.")
                return

            # (Unpack)
            # I = 4 bytes (Cookie), B = 1 byte (Type)
            cookie, msg_type = struct.unpack('I B', header_data)

            # Check the Magic Cookie:
            if cookie != MAGIC_COOKIE:
                print(f"Invalid Cookie: {hex(cookie)}. Kicking player out!")
                return

            # check the type:
            if msg_type == 0x3:
                print("Got Request message (0x3). Starting game logic...")
                # כאן תקראי את שאר ההודעה (למשל שם השחקן) ותתחילי משחק

            elif msg_type == 0x4:
                print("Got Payload message (0x4). Processing move...")
                # כאן מטפלים במהלך המשחק

            else:
                print(f"Unknown message type: {msg_type}")

        except Exception as e:
            print(f"Error handling player {addr}: {e}")

    print(f"Connection with {addr} closed.")


def start_dealer():
    """
        Initializes and starts the main server loop to accept incoming player connections.
        This function sets up the TCP/IP socket, binds it to the configured host and port,
        and listens for new clients. When a client connects, it delegates the session
        management to `handle_player` (typically in a new thread).
    """
    # Create TCP
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
        server_socket.bind(('0.0.0.0', 0))  # "choose a port for me"
        server_socket.listen()

        server_ip, server_port = server_socket.getsockname()
        print(f"Dealer is listening on TCP IP {server_ip} and PORT {server_port}")

        broadcast_thread = threading.Thread(target=broadcast_offers, args=(server_port,))
        broadcast_thread.daemon = True
        broadcast_thread.start()

        # get players
        while True:
            conn, addr = server_socket.accept()

            # If a new player came, we send him to the handle_player func
            client_thread = threading.Thread(target=handle_player, args=(conn, addr))
            client_thread.start()


if __name__ == '__main__':
    start_dealer()
