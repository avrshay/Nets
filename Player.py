import socket
import struct

from Cards import Card

UDP_DEST_PORT = 13122  # The client needs to listen for the offer message on 13122 UDP port
MAGIC_COOKIE = 0xabcddcba
MSG_TYPE_OFFER = 0x2  # Offer
MSG_TYPE_REQUEST = 0x3  # request
MSG_TYPE_PAYLOAD = 0x4  # payload
TEAM_NAME = "WeNeedToChooseName"

"""
The Handshake:
step 1. Player Listen: The client opens a UDP Socket in passive mode and waits for requests from one of the dealers in the network.

step 2. Dealer Broadcast: The dealer sends messages containing offers to all listeners in the network using Broadcast in the UDP protocol.

step 3. Player Connect: The client receives the offer from the Broadcast, and in response initiates the creation of a TCP connection directly with the dealer who sent the offer.

step 4. Connection Established: The dealer receives the connection request, confirms it, and updates that an active connection has been created with the client.
"""


class Player:
    """
        Represents a Player in the Blackjack game.
    """
    def __init__(self):
        """
                Initializes the Player instance with default values.
        """
        self.server_ip = None
        self.server_tcp_port = None
        self.tcp_socket = None
        self.total_sum = 0

    # step 1:
    def listen_for_offers(self):
        """
                Listens for UDP broadcast offers from an active Dealer.
        """

        # The client opens a UDP socket and waits for a Broadcast message on a predetermined port (13122).
        udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        udp_sock.bind(("", UDP_DEST_PORT))

        # Get an offer- a message contains the port on which it is listening on TCP.
        while True:
            try:
                #  getting the data and the info of the dealer
                data, addr = udp_sock.recvfrom(1024)  # set capacity to 1024 B
                server_ip = addr[0]

                # Cookie(4) + Type(1) + TCP_Port(2) = 7 bytes
                if len(data) < 7:
                    continue

                # (Unpacking)
                # ! = control the network Byte Order
                # I = 4 bytes (Cookie)
                # B = 1 byte (Type)
                # H = 2 bytes (Server TCP Port)
                cookie, msg_type, server_tcp_port = struct.unpack('!I B H', data[:7])

                #  (Validation)
                if cookie != MAGIC_COOKIE:
                    continue

                if msg_type != MSG_TYPE_OFFER:
                    continue

                print(f"Received offer from {server_ip}, attempting to connect on TCP port {server_tcp_port}...")
                self.server_ip = server_ip
                self.server_tcp_port = server_tcp_port
                break

            except Exception as e:
                print(f"Error receiving UDP packet: {e}")

            finally:
                # Always close the UDP socket when done (or if an error crashed the outer logic)
                udp_sock.close()

    # step 3:
    def initiate_game(self, rounds):  # request - also broadcast
        """
                Establishes a TCP connection with the Dealer and sends a Join Request.

                Args:
                    rounds (int): The number of rounds the player wants to play (1-255).

                Returns:
                    socket.socket: The active TCP socket if connection succeeded.
                    None: If connection failed or server info is missing.
        """
        #  The client accepts the Offer and want to initiate a TCP connection.
        if not self.server_ip or not self.server_tcp_port:
            print("Error: No server info found.")
            return None

        try:
            # create TCP socket
            self.tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

            # Connect:
            self.tcp_socket.connect((self.server_ip, self.server_tcp_port))
            print("Connected successfully via TCP!")

            # Sending a request to join

            team_name_bytes = TEAM_NAME.encode('utf-8')
            padded_team_name = team_name_bytes.ljust(32, b'\x00')[:32]

            requested_rounds = rounds

            # !  = Network Order (Big Endian)
            # I  = Cookie (4 bytes)
            # B  = Type (1 byte)
            # B  = Rounds (1 byte)
            # 32s= Team Name (32 bytes)
            request_packet = struct.pack('!I B B 32s', MAGIC_COOKIE, MSG_TYPE_REQUEST, requested_rounds,
                                         padded_team_name)

            # Sending
            self.tcp_socket.sendall(request_packet)

            return self.tcp_socket

        except Exception as e:

            print(f"Failed to connect via TCP: {e}")
            self.tcp_socket = None
            return None

    def all_recv(self, n):
        data = b''
        while len(data) < n:
            more = self.tcp_socket.recv(n - len(data))
            if not more:
                print("Connection closed before receiving full data")
                return
            data += more
        return data


    def send_decision(self, decision):
        #Send Hittt or Stand
        decision_bytes = decision.encode('utf-8').ljust(5, b'\x00')[:5]
        packet = struct.pack('!I B 5s', MAGIC_COOKIE, MSG_TYPE_PAYLOAD, decision_bytes)
        self.tcp_socket.sendall(packet)

    def receive_payload(self):
        #Receive payload from server (card or round result)
        header = self.all_recv(6)  # 4+1+1 minimal
        if not header or len(header) < 6:
            return None
        cookie, msg_type, result = struct.unpack('!I B B', header)
        if msg_type != MSG_TYPE_PAYLOAD:
            return None

        # Card data: rank (2 bytes) + suit (1 byte)
        card_data = self.all_recv(3)
        rank, suit = struct.unpack('!H B', card_data)
        card_get = Card(suit, rank)
        return result, card_get

    def play_game(self, rounds):
        statistics = {"wins":0, "losses":0, "ties":0}
        for round_num in range(1, rounds+1):
            print(f"\n=== Starting round {round_num} ===")
            player_total = 0
            #receive cards
            for i in range(0,2):
                payload = self.receive_payload()
                if not payload:
                     break
                result, card = payload
                print(f"DEBUG: suit={card.suit}, rank={card.rank}")
                print(f"You received card: {card.print_card()}")
                player_total += card.get_value()

            # dealer cards
            payload = self.receive_payload()
            if not payload:
                break
            result, card = payload
            print(f"Dealer received card: {card.print_card()}")
            flag=True
            # Ask player decision
            while flag:
                move = input("Hit or Stand? ").strip()
                if move.lower() == "hit":
                    self.send_decision("Hittt")
                    # wait for card
                    payload = self.receive_payload()
                    if not payload:
                        return
                    result, card = payload
                    print(f"Received card: {card.print_card()}")
                    player_total += card.get_value()
                    if player_total>21:
                        flag=False
                elif move.lower() == "stand":
                    self.send_decision("Stand")
                    flag = False
                else:
                    continue

            # round result from server
            try:
                header = self.all_recv(self.tcp_socket,6)
                cookie, msg_type, result = struct.unpack('!I B B', header)
                if result == 0x3:
                    print("You win this round!")
                    statistics["wins"] += 1
                elif result == 0x2:
                    print("You lose this round!")
                    statistics["losses"] += 1
                elif result == 0x1:
                    print("Tie!")
                    statistics["ties"] += 1
            except:
                return

        # final Statistics
        total_played = statistics["wins"] + statistics["losses"] + statistics["ties"]
        print(f"\nGame Over: {total_played} rounds played")
        print(f"Wins: {statistics['wins']}, Losses: {statistics['losses']}, Ties: {statistics['ties']}")
        if total_played > 0:
            print(f"Win rate: {statistics['wins']/total_played:.2f}")


def main():
    """
        Main entry point for a new Client.
        Parses user input, listens for server offers, and initiates the connection.
    """
    try:
        user_input = input("Please enter the number of rounds to play: ")
        rounds = int(user_input)

        # Validity check (because the protocol limits to one byte, i.e. a maximum of 255)
        if not (1 <= rounds <= 255):
            print("Error: Rounds must be between 1 and 255.")
            return

    except ValueError:
        print("Error: Please enter a valid integer number.")
        return

    player = Player()

    # --- Step 1 ---
    player.listen_for_offers()

    # --- Step 3 ---
    sock = player.initiate_game(rounds)
    while True:
        if sock:
            # --- Game Loop ---
            player.play_game(rounds)
        else:
            print("Failed to start game.")


if __name__ == "__main__":
    main()
