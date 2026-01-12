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
        team_name = "Unknown"
        with conn:
            try:
                # header = magic cookie 4 + type 1 = 5
                conn.settimeout(60.0)

                header_data = self.all_recv(conn, 5)

                if header_data is None:
                    print("Connection lost while waiting for header.")
                    return None

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

                    remaining_data = self.all_recv(conn, 33)
                    if remaining_data is None:
                        print("Connection lost while waiting for header.")
                        return None

                    if len(remaining_data) < 33:
                        print("Incomplete request packet")
                        return

                    rounds, team_name_bytes = struct.unpack('!B 32s', remaining_data)
                    team_name = team_name_bytes.decode('utf-8').strip('\x00')

                    print(f"{team_name} connected requesting {rounds} rounds.")

                    # step 4
                    print(f"Welcome to the Game {team_name}!")
                    self.play(conn, rounds, team_name)

                else:
                    print(f"Unknown message type: {msg_type}")

            except socket.timeout:
                print(f" {team_name} it's been over a minute since you responded, are you cheating?! I'm kicking you "
                      f"out!")

            except Exception as e:
                print(f"Error handling player {addr}: {e}")


        print(f"Connection with {team_name} closed.")

    def current_dealer_sum(self,dealer_hand):
        """
                Calculates the total value of the cards currently in the dealer's hand.

                Returns:
                    int: The cur sum of the card values.
         """
        total_sum = 0
        for card in dealer_hand:
            total_sum += card.get_value()
        return total_sum

    def all_recv(self, sock, n):
        data = b''
        try:
            while len(data) < n:
                more = sock.recv(n - len(data))
                if not more:
                    print("Connection closed before receiving full data")
                    return
                data += more
            return data
        except (ConnectionResetError, ConnectionAbortedError):
            return None
        except Exception as e:
            print(f"Unexpected error during recv: {e}")
            return None

    def send_payload_card(self, conn, result, card):
        """
        result: 0x0 / 0x1 / 0x2 / 0x3
        card: Card object
        """
        packet = struct.pack(
            '!I B B H B',
            MAGIC_COOKIE,
            MSG_TYPE_PAYLOAD,
            result,
            card.rank,
            card.suit
        )
        conn.sendall(packet)

    def send_payload_result(self, conn, result):
        packet = struct.pack(
            '!I B B',
            MAGIC_COOKIE,
            MSG_TYPE_PAYLOAD,
            result
        )
        conn.sendall(packet)

    def play(self, conn, rounds, team):
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

        # Statistics
        statistics = {
            "wins": 0,
            "losses": 0,
            "ties": 0
        }

        for round_num in range(1, rounds + 1):

            time.sleep(1)
            print(f"\n==={team} starting round {round_num} ===")

            # Initial Deal - round 0:
            deck = Deck()  # Deck to each thread
            deck.shuffle()

            player_hand = []
            dealer_hand = []

            player_hand.append(deck.deal_one())
            dealer_hand.append(deck.deal_one())  # The player will see it
            player_hand.append(deck.deal_one())
            dealer_hand.append(deck.deal_one())  # The player cannot see it

            self.send_payload_card(conn, 0x0, player_hand[0])
            self.send_payload_card(conn, 0x0, player_hand[1])
            self.send_payload_card(conn, 0x0, dealer_hand[0])

            player_total = sum([card.get_value() for card in player_hand])
            print(f"{team} initial cards: {[c.print_card() for c in player_hand]}")
            print(f"{team} total: {player_total}")
            print(f"Dealer that play with {team} visible card: {dealer_hand[0].print_card()}")
            print(f"Dealer that play with {team} invisible card: {dealer_hand[1].print_card()}")
            print(f"Dealer that play with {team} total: {self.current_dealer_sum(dealer_hand)}")

            flag = True
            while flag:
                conn.settimeout(60.0)
                # (Hittt / Stand)
                try:
                    # checking fo new msg:
                    new_header = self.all_recv(conn, 5)

                    if not new_header:
                        print(f"Connection lost with {team}. Closing session.")
                        return

                    cookie, m_type = struct.unpack('!I B', new_header)

                    # Check the Magic Cookie:
                    if cookie != MAGIC_COOKIE:
                        print(f"Invalid Cookie: {hex(cookie)}. Kicking player out!")
                        return

                    if m_type != MSG_TYPE_PAYLOAD:
                        print(
                            f"Protocol Error: Received MSG_TYPE {hex(m_type)} instead of 0x4 from {team}. Kicking player out!")
                        return

                    else:

                        decision_data = self.all_recv(conn, 5)

                        if not decision_data:
                            print(f"Failed to receive move content from {team}.")
                            return

                        move = struct.unpack('!5s', decision_data)[0].decode('utf-8').strip()

                        if move == "Stand":
                            print(f"{team} decision: {move}")
                            flag = False
                            break

                        elif move == "Hittt":
                            print(f"Player decision: {move}")
                            new_card = deck.deal_one()
                            player_hand.append(new_card)
                            player_total = sum([c.get_value() for c in player_hand])
                            self.send_payload_card(conn, 0x0, new_card)
                            print(f"{team} received: {new_card.print_card()}")
                            print(f"{team} total: {player_total}")
                            if player_total > 21:

                                flag = False
                                break

                        else:
                            print(
                                f"Illogical move received: '{move}' from {team}. Protocol violation! Kicking player out.")
                            return
                except socket.timeout:
                    print(f"{team} took too long to respond this turn! Kicking out.")
                    return

                except Exception as e:
                    print(f"Error during {team}'s turn: {e}")
                    return

            time.sleep(1)
            if player_total > 21:
                print(f"{team} busts! Dealer wins this round")
                self.send_payload_result(conn, 0x2)  # player loss
                statistics["losses"] += 1
                continue
            # dealer
            self.send_payload_card(conn, 0x0, dealer_hand[1])
            dealer_total = self.current_dealer_sum(dealer_hand)
            while dealer_total < 17:
                new_card = deck.deal_one()
                dealer_hand.append(new_card)
                dealer_total = self.current_dealer_sum(dealer_hand)
                self.send_payload_card(conn, 0x0, new_card)
                print(f"Dealer that play with {team}received: {new_card.print_card()}")
                print(f"Dealer that play with {team} total: {dealer_total}")

            # Deciding winner
            result = 0x0
            if dealer_total > 21:
                result = 0x3
                print(f"Result: Dealer busts, {team} wins.")
                statistics["wins"] += 1
            else:
                if player_total > dealer_total:
                    result = 0x3
                    print(f"Result: {team} has higher total, wins.")
                    statistics["wins"] += 1
                elif dealer_total > player_total:
                    result = 0x2
                    print(f"Result: Dealer has higher total, {team} loses.")
                    statistics["losses"] += 1
                else:
                    result = 0x1
                    print(f"Result: Tie! {team}: {player_total}, Dealer: {dealer_total}")
                    statistics["ties"] += 1

            self.send_payload_result(conn, result)
            print(f"End of round {round_num} for {team}")

        print(f"\n{team} - All rounds finished")
        total_played = statistics["wins"] + statistics["losses"] + statistics["ties"]
        win_rate = statistics["wins"] / total_played if total_played > 0 else 0
        print(f"{team} finished {total_played} rounds, win rate: {win_rate:.2f}")

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
