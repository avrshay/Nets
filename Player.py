import socket
import struct

from Cards import Card

UDP_DEST_PORT = 13122  # The client needs to listen for the offer message on 13122 UDP port
MAGIC_COOKIE = 0xabcddcba
MSG_TYPE_OFFER = 0x2  # Offer
MSG_TYPE_REQUEST = 0x3  # request
MSG_TYPE_PAYLOAD = 0x4  # payload
TEAM_NAME = "JackWho"

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
        try:
            while True:
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
                    print(f"MAGIC COOKIE is wrong")
                    continue

                if msg_type != MSG_TYPE_OFFER:
                    print(f"TYPE is unfamiliar")
                    continue

                print(f"{TEAM_NAME} Received offer from {server_ip}, attempting to connect on TCP port {server_tcp_port}...")
                self.server_ip = server_ip
                self.server_tcp_port = server_tcp_port
                break

        except Exception as e:
            print(f"{TEAM_NAME} has error receiving UDP packet: {e}")

        finally:
            # Always close the UDP socket when done (or if an error crashed the outer logic)
            udp_sock.close()
            print(f"{TEAM_NAME}'s UDP socket closed.")

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
            print(f"{TEAM_NAME} has error: No server info found.")
            return None

        try:
            # create TCP socket
            self.tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

            # Connect:
            self.tcp_socket.connect((self.server_ip, self.server_tcp_port))
            print(f"{TEAM_NAME} connected successfully via TCP!")

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

            print(f"{TEAM_NAME} failed to connect via TCP: {e}")
            self.tcp_socket = None
            return None

    def all_recv(self, n):
        data = b''
        try:
            while len(data) < n:
                more = self.tcp_socket.recv(n - len(data))
                if not more:
                    print(f"{TEAM_NAME} connection closed before receiving full data")
                    return
                data += more
            return data
        except ConnectionResetError:
            print(f"\n{TEAM_NAME} connection was forcibly closed by the dealer (Error 10054).")
            return None
        except Exception as e:
            print(f"\n[{TEAM_NAME}] Unexpected error during receive: {e}")
            return None

    def send_decision(self, decision):
        # Send Hittt or Stand
        decision_bytes = decision.encode('utf-8').ljust(5, b'\x00')[:5]
        packet = struct.pack('!I B 5s', MAGIC_COOKIE, MSG_TYPE_PAYLOAD, decision_bytes)
        self.tcp_socket.sendall(packet)

    def receive_payload(self):
        # Receive payload from server (card or round result)
        header = self.all_recv(6)  # 4 + 1 + 1
        if not header or len(header) < 6:
            print("The dealer kick you out!")
            return None

        cookie, msg_type, result = struct.unpack('!I B B', header)

        if cookie != MAGIC_COOKIE:
            print("Error: Invalid magic cookie in payload")
            return None

        card = None
        if msg_type != 0x4:
            print("Move is unfamiliar")
            return None

        if result == 0x0:
            # Round not over → card is included
            card_data = self.all_recv(3)
            rank, suit = struct.unpack('!H B', card_data)
            card = Card(suit, rank)
            return result, card
        else:
            # Round over → no card
            return result, None

    def play_game(self, rounds):
        try:
            statistics = {"wins": 0, "losses": 0, "ties": 0}
            for round_num in range(1, rounds + 1):
                print(f"\n=== {TEAM_NAME} starting round {round_num} ===")
                player_total = 0
                dealer_total = 0
                # receive initial cards
                for i in range(0, 2):
                    payload = self.receive_payload()
                    if not payload:
                        print(f"For {TEAM_NAME} game aborted.")
                        return
                    result, card = payload
                    if card:
                        print(f"You received card: {card.print_card()}")
                        player_total += card.get_value()
                        print(f"Your total: {player_total}")

                # dealer initial card
                payload = self.receive_payload()
                if not payload:
                    print(f"For {TEAM_NAME} Connection closed or invalid data")
                    return
                result, card = payload
                if card:
                    print(f"Dealer received card: {card.print_card()}")
                    dealer_total += card.get_value()
                    print(f"Dealer total: {dealer_total}")

                flag = True
                # Ask player decision
                while flag:
                    move = input("Hit or Stand? ").strip().lower()
                    if move.lower() == "hit":
                        self.send_decision("Hittt")
                        # wait for card
                        payload = self.receive_payload()
                        if not payload:
                            return  # failed
                        result, card = payload
                        if card:
                            print(f"Received card: {card.print_card()}")
                            player_total += card.get_value()
                            print(f"Your total: {player_total}")

                        if player_total > 21:
                            print("You went over 21! Bust!")
                            payload = self.receive_payload()
                            if not payload:
                                return
                            result, card = payload
                            if result != 0x0:
                                if result == 0x3:
                                    print("You win this round!")
                                    statistics["wins"] += 1
                                elif result == 0x2:
                                    print("You lose this round!")
                                    statistics["losses"] += 1
                                elif result == 0x1:
                                    print("You ties this round!")
                                    statistics["ties"] += 1
                                flag = False
                            break
                    elif move.lower() == "stand":
                        self.send_decision("Stand")
                        while True:
                            payload = self.receive_payload()
                            if not payload:
                                print(f"For {TEAM_NAME} connection closed or invalid data")
                                return
                            result, card = payload
                            if card:
                                print(f"Dealer received: {card.print_card()}")
                                dealer_total += card.get_value()
                                print(f"Dealer total: {dealer_total}")
                            if result != 0x0:
                                # round over
                                if result == 0x3:
                                    print("You win this round!")
                                    statistics["wins"] += 1
                                elif result == 0x2:
                                    print("You lose this round!")
                                    statistics["losses"] += 1
                                elif result == 0x1:
                                    print("You ties this round!")
                                    statistics["ties"] += 1
                                flag = False
                                break
                        break
                    else:
                        print(f"{TEAM_NAME} please enter 'Hit' or 'Stand'.")
                        continue

                print(f"End of round {round_num}")

            # final Statistics
            total_played = statistics["wins"] + statistics["losses"] + statistics["ties"]
            print(f"\n {TEAM_NAME} - Game Over: {total_played} rounds played")
            print(f"Wins: {statistics['wins']}, Losses: {statistics['losses']}, Ties: {statistics['ties']}")
            if total_played > 0:
                print(f"Win rate: {statistics['wins'] / total_played:.2f}")

        except KeyboardInterrupt:
            print("\nKeyboard interrupt detected. Exiting.")


def main():
    """
        Main entry point for a new Client.
        Parses user input, listens for server offers, and initiates the connection.
    """
    while True:
        while True:
            try:
                user_input = input(f"{TEAM_NAME} please enter the number of rounds to play: ")
                rounds = int(user_input)

                if not (1 <= rounds <= 255):
                    # Validity check (because the protocol limits to one byte, i.e. a maximum of 255)
                    print(f"{TEAM_NAME} - Error: Rounds must be between 1 and 255.")
                else:
                    break  # input ok - skip next

            except ValueError:
                print(f"{TEAM_NAME} - Error: Please enter a valid integer number.")

            except (KeyboardInterrupt, EOFError):
                print("\nExiting.")
                return

        player = Player()

        # --- Step 1 ---
        player.listen_for_offers()

        # --- Step 3 ---
        sock = player.initiate_game(rounds)
        if sock:
            # --- Game Loop ---
            player.play_game(rounds)

        else:
            print(f"{TEAM_NAME} - Failed to start game.")

        # If he wants to play again
        while True:
            try:
                again = input(f" \n{TEAM_NAME} do you want to play again? (y/n): ").strip().lower()
            except KeyboardInterrupt:
                print("\nKeyboard interrupt detected. Exiting.")
                return
            if again == 'y':
                break  # back to outer while loop
            elif again == 'n':
                print(f"Thanks for playing {TEAM_NAME}! Goodbye!")
                return
            else:
                print(f"{TEAM_NAME} please enter 'y' or 'n'.")


if __name__ == "__main__":
    main()
