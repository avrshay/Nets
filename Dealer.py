import random
import socket
import struct
import threading
import time
from Cards import *

UDP_DEST_PORT = 13122  # The client needs to listen for the offer message on 13122 UDP port
MAGIC_COOKIE = 0xabcddcba
MSG_TYPE_OFFER = 0x2  # Offer
MSG_TYPE_REQUEST = 0x3
MSG_TYPE_PAYLOAD = 0x4
SERVER_NAME = "MyBlackJackDealer"
TCP_PORT = 0  # The port at the offer

"""
The Handshake:
step 1. Player Listen: The client opens a UDP Socket in passive mode and waits for requests from one of the dealers in the network.

step 2. Dealer Broadcast: The dealer sends messages containing offers to all listeners in the network using Broadcast in the UDP protocol.

step 3. Player Connect: The client receives the offer from the Broadcast, and in response initiates the creation of a TCP connection directly with the dealer who sent the offer.

step 4. Connection Established: The dealer receives the connection request, confirms it, and updates that an active connection has been created with the client.
"""


class Dealer:
    """
        Represents the Dealer in the Blackjack game.
        """
    def __init__(self):
        """
             Initializes the Dealer instance.
        """
        self.server_ip = None
        self.server_tcp_port = None
        self.tcp_socket = None
        self.deck = None
        self.dealer_hand = []

    # step 2:
    def broadcast_offers(self, server_port):  # offer - The client is generally a "UDP server" (listener), and the
        """
                Broadcasts offer packets via UDP to announce the server's availability.
                Intended to run in a separate background thread.

                The packet format is:
                - Magic Cookie (4 bytes)
                - Message Type (1 byte)
                - Server Port (2 bytes)
                - Server Name (32 bytes, padded)

                Args:
                    server_port (int): The TCP port number the dealer is listening on.
        """
        # server is
        # the one that sends (transmits) to it.

        # AF_INET= We are going to use regular IPv4 internet addresses.
        # SOCK_DGRAM= UDP (Datagram)
        udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        # enable Broadcast
        udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

        # The offer packet:
        # I - Unsigned Int  = 4 bytes (Magic Cookie)
        # B - Unsigned Byte = 1 byte (Message Type)
        # H - Unsigned Short= 2 bytes (Server Port)
        # 32s - String = 32 bytes (Server Name)

        # Padding the server name to 32 bytes
        SERVER_NAME_PADDED = SERVER_NAME.encode('utf-8').ljust(32, b'\0')
        packet = struct.pack('!I B H 32s', MAGIC_COOKIE, MSG_TYPE_OFFER, server_port, SERVER_NAME_PADDED)

        print(f"Dealer started broadcasting on UDP port {UDP_DEST_PORT}...")

        while True:
            try:
                # The server sends an Offer message to the whole world (Broadcast).
                udp_socket.sendto(packet, ('<broadcast>', UDP_DEST_PORT))
                time.sleep(1)
            except Exception as e:
                print(f"Broadcast error: {e}")

    def handle_player(self, conn, addr):  # payload, request
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
                cookie, msg_type = struct.unpack('!I B', header_data)

                # Check the Magic Cookie:
                if cookie != MAGIC_COOKIE:
                    print(f"Invalid Cookie: {hex(cookie)}. Kicking player out!")
                    return

                # check the type:
                if msg_type == MSG_TYPE_REQUEST:

                    remaining_data = conn.recv(33)
                    if len(remaining_data) < 33:
                        print("Incomplete request packet")
                        return

                    rounds, team_name_bytes = struct.unpack('!B 32s', remaining_data)
                    team_name = team_name_bytes.decode('utf-8').strip('\x00')

                    print(f"{team_name} connected requesting {rounds} rounds.")

                    # step 4?
                    print("Welcome to the Game!")
                    for round in range(1,rounds+1):
                        print(f"---Round {round}---")
                        self.play(conn)

                else:
                    print(f"Unknown message type: {msg_type}")

            except Exception as e:
                print(f"Error handling player {addr}: {e}")

        print(f"Connection with {addr} closed.")

    def current_dealer_sum(self):
        """
                Calculates the total value of the cards currently in the dealer's hand.

                Returns:
                    int: The cur sum of the card values.
         """
        total_sum = 0
        for card in self.dealer_hand:
            total_sum += card.get_value()
        return total_sum

    def play(self, conn):
        """
                Manages the main game loop for a specific client connection.

                Responsibilities:
                1. Initializes the deck and deals initial cards.
                2. Sends initial game state to the player.
                3. Waits for player actions (Hit/Stand) via the protocol.
                4. Executes dealer logic.
                5. Determines the winner and sends the result.

                Args:
                    conn (socket.socket): The active TCP socket for communication.
        """
        # Initial Deal - round 0:
        self.deck = Deck()
        self.deck.shuffle()

        player_hand = []

        player_hand.append(self.deck.deal_one())
        self.dealer_hand.append(self.deck.deal_one())  # The player will see it
        player_hand.append(self.deck.deal_one())
        self.dealer_hand.append(self.deck.deal_one())  # The player cannot see it

        #if self.current_dealer_sum() > 21:
        #    pass  # זה לא אמור להחשף עד תורו

        while True:

            # (Hittt / Stand)
            try:
                # checking fo new msg:
                new_header = conn.recv(5)

                if not new_header:
                    print(f"Failed.")
                    break

                cookie, m_type = struct.unpack('!I B', new_header)

                # Check the Magic Cookie:
                if cookie != MAGIC_COOKIE:
                    print(f"Invalid Cookie: {hex(cookie)}. Kicking player out!")
                    return

                if m_type == MSG_TYPE_PAYLOAD:

                    decision_data = conn.recv(5)

                    move = struct.unpack('!5s', decision_data)[0].decode('utf-8')

                    print(f"Player Move: {move}")

                    if move == "Stand":

                        # דילר משחק, מחשבים מנצח, שולחים תוצאה ויוצאים מהלולאה (לסיבוב הבא)

                        break

                    elif move == "Hittt":

                        # דילר שולח עוד קלף וחוזרים לתחילת הלולאה

                        pass

                else:
                    print("Failed 1")

            except Exception as e:
                print(e)
                break


    def start_dealer(self):
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

            broadcast_thread = threading.Thread(target=self.broadcast_offers, args=(server_port,))
            broadcast_thread.daemon = True
            broadcast_thread.start()

            # get players
            while True:
                conn, addr = server_socket.accept()

                # If a new player came, we send him to the handle_player func
                client_thread = threading.Thread(target=self.handle_player, args=(conn, addr))
                client_thread.start()


if __name__ == '__main__':
    dealer = Dealer()
    dealer.start_dealer()
